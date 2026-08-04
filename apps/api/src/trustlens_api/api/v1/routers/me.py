"""Current-user and seller-profile endpoints."""

from __future__ import annotations

import dataclasses
from typing import Any

from fastapi import APIRouter, status

from trustlens.core.domain.entities import SellerProfile
from trustlens.core.domain.enums import UserRole, VerificationStatus
from trustlens.core.domain.errors import ConflictError, EntityNotFound
from trustlens.db.unit_of_work import SqlAlchemyUnitOfWork
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.auth import UserSummary
from trustlens_api.api.v1.schemas.common import envelope
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
    base = "".join(c if c.isalnum() else "-" for c in display_name.lower()).strip("-")[:40]
    base = base or "seller"
    for suffix in range(100):
        candidate = base if suffix == 0 else f"{base}-{suffix}"
        if not await uow.sellers.handle_exists(candidate):
            return candidate
    raise ConflictError("Could not allocate a unique handle. Try a different display name.")


def _seller_response(seller: SellerProfile, score=None) -> SellerResponse:
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


__all__ = ["router"]
