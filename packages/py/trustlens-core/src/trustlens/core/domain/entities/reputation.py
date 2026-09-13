"""Follows and reviews (feature REP-01).

A `Follow` is a buyer bookmarking a seller, not a listing - `Favorite`
(listing.py) already covers "save this item"; this is "keep an eye on this
seller." A `Review` is one side of a blind, transaction-scoped exchange: it
is only shown publicly once *both* the buyer and the seller for that same
transaction have left one (`ReviewRepository.list_visible_for_seller`
enforces this at the query level, not with a stored flag - visibility is a
property of the pair, not either row alone).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Follow:
    id: UUID
    follower_id: UUID
    seller_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Review:
    id: UUID
    transaction_id: UUID
    listing_id: UUID
    reviewer_id: UUID
    reviewee_id: UUID
    rating: int
    created_at: datetime
    comment: str | None = None


@dataclass(frozen=True, slots=True)
class SellerRatingSummary:
    seller_id: UUID
    average_rating: float | None
    review_count: int


__all__ = ["Follow", "Review", "SellerRatingSummary"]
