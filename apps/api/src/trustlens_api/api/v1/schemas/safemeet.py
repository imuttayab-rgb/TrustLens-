"""SafeMeet request/response models (feature SAFE-01)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from trustlens_api.api.v1.schemas.common import Schema


class MeetingVenueResponse(Schema):
    id: UUID
    name: str
    address: str
    city: str
    area: str | None = None
    latitude: float
    longitude: float
    is_active: bool
    notes: str | None = None
    created_at: datetime


class ProposeMeetupRequest(Schema):
    venue_id: UUID
    proposed_time: datetime
    message: str | None = Field(default=None, max_length=1_000)


class RespondToMeetupRequest(Schema):
    accept: bool


class MeetupResponse(Schema):
    id: UUID
    conversation_id: UUID
    listing_id: UUID
    buyer_id: UUID
    seller_id: UUID
    proposed_by: UUID
    venue_id: UUID
    proposed_time: datetime
    status: str
    created_at: datetime
    message: str | None = None
    responded_at: datetime | None = None


__all__ = [
    "MeetingVenueResponse",
    "MeetupResponse",
    "ProposeMeetupRequest",
    "RespondToMeetupRequest",
]
