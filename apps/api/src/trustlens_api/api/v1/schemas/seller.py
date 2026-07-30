"""Seller and listing schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from trustlens_api.api.v1.schemas.common import Schema


class SellerResponse(Schema):
    id: UUID
    handle: str
    display_name: str
    business_type: str | None = None
    city: str | None = None
    country_code: str | None = None
    bio: str | None = None
    account_opened_at: datetime
    identity_status: str
    phone_status: str
    email_status: str
    is_flagged: bool = False
    score: int | None = None
    risk_level: str | None = None


class UpdateSellerRequest(Schema):
    display_name: str | None = Field(default=None, min_length=2, max_length=150)
    business_type: str | None = Field(default=None, max_length=50)
    city: str | None = Field(default=None, max_length=80)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    bio: str | None = Field(default=None, max_length=2000)


class BecomeSellerRequest(Schema):
    display_name: str = Field(min_length=2, max_length=150)
    business_type: str | None = Field(default=None, max_length=50)
    city: str | None = Field(default=None, max_length=80)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)


class ListingResponse(Schema):
    id: UUID
    title: str
    description: str
    price: float | None = None
    currency: str | None = None
    category: str | None = None
    city: str | None = None
    status: str
    created_at: datetime
    risk_score: float | None = None
    labels: list[str] = Field(default_factory=list)


class CreateListingRequest(Schema):
    title: str = Field(min_length=3, max_length=250)
    description: str = Field(min_length=10, max_length=8000)
    price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    category: str | None = Field(default=None, max_length=80)
    condition: str | None = Field(default=None, max_length=40)
    city: str | None = Field(default=None, max_length=80)
    external_url: str | None = Field(default=None, max_length=2000)
    image_file_ids: list[UUID] = Field(default_factory=list, max_length=10)


class AppealResponse(Schema):
    id: UUID
    seller_id: UUID
    trust_score_id: UUID
    reason_category: str
    reason: str
    status: str
    submitted_at: datetime
    resolved_at: datetime | None = None
    decision: str | None = None
    resolution_note: str | None = None


class CreateAppealRequest(Schema):
    #: The SPECIFIC computation being appealed. Appealing "my score" is
    #: meaningless once it changes; appealing this one is reviewable.
    trust_score_id: UUID
    reason_category: str = Field(max_length=50)
    reason: str = Field(min_length=20, max_length=4000)


class AppealMessageRequest(Schema):
    body: str = Field(min_length=1, max_length=4000)


class JobStatusResponse(Schema):
    job_id: str
    status: str
    stage: str | None = None
    progress: int = Field(default=0, ge=0, le=100)
    result: dict | None = None
    error: str | None = None


__all__ = [
    "AppealMessageRequest",
    "AppealResponse",
    "BecomeSellerRequest",
    "CreateAppealRequest",
    "CreateListingRequest",
    "JobStatusResponse",
    "ListingResponse",
    "SellerResponse",
    "UpdateSellerRequest",
]
