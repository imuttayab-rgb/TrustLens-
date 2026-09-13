"""Follow and review request/response models (feature REP-01)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from trustlens_api.api.v1.schemas.common import Schema


class FollowSellerRequest(Schema):
    #: A handle, not the seller's internal user id - the same
    #: PII-minimisation boundary the public trust-score payload uses.
    handle: str = Field(min_length=1, max_length=60)


class CreateReviewRequest(Schema):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1_000)


class ReviewResponse(Schema):
    """The full shape, with both parties' user ids - only ever returned to
    one of those two parties about their own transaction (they already
    know who the other side is: messaging already exposes
    `counterpart_user_id`). Never used for the public, anonymous list."""

    id: UUID
    transaction_id: UUID
    listing_id: UUID
    reviewer_id: UUID
    reviewee_id: UUID
    rating: int
    comment: str | None = None
    created_at: datetime


class PublicReviewResponse(Schema):
    """No user ids - what an anonymous visitor to a seller's page sees."""

    id: UUID
    rating: int
    comment: str | None = None
    created_at: datetime


class SellerRatingSummaryResponse(Schema):
    average_rating: float | None
    review_count: int


class SellerReviewsResponse(Schema):
    items: list[PublicReviewResponse]
    summary: SellerRatingSummaryResponse


__all__ = [
    "CreateReviewRequest",
    "FollowSellerRequest",
    "PublicReviewResponse",
    "ReviewResponse",
    "SellerRatingSummaryResponse",
    "SellerReviewsResponse",
]
