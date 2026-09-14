"""Current-user, seller-profile and favorites endpoints."""

from __future__ import annotations

import dataclasses
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, status

from trustlens.core.application.use_cases.favorites import (
    AddFavorite,
    AddFavoriteCommand,
    ListFavoriteIds,
    ListFavorites,
    ListFavoritesQuery,
    RemoveFavorite,
    RemoveFavoriteCommand,
)
from trustlens.core.application.use_cases.saved_searches import (
    CreateSavedSearch,
    CreateSavedSearchCommand,
    DeleteSavedSearch,
    DeleteSavedSearchCommand,
    ListSavedSearches,
)
from trustlens.core.domain.entities import SellerProfile, TrustScore
from trustlens.core.domain.enums import UserRole, VerificationStatus
from trustlens.core.domain.errors import ConflictError, EntityNotFound, ValidationError
from trustlens.core.domain.policies import (
    MAX_HANDLE_LENGTH,
    MIN_HANDLE_LENGTH,
    is_reserved,
    slugify_handle,
)
from trustlens.db.unit_of_work import SqlAlchemyUnitOfWork
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.routers._public_listing_presentation import to_public_listing_response
from trustlens_api.api.v1.schemas.auth import UserSummary
from trustlens_api.api.v1.schemas.common import PageMeta, envelope
from trustlens_api.api.v1.schemas.favorite import AddFavoriteRequest, FavoriteIdsResponse
from trustlens_api.api.v1.schemas.saved_search import CreateSavedSearchRequest, SavedSearchResponse
from trustlens_api.api.v1.schemas.seller import (
    BecomeSellerRequest,
    SellerResponse,
    UpdateSellerRequest,
)

router = APIRouter(tags=["Me"])


@router.get("/me", summary="Current user")
async def get_me(actor: ActorDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    assert actor.user_id is not None
    user = await uow.users.get(actor.user_id)
    if user is None:
        raise EntityNotFound("user", actor.user_id)

    seller = await uow.sellers.get_by_user(user.id)
    return envelope(
        UserSummary(
            id=user.id,
            email=user.email.value,
            full_name=user.full_name,
            status=user.status.value,
            roles=[role.value for role in user.roles],
            permissions=sorted(actor.permissions),
            email_verified=user.is_email_verified,
            mfa_enabled=user.mfa_enabled,
            has_seller_profile=seller is not None,
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post(
    "/me/become-seller",
    status_code=status.HTTP_201_CREATED,
    summary="Upgrade a buyer account to also be a seller",
)
async def become_seller(
    body: BecomeSellerRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    if await uow.sellers.get_by_user(actor.user_id) is not None:
        raise ConflictError("This account already has a seller profile.")

    user = await uow.users.get(actor.user_id)
    if user is None:
        raise EntityNotFound("user", actor.user_id)

    now = container.clock.now()
    handle = await _unique_handle(uow, body.display_name)
    seller = await uow.sellers.create(
        SellerProfile(
            id=container.ids.new(),
            user_id=user.id,
            handle=handle,
            display_name=body.display_name,
            business_type=body.business_type,
            city=body.city,
            country_code=body.country_code,
            # Account age is measured from registration, not from the seller
            # upgrade: a long-standing buyer should not be treated as brand new.
            account_opened_at=user.created_at,
            created_at=now,
            email_status=(
                VerificationStatus.VERIFIED
                if user.is_email_verified
                else VerificationStatus.PENDING
            ),
        )
    )
    await uow.users.assign_role(user.id, UserRole.SELLER.value, granted_by=None)
    await uow.commit()

    # Roles changed, so every existing access token for this user is stale.
    await container.cache.incr(f"perm_version:{user.id}")
    await container.queue.enqueue(
        "scoring.recompute_trust_score", seller_id=str(seller.id), trigger="SIGNAL_CHANGE"
    )

    return envelope(_seller_response(seller).model_dump(by_alias=True), request_id=meta.request_id)


@router.get("/sellers/me", summary="Own seller profile")
async def get_my_seller(actor: ActorDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    assert actor.user_id is not None
    seller = await uow.sellers.get_by_user(actor.user_id)
    if seller is None:
        raise EntityNotFound("seller_profile", actor.user_id)

    score = await uow.trust_scores.get_current(seller.id)
    return envelope(
        _seller_response(seller, score).model_dump(by_alias=True), request_id=meta.request_id
    )


@router.patch("/sellers/me", summary="Update own seller profile")
async def update_my_seller(
    body: UpdateSellerRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    seller = await uow.sellers.get_by_user(actor.user_id)
    if seller is None:
        raise EntityNotFound("seller_profile", actor.user_id)

    changes = body.model_dump(exclude_unset=True, by_alias=False)
    updated = dataclasses.replace(seller, **changes, updated_at=container.clock.now())
    await uow.sellers.update(updated)
    await uow.commit()
    await container.cache.delete(f"seller:{seller.id}:summary")

    # The declared country feeds NETWORK_GEO_CONSISTENT, so changing it must
    # re-score rather than leave a stale comparison in place.
    if "country_code" in changes:
        await container.queue.enqueue(
            "scoring.recompute_trust_score",
            seller_id=str(seller.id),
            trigger="SIGNAL_CHANGE",
        )

    return envelope(_seller_response(updated).model_dump(by_alias=True), request_id=meta.request_id)


async def _unique_handle(uow: SqlAlchemyUnitOfWork, display_name: str) -> str:
    """Derive a free, non-impersonating handle from the display name.

    The handle is public identity: `/seller/<handle>` is where a buyer checks
    a score, so a derived `daraz-official` would hand a scammer a marketplace's
    reputation. Reserved names are refused outright rather than suffixed —
    `olx-1` still trades on the same brand (P2-04).
    """
    base = slugify_handle(display_name)
    if len(base) < MIN_HANDLE_LENGTH:
        base = "seller"
    if is_reserved(base):
        raise ValidationError(
            "That display name is reserved. Choose a name that is clearly your own.",
            field="displayName",
        )

    for suffix in range(100):
        candidate = base if suffix == 0 else f"{base}-{suffix}"
        # A numeric suffix can push the handle past the column limit, and a
        # truncated one could collide with a name already taken.
        if len(candidate) > MAX_HANDLE_LENGTH:
            candidate = f"{base[: MAX_HANDLE_LENGTH - len(str(suffix)) - 1].strip('-')}-{suffix}"
        if not await uow.sellers.handle_exists(candidate):
            return candidate
    raise ConflictError("Could not allocate a unique handle. Try a different display name.")


def _seller_response(seller: SellerProfile, score: TrustScore | None = None) -> SellerResponse:
    return SellerResponse(
        id=seller.id,
        handle=seller.handle,
        display_name=seller.display_name,
        business_type=seller.business_type,
        city=seller.city,
        country_code=seller.country_code,
        bio=seller.bio,
        account_opened_at=seller.account_opened_at,
        identity_status=seller.identity_status.value,
        phone_status=seller.phone_status.value,
        email_status=seller.email_status.value,
        is_flagged=seller.is_flagged,
        score=int(score.score) if score else None,
        risk_level=score.risk_level.value if score else None,
    )


# ── Favorites ────────────────────────────────────────────────────────
# A saved listing, not a scored signal - any signed-in user (buyer or
# seller) may save one, same as `/me` itself asks nothing about role.


@router.post(
    "/me/favorites",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Save a listing",
)
async def add_favorite(
    body: AddFavoriteRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
) -> None:
    assert actor.user_id is not None
    await AddFavorite(uow=uow, clock=container.clock, ids=container.ids).execute(
        AddFavoriteCommand(user_id=actor.user_id, listing_id=body.listing_id)
    )


@router.delete(
    "/me/favorites/{listing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unsave a listing",
)
async def remove_favorite(listing_id: UUID, actor: ActorDep, uow: UowDep) -> None:
    assert actor.user_id is not None
    await RemoveFavorite(uow=uow).execute(
        RemoveFavoriteCommand(user_id=actor.user_id, listing_id=listing_id)
    )


@router.get("/me/favorites", summary="List saved listings")
async def list_favorites(
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    assert actor.user_id is not None
    page = await ListFavorites(uow=uow).execute(
        ListFavoritesQuery(user_id=actor.user_id, limit=limit, offset=offset)
    )
    responses = [await to_public_listing_response(item, container, uow) for item in page.items]

    return envelope(
        [item.model_dump(by_alias=True) for item in responses],
        request_id=meta.request_id,
        pagination=PageMeta.build(
            page=(page.offset // page.limit) + 1,
            per_page=page.limit,
            total=page.total,
        ),
    )


@router.get(
    "/me/favorites/ids",
    summary="Listing ids the current user has saved",
    description=(
        "Unpaginated on purpose - meant for hydrating 'already saved' state "
        "on a page of catalog cards in one call, not for display."
    ),
)
async def list_favorite_ids(actor: ActorDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    assert actor.user_id is not None
    ids = await ListFavoriteIds(uow=uow).execute(actor.user_id)
    return envelope(
        FavoriteIdsResponse(listing_ids=sorted(ids)).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


# ── Saved searches ───────────────────────────────────────────────────
# A remembered browse filter (FAV-01), re-runnable with one click - the
# same "any signed-in user, no role check" reasoning as favorites above.


def _to_saved_search_response(search: Any) -> SavedSearchResponse:
    return SavedSearchResponse(
        id=search.id,
        name=search.name,
        category=search.category,
        q=search.q,
        city=search.city,
        area=search.area,
        min_price=search.min_price,
        max_price=search.max_price,
        created_at=search.created_at,
    )


@router.post(
    "/me/saved-searches",
    status_code=status.HTTP_201_CREATED,
    summary="Save the current browse filter",
)
async def create_saved_search(
    body: CreateSavedSearchRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    search = await CreateSavedSearch(uow=uow, clock=container.clock, ids=container.ids).execute(
        CreateSavedSearchCommand(
            user_id=actor.user_id,
            name=body.name,
            category=body.category,
            q=body.q,
            city=body.city,
            area=body.area,
            min_price=body.min_price,
            max_price=body.max_price,
        )
    )
    return envelope(
        _to_saved_search_response(search).model_dump(by_alias=True), request_id=meta.request_id
    )


@router.get("/me/saved-searches", summary="List saved searches")
async def list_saved_searches(actor: ActorDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    assert actor.user_id is not None
    searches = await ListSavedSearches(uow=uow).execute(actor.user_id)
    return envelope(
        [_to_saved_search_response(item).model_dump(by_alias=True) for item in searches],
        request_id=meta.request_id,
    )


@router.delete(
    "/me/saved-searches/{search_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved search",
)
async def delete_saved_search(search_id: UUID, actor: ActorDep, uow: UowDep) -> None:
    assert actor.user_id is not None
    await DeleteSavedSearch(uow=uow).execute(
        DeleteSavedSearchCommand(user_id=actor.user_id, search_id=search_id)
    )


__all__ = ["router"]
