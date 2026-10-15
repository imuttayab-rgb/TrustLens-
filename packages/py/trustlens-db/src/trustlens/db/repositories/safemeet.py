"""Safemeet repositories. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from trustlens.core.domain import entities as ent
from trustlens.core.domain import enums as e
from trustlens.db import mappers as map_
from trustlens.db import models as m


class SqlMeetingVenueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, venue: ent.MeetingVenue) -> ent.MeetingVenue:
        self._s.add(
            m.MeetingVenueModel(
                id=venue.id,
                name=venue.name,
                address=venue.address,
                city=venue.city,
                area=venue.area,
                latitude=venue.latitude,
                longitude=venue.longitude,
                is_active=venue.is_active,
                notes=venue.notes,
                created_at=venue.created_at,
            )
        )
        await self._s.flush()
        return venue

    async def get(self, venue_id: UUID) -> ent.MeetingVenue | None:
        row = await self._s.get(m.MeetingVenueModel, venue_id)
        return map_.to_meeting_venue(row) if row else None

    async def list_near(self, *, city: str, limit: int = 5) -> list[ent.MeetingVenue]:
        stmt = (
            select(m.MeetingVenueModel)
            .where(
                m.MeetingVenueModel.city == city,
                m.MeetingVenueModel.is_active.is_(True),
            )
            .order_by(m.MeetingVenueModel.created_at.desc())
            .limit(limit)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_meeting_venue(r) for r in rows]

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[ent.MeetingVenue]:
        stmt = (
            select(m.MeetingVenueModel)
            .order_by(m.MeetingVenueModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_meeting_venue(r) for r in rows]

    async def set_active(self, venue_id: UUID, *, is_active: bool) -> ent.MeetingVenue:
        await self._s.execute(
            update(m.MeetingVenueModel)
            .where(m.MeetingVenueModel.id == venue_id)
            .values(is_active=is_active)
        )
        row = await self._s.get(m.MeetingVenueModel, venue_id)
        assert row is not None
        return map_.to_meeting_venue(row)


class SqlMeetupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, meetup: ent.Meetup) -> ent.Meetup:
        self._s.add(
            m.MeetupModel(
                id=meetup.id,
                conversation_id=meetup.conversation_id,
                listing_id=meetup.listing_id,
                buyer_id=meetup.buyer_id,
                seller_id=meetup.seller_id,
                proposed_by=meetup.proposed_by,
                venue_id=meetup.venue_id,
                proposed_time=meetup.proposed_time,
                status=meetup.status,
                created_at=meetup.created_at,
                message=meetup.message,
            )
        )
        await self._s.flush()
        return meetup

    async def get(self, meetup_id: UUID) -> ent.Meetup | None:
        row = await self._s.get(m.MeetupModel, meetup_id)
        return map_.to_meetup(row) if row else None

    async def list_for_conversation(self, conversation_id: UUID) -> list[ent.Meetup]:
        stmt = (
            select(m.MeetupModel)
            .where(m.MeetupModel.conversation_id == conversation_id)
            .order_by(m.MeetupModel.created_at.asc())
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_meetup(r) for r in rows]

    async def get_open_for_conversation(self, conversation_id: UUID) -> ent.Meetup | None:
        stmt = select(m.MeetupModel).where(
            m.MeetupModel.conversation_id == conversation_id,
            m.MeetupModel.status == e.MeetupStatus.PROPOSED,
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_meetup(row) if row else None

    async def close(
        self, meetup_id: UUID, *, status: e.MeetupStatus, responded_at: datetime
    ) -> ent.Meetup:
        await self._s.execute(
            update(m.MeetupModel)
            .where(m.MeetupModel.id == meetup_id)
            .values(status=status, responded_at=responded_at)
        )
        row = await self._s.get(m.MeetupModel, meetup_id)
        assert row is not None
        return map_.to_meetup(row)
