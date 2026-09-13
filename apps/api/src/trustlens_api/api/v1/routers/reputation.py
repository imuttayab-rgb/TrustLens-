"""Follows and reviews (feature REP-01).

Follows and review creation live under /me and /transactions, the usual
signed-in-user convention. The public reviews read lives under
/public/sellers/{handle}/reviews, mirroring public_scores.py: anonymous,
and keyed by handle rather than the seller's internal user id - the same
PII-minimisation boundary that keeps the public trust-score payload free
of it (see MOD-01's SellerReportButton for the same reasoning applied to
reporting). `PublicReviewResponse` carries no user ids at all for the
same reason.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, status

from trustlens.core.application.use_cases.reputation import (
    CreateReview,
    CreateReviewCommand,
    FollowSeller,
    FollowSellerCommand,
    GetMyReviewForTransaction,
    ListFollowedSellerIds,
    ListReviewsForSeller,
    UnfollowSeller,
    UnfollowSellerCommand,
)
from trustlens.core.domain.entities import SellerProfile
from trustlens.core.domain.errors import EntityNotFound
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.common import envelope
from trustlens_api.api.v1.schemas.reputation import (
    CreateReviewRequest,
    FollowSellerRequest,
    PublicReviewResponse,
    ReviewResponse,
    SellerRatingSummaryResponse,
    SellerReviewsResponse,
)

router = APIRouter(tags=["Reputation"])


def _to_review_response(review: Any) -> ReviewResponse:
    return ReviewResponse(
        id=review.id,
        transaction_id=review.transaction_id,
        listing_id=review.listing_id,
        reviewer_id=review.reviewer_id,
        reviewee_id=review.reviewee_id,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
    )


async def _resolve_seller_user_id(uow: UowDep, handle: str) -> UUID:
    seller: SellerProfile | None = await uow.sellers.get_by_handle(handle)
    if seller is None:
        raise EntityNotFound("seller", handle)
    return seller.user_id


@router.post(
    "/me/follows", status_code=status.HTTP_204_NO_CONTENT, summary="Follow a seller by handle"
)
async def follow_seller(
    body: FollowSellerRequest, actor: ActorDep, container: ContainerDep, uow: UowDep
) -> None:
    assert actor.user_id is not None
    seller_user_id = await _resolve_seller_user_id(uow, body.handle)
    await FollowSeller(uow=uow, clock=container.clock, ids=container.ids).execute(
        FollowSellerCommand(follower_id=actor.user_id, seller_id=seller_user_id)
    )


@router.delete(
    "/me/follows/{handle}", status_code=status.HTTP_204_NO_CONTENT, summary="Unfollow a seller"
)
async def unfollow_seller(handle: str, actor: ActorDep, uow: UowDep) -> None:
    assert actor.user_id is not None
    seller_user_id = await _resolve_seller_user_id(uow, handle)
    await UnfollowSeller(uow=uow).execute(
        UnfollowSellerCommand(follower_id=actor.user_id, seller_id=seller_user_id)
    )


@router.get("/me/follows", summary="Sellers I follow")
async def list_my_follows(actor: ActorDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    assert actor.user_id is not None
    seller_ids = await ListFollowedSellerIds(uow=uow).execute(actor.user_id)
    handles: list[str] = []
    for seller_id in seller_ids:
        seller = await uow.sellers.get_by_user(seller_id)
        if seller is not None:
            handles.append(seller.handle)
    return envelope(handles, request_id=meta.request_id)


@router.post(
    "/transactions/{transaction_id}/reviews",
    status_code=status.HTTP_201_CREATED,
    summary="Review the other party in a completed transaction",
)
async def create_review(
    transaction_id: UUID,
    body: CreateReviewRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    review = await CreateReview(uow=uow, clock=container.clock, ids=container.ids).execute(
        CreateReviewCommand(
            transaction_id=transaction_id,
            reviewer_id=actor.user_id,
            rating=body.rating,
            comment=body.comment,
        )
    )
    return envelope(
        _to_review_response(review).model_dump(by_alias=True), request_id=meta.request_id
    )


@router.get(
    "/transactions/{transaction_id}/reviews/mine",
    summary="My own review of this transaction, if I've left one",
)
async def get_my_review(
    transaction_id: UUID, actor: ActorDep, uow: UowDep, meta: MetaDep
) -> dict[str, Any]:
    assert actor.user_id is not None
    review = await GetMyReviewForTransaction(uow=uow).execute(transaction_id, actor.user_id)
    return envelope(
        _to_review_response(review).model_dump(by_alias=True) if review else None,
        request_id=meta.request_id,
    )


@router.get(
    "/public/sellers/{handle}/reviews",
    summary="A seller's public reviews and rating (no auth)",
    description=(
        "Only reviews where both sides of the transaction have left one are "
        "shown - the blind-reveal rule. No reviewer/reviewee identity is "
        "included, matching the public trust-score payload's PII boundary."
    ),
)
async def list_seller_reviews(
    handle: str,
    uow: UowDep,
    meta: MetaDep,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    seller_user_id = await _resolve_seller_user_id(uow, handle)
    page = await ListReviewsForSeller(uow=uow).execute(seller_user_id, limit=limit, offset=offset)
    body = SellerReviewsResponse(
        items=[
            PublicReviewResponse(
                id=r.id, rating=r.rating, comment=r.comment, created_at=r.created_at
            )
            for r in page.items
        ],
        summary=SellerRatingSummaryResponse(
            average_rating=page.summary.average_rating,
            review_count=page.summary.review_count,
        ),
    )
    return envelope(body.model_dump(by_alias=True), request_id=meta.request_id)


__all__ = ["router"]
