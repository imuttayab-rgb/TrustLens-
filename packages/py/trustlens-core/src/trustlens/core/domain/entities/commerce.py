"""Offers, counter-offers and transactions (feature OFF-01).

An offer lives inside a conversation - the same immutable-listing-snapshot
reasoning `messaging.py` describes applies here too, but the fields that
matter for a price negotiation (amount, status, expiry) are small and
frequently updated, so this is its own entity rather than a field on
`Message`.

A counter-offer is not an edit: it is a new `Offer` row with
`parent_offer_id` set, and the offer it replies to is closed out
(COUNTERED). This keeps the full negotiation history intact and matches how
`ScoringModel` versions or `TrustScore` recomputes are handled elsewhere in
this codebase - state changes append, they do not overwrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from trustlens.core.domain.enums import OfferStatus, TransactionStatus


@dataclass(frozen=True, slots=True)
class Offer:
    id: UUID
    conversation_id: UUID
    listing_id: UUID
    buyer_id: UUID
    #: The seller's users.id, not their seller_profiles.id - symmetric with
    #: buyer_id, and what a Transaction and a Block both key on.
    seller_id: UUID
    #: Who made *this* offer - the buyer proposing a price, or the seller
    #: countering. Needed because either side can be "offering".
    offered_by: UUID
    amount: float
    currency: str
    status: OfferStatus
    created_at: datetime
    expires_at: datetime
    message: str | None = None
    parent_offer_id: UUID | None = None
    responded_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.status.is_open


@dataclass(frozen=True, slots=True)
class Transaction:
    """Created the moment an offer is accepted. One listing can only have
    one open transaction at a time - accepting an offer is what reserves
    the listing (ListingStatus.RESERVED)."""

    id: UUID
    listing_id: UUID
    buyer_id: UUID
    seller_id: UUID
    offer_id: UUID
    amount: float
    currency: str
    status: TransactionStatus
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status.is_open


__all__ = ["Offer", "Transaction"]
