"""Following a seller, and leaving a blind, transaction-scoped review
(feature REP-01).

Follow is a plain bookmark - add/remove are both idempotent, the same
"heart button" reasoning `favorites/manage.py` documents. A review is not:
it can only be left once per person per transaction, only once that
transaction is COMPLETED, and only by one of its two parties about the
other. Visibility (whether it is shown publicly yet) is computed at read
time by `ReviewRepository.list_visible_for_seller`, not decided here.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from trustlens.core.domain.entities import Follow, Review, SellerRatingSummary
from trustlens.core.domain.enums import TransactionStatus
from trustlens.core.domain.errors import (
    EntityNotFound,
    InvalidStateError,
    PermissionDenied,
    ValidationError,
)
from trustlens.core.domain.ports import Clock, IdGenerator, UnitOfWork


@dataclass(frozen=True, slots=True)
class FollowSellerCommand:
    follower_id: UUID
    seller_id: UUID


class FollowSeller:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: FollowSellerCommand) -> None:
        if cmd.follower_id == cmd.seller_id:
            raise ValidationError("You cannot follow yourself.", field="sellerId")
        async with self._uow:
            seller = await self._uow.sellers.get_by_user(cmd.seller_id)
            if seller is None:
                raise EntityNotFound("seller", cmd.seller_id)

            if await self._uow.follows.exists(follower_id=cmd.follower_id, seller_id=cmd.seller_id):
                return

            await self._uow.follows.add(
                Follow(
                    id=self._ids.new(),
                    follower_id=cmd.follower_id,
                    seller_id=cmd.seller_id,
                    created_at=self._clock.now(),
                )
            )
            await self._uow.commit()


@dataclass(frozen=True, slots=True)
class UnfollowSellerCommand:
    follower_id: UUID
    seller_id: UUID


class UnfollowSeller:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, cmd: UnfollowSellerCommand) -> None:
        async with self._uow:
            await self._uow.follows.remove(follower_id=cmd.follower_id, seller_id=cmd.seller_id)
            await self._uow.commit()


class ListFollowedSellerIds:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, follower_id: UUID) -> frozenset[UUID]:
        async with self._uow:
            return await self._uow.follows.list_followed_seller_ids(follower_id)


@dataclass(frozen=True, slots=True)
class CreateReviewCommand:
    transaction_id: UUID
    reviewer_id: UUID
    rating: int
    comment: str | None = None


class CreateReview:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: CreateReviewCommand) -> Review:
        if not 1 <= cmd.rating <= 5:
            raise ValidationError("Rating must be between 1 and 5.", field="rating")

        async with self._uow:
            transaction = await self._uow.transactions.get(cmd.transaction_id)
            if transaction is None:
                raise EntityNotFound("transaction", cmd.transaction_id)
            if transaction.status != TransactionStatus.COMPLETED:
                raise InvalidStateError("You can only review a completed transaction.")
            if cmd.reviewer_id not in (transaction.buyer_id, transaction.seller_id):
                raise PermissionDenied("This transaction belongs to someone else.")

            existing = await self._uow.reviews.get_by_transaction_and_reviewer(
                transaction.id, cmd.reviewer_id
            )
            if existing is not None:
                raise InvalidStateError("You have already reviewed this transaction.")

            reviewee_id = (
                transaction.seller_id
                if cmd.reviewer_id == transaction.buyer_id
                else transaction.buyer_id
            )
            review = await self._uow.reviews.add(
                Review(
                    id=self._ids.new(),
                    transaction_id=transaction.id,
                    listing_id=transaction.listing_id,
                    reviewer_id=cmd.reviewer_id,
                    reviewee_id=reviewee_id,
                    rating=cmd.rating,
                    comment=cmd.comment,
                    created_at=self._clock.now(),
                )
            )
            await self._uow.commit()
        return review


class GetMyReviewForTransaction:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, transaction_id: UUID, reviewer_id: UUID) -> Review | None:
        async with self._uow:
            return await self._uow.reviews.get_by_transaction_and_reviewer(
                transaction_id, reviewer_id
            )


@dataclass(frozen=True, slots=True)
class SellerReviewsPage:
    items: tuple[Review, ...]
    summary: SellerRatingSummary
    limit: int
    offset: int


class ListReviewsForSeller:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self, seller_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> SellerReviewsPage:
        bounded = max(1, min(limit, 50))
        async with self._uow:
            items = await self._uow.reviews.list_visible_for_seller(
                seller_id, limit=bounded, offset=max(0, offset)
            )
            summary = await self._uow.reviews.get_rating_summary(seller_id)
        return SellerReviewsPage(
            items=tuple(items), summary=summary, limit=bounded, offset=max(0, offset)
        )


__all__ = [
    "CreateReview",
    "CreateReviewCommand",
    "FollowSeller",
    "FollowSellerCommand",
    "GetMyReviewForTransaction",
    "ListFollowedSellerIds",
    "ListReviewsForSeller",
    "SellerReviewsPage",
    "UnfollowSeller",
    "UnfollowSellerCommand",
]
