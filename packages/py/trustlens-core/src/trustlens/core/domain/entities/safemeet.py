"""Platform-curated meetup spots and proposals (feature SAFE-01).

A `MeetingVenue` is a public location - a police station, a mall, a busy
cafe - vetted and published by staff, never a party's home address. A
`Meetup` is a specific place+time proposed for one conversation's deal;
either party can propose one, and it only becomes a plan once the other
side accepts the *same* proposal (mutual accept, not just an offer).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from trustlens.core.domain.enums import MeetupStatus


@dataclass(frozen=True, slots=True)
class MeetingVenue:
    id: UUID
    name: str
    address: str
    city: str
    latitude: float
    longitude: float
    is_active: bool
    created_at: datetime
    area: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class Meetup:
    id: UUID
    conversation_id: UUID
    listing_id: UUID
    buyer_id: UUID
    seller_id: UUID
    #: Who proposed *this* place+time - either side can propose.
    proposed_by: UUID
    venue_id: UUID
    proposed_time: datetime
    status: MeetupStatus
    created_at: datetime
    message: str | None = None
    responded_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.status.is_open


__all__ = ["MeetingVenue", "Meetup"]
