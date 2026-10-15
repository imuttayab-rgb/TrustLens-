"""Safemeet models. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from trustlens.core.domain import enums as e
from trustlens.db.base import (
    Base,
    uuid_fk,
    uuid_pk,
)
from .common import pg_enum


class MeetingVenueModel(Base):
    """A staff-curated public meetup spot (SAFE-01) - never a party's home
    address. Deactivated rather than deleted, so past meetups keep a valid
    FK to whatever venue they were actually proposed at."""

    __tablename__ = "meeting_venues"

    id: Mapped[UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    area: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_meeting_venues_city", "city", "is_active"),)


class MeetupModel(Base):
    """A specific place+time proposed for one conversation's handover
    (SAFE-01). Mutual accept, not a one-sided offer: `status` only moves to
    ACCEPTED when the other party responds yes to this exact proposal."""

    __tablename__ = "meetups"

    id: Mapped[UUID] = uuid_pk()
    conversation_id: Mapped[UUID] = uuid_fk("conversations.id")
    listing_id: Mapped[UUID] = uuid_fk("listings.id")
    buyer_id: Mapped[UUID] = uuid_fk("users.id")
    seller_id: Mapped[UUID] = uuid_fk("users.id")
    proposed_by: Mapped[UUID] = uuid_fk("users.id")
    venue_id: Mapped[UUID] = uuid_fk("meeting_venues.id")
    proposed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[e.MeetupStatus] = mapped_column(
        pg_enum(e.MeetupStatus, "meetup_status"), nullable=False, default=e.MeetupStatus.PROPOSED
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    message: Mapped[str | None] = mapped_column(Text)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_meetups_conversation", "conversation_id", "created_at"),
        # At most one open proposal per conversation at a time, same
        # partial-index pattern as uq_offers_listing_open.
        Index(
            "uq_meetups_conversation_open",
            "conversation_id",
            unique=True,
            postgresql_where=text("status = 'PROPOSED'"),
        ),
    )
