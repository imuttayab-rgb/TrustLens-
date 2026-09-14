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


__all__ = [
    "CancelTransactionRequest",
    "CreateOfferRequest",
    "OfferResponse",
    "RaiseDisputeRequest",
    "ResolveDisputeRequest",
    "RespondToOfferRequest",
    "TransactionResponse",
]
