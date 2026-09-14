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

from trustlens.core.domain.enums import (
    AuctionStatus,
    InstallmentPlanStatus,
    InstallmentStatus,
    OfferStatus,
    TransactionStatus,
)


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


@dataclass(frozen=True, slots=True)
class InstallmentPlan:
    """Buy-now-pay-later, sandboxed (PAY-01): the platform tracks a payment
    schedule against an existing Transaction, it does not move money. Each
    Installment is marked paid the same mutual-trust way `CompleteTransaction`
    already works - either party can confirm it, there is no card charge or
    gateway behind it."""

    id: UUID
    transaction_id: UUID
    buyer_id: UUID
    seller_id: UUID
    total_amount: float
    currency: str
    installment_count: int
    status: InstallmentPlanStatus
    created_at: datetime
    cancelled_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.status.is_open


@dataclass(frozen=True, slots=True)
class Installment:
    id: UUID
    plan_id: UUID
    #: 1-indexed position in the schedule - installments are paid in order,
    #: so this is also how "the next payable one" is found.
    sequence_number: int
    amount: float
    due_at: datetime
    status: InstallmentStatus
    created_at: datetime
    paid_at: datetime | None = None
    #: Whichever party marked it paid - kept for the same reason a
    #: transaction's completion isn't anonymous: it's a claim one side is
    #: making, and disputing it later needs to know who made it.
    paid_by: UUID | None = None

    @property
    def is_paid(self) -> bool:
        return self.status == InstallmentStatus.PAID


@dataclass(frozen=True, slots=True)
class Auction:
    """A listing sold competitively instead of at a fixed price (AUC-01) -
    a distinct mechanism from OFF-01's offers, not a reuse of them: bidding
    is public and time-boxed, an offer is one buyer negotiating privately.
    """

    id: UUID
    listing_id: UUID
    seller_id: UUID
    starting_price: float
    currency: str
    ends_at: datetime
    status: AuctionStatus
    created_at: datetime
    #: The lowest amount the seller will actually accept - never shown to
    #: bidders, the same "declared but private" shape a lot of real auction
    #: sites use. Bidding can proceed below it; closing without a bid at or
    #: above it ends the auction with no winner.
    reserve_price: float | None = None
    #: Set once the auction ends with at least one qualifying bid.
    winning_bid_id: UUID | None = None
    ended_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.status.is_open


@dataclass(frozen=True, slots=True)
class Bid:
    id: UUID
    auction_id: UUID
    bidder_id: UUID
    amount: float
    created_at: datetime


__all__ = ["Auction", "Bid", "Installment", "InstallmentPlan", "Offer", "Transaction"]
