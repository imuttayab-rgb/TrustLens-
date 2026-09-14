"""Offers and transactions request/response models (feature OFF-01)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from trustlens.core.application.use_cases.moderation import (
    MAX_REPORT_DESCRIPTION_CHARS,
    MIN_REPORT_DESCRIPTION_CHARS,
)
from trustlens_api.api.v1.schemas.common import Schema


class CreateOfferRequest(Schema):
    amount: float = Field(gt=0)
    currency: str = Field(default="PKR", min_length=3, max_length=3)
    message: str | None = Field(default=None, max_length=1_000)
    ttl_hours: int = Field(default=48, ge=1, le=24 * 14)


class RespondToOfferRequest(Schema):
    accept: bool


class OfferResponse(Schema):
    id: UUID
    conversation_id: UUID
    listing_id: UUID
    buyer_id: UUID
    seller_id: UUID
    offered_by: UUID
    amount: float
    currency: str
    status: str
    created_at: datetime
    expires_at: datetime
    message: str | None = None
    parent_offer_id: UUID | None = None
    responded_at: datetime | None = None


class TransactionResponse(Schema):
    id: UUID
    listing_id: UUID
    buyer_id: UUID
    seller_id: UUID
    offer_id: UUID
    amount: float
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None


class CancelTransactionRequest(Schema):
    reason: str = Field(min_length=1, max_length=1_000)


class RaiseDisputeRequest(Schema):
    category: str
    description: str = Field(
        min_length=MIN_REPORT_DESCRIPTION_CHARS, max_length=MAX_REPORT_DESCRIPTION_CHARS
    )


class ResolveDisputeRequest(Schema):
    #: "COMPLETED" or "CANCELLED" - the only two outcomes a dispute resolves to.
    outcome: str


class CreateInstallmentPlanRequest(Schema):
    installment_count: int = Field(ge=2, le=12)
    frequency_days: int = Field(ge=7, le=90)


class InstallmentResponse(Schema):
    id: UUID
    sequence_number: int
    amount: float
    due_at: datetime
    status: str
    paid_at: datetime | None = None
    paid_by: UUID | None = None


class InstallmentPlanResponse(Schema):
    id: UUID
    transaction_id: UUID
    buyer_id: UUID
    seller_id: UUID
    total_amount: float
    currency: str
    installment_count: int
    status: str
    created_at: datetime
    cancelled_at: datetime | None = None
    installments: list[InstallmentResponse] = Field(default_factory=list)


class CreateAuctionRequest(Schema):
    starting_price: float = Field(gt=0)
    currency: str = Field(default="PKR", min_length=3, max_length=3)
    duration_hours: int = Field(ge=1, le=24 * 14)
    reserve_price: float | None = Field(default=None, gt=0)


class PlaceBidRequest(Schema):
    amount: float = Field(gt=0)


class AuctionResponse(Schema):
    id: UUID
    listing_id: UUID
    seller_id: UUID
    starting_price: float
    currency: str
    ends_at: datetime
    status: str
    created_at: datetime
    reserve_price: float | None = None
    winning_bid_id: UUID | None = None
    ended_at: datetime | None = None
    #: Convenience for a client that just wants "what do I have to beat" -
    #: derived from the bid list, not stored.
    current_price: float | None = None
    bid_count: int = 0


class BidResponse(Schema):
    id: UUID
    auction_id: UUID
    bidder_id: UUID
    amount: float
    created_at: datetime


__all__ = [
    "AuctionResponse",
    "BidResponse",
    "CancelTransactionRequest",
    "CreateAuctionRequest",
    "CreateInstallmentPlanRequest",
    "CreateOfferRequest",
    "InstallmentPlanResponse",
    "InstallmentResponse",
    "OfferResponse",
    "PlaceBidRequest",
    "RaiseDisputeRequest",
    "ResolveDisputeRequest",
    "RespondToOfferRequest",
    "TransactionResponse",
]
