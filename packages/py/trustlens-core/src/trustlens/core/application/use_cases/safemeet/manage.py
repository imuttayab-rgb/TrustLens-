"""Platform-curated meetup proposals (feature SAFE-01).

A meetup is proposed for a conversation, at a staff-curated `MeetingVenue` -
never a party's home address. At most one open (PROPOSED) meetup exists per
conversation at a time (enforced at the database level too,
`uq_meetups_conversation_open`); a new proposal while one is open replaces
it (the old one is cancelled), matching how a re-offered price replaces the
open offer in OFF-01.

Accepting a meetup does not, by itself, complete the deal - it nudges the
matching open transaction (if one exists) to MEETUP_PLANNED so its status
reflects "handover is planned", but completing or cancelling the deal is
still the buyer/seller's own call via `CompleteTransaction`/`CancelTransaction`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from trustlens.core.application.notifications import notify
from trustlens.core.domain.entities import MeetingVenue, Meetup
from trustlens.core.domain.enums import MeetupStatus, TransactionStatus
from trustlens.core.domain.errors import (
    EntityNotFound,
    InvalidStateError,
    PermissionDenied,
    ValidationError,
)
from trustlens.core.domain.ports import Clock, IdGenerator, UnitOfWork


class ListNearbyVenues:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, city: str, limit: int = 5) -> list[MeetingVenue]:
        bounded = max(1, min(limit, 10))
        async with self._uow:
            return await self._uow.meeting_venues.list_near(city=city, limit=bounded)


@dataclass(frozen=True, slots=True)
class ProposeMeetupCommand:
    conversation_id: UUID
    proposed_by: UUID
    venue_id: UUID
    proposed_time: datetime
    message: str | None = None


class ProposeMeetup:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: ProposeMeetupCommand) -> Meetup:
        now = self._clock.now()
        if cmd.proposed_time <= now:
            raise ValidationError(
                "Proposed meetup time must be in the future.", field="proposedTime"
            )

        async with self._uow:
            conversation = await self._uow.messaging.get_conversation(cmd.conversation_id)
            if conversation is None:
                raise EntityNotFound("conversation", cmd.conversation_id)
            if conversation.listing_id is None:
                raise ValidationError(
                    "This conversation isn't about a specific listing.",
                    field="conversationId",
                )

            participants = await self._uow.messaging.get_participants(conversation.id)
            if participants is None or cmd.proposed_by not in participants:
                raise PermissionDenied("This conversation belongs to someone else.")
            buyer_id, seller_id = participants

            venue = await self._uow.meeting_venues.get(cmd.venue_id)
            if venue is None or not venue.is_active:
                raise EntityNotFound("meeting venue", cmd.venue_id)

            existing_open = await self._uow.meetups.get_open_for_conversation(conversation.id)
            if existing_open is not None:
                await self._uow.meetups.close(
                    existing_open.id, status=MeetupStatus.CANCELLED, responded_at=now
                )

            meetup = await self._uow.meetups.add(
                Meetup(
                    id=self._ids.new(),
                    conversation_id=conversation.id,
                    listing_id=conversation.listing_id,
                    buyer_id=buyer_id,
                    seller_id=seller_id,
                    proposed_by=cmd.proposed_by,
                    venue_id=venue.id,
                    proposed_time=cmd.proposed_time,
                    status=MeetupStatus.PROPOSED,
                    created_at=now,
                    message=cmd.message,
                )
            )
            recipient = seller_id if cmd.proposed_by == buyer_id else buyer_id
            await notify(
                self._uow,
                self._ids,
                self._clock,
                user_id=recipient,
                type="MEETUP_PROPOSED",
                title="SafeMeet proposed",
                body=f"A meetup was proposed at {venue.name}.",
                data={"conversationId": str(conversation.id), "meetupId": str(meetup.id)},
            )
            await self._uow.commit()
        return meetup


class ListMeetupsForConversation:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, conversation_id: UUID, requester_id: UUID) -> list[Meetup]:
        async with self._uow:
            participants = await self._uow.messaging.get_participants(conversation_id)
            if participants is None or requester_id not in participants:
                raise PermissionDenied("This conversation belongs to someone else.")
            return await self._uow.meetups.list_for_conversation(conversation_id)


@dataclass(frozen=True, slots=True)
class RespondToMeetupCommand:
    meetup_id: UUID
    responder_id: UUID
    accept: bool


class RespondToMeetup:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: RespondToMeetupCommand) -> Meetup:
        now = self._clock.now()
        async with self._uow:
            meetup = await self._uow.meetups.get(cmd.meetup_id)
            if meetup is None:
                raise EntityNotFound("meetup", cmd.meetup_id)
            if not meetup.is_open:
                raise InvalidStateError("This meetup proposal is no longer open.")
            if cmd.responder_id == meetup.proposed_by:
                raise PermissionDenied("You cannot respond to your own proposal.")
            if cmd.responder_id not in (meetup.buyer_id, meetup.seller_id):
                raise PermissionDenied("This meetup belongs to someone else.")

            status = MeetupStatus.ACCEPTED if cmd.accept else MeetupStatus.DECLINED
            closed = await self._uow.meetups.close(meetup.id, status=status, responded_at=now)

            if cmd.accept:
                transaction = await self._uow.transactions.get_open_for_listing(meetup.listing_id)
                if transaction is not None and transaction.status in (
                    TransactionStatus.INITIATED,
                    TransactionStatus.AGREED,
                ):
                    await self._uow.transactions.update_status(
                        transaction.id, status=TransactionStatus.MEETUP_PLANNED, at=now
                    )

            await notify(
                self._uow,
                self._ids,
                self._clock,
                user_id=meetup.proposed_by,
                type="MEETUP_ACCEPTED" if cmd.accept else "MEETUP_DECLINED",
                title="SafeMeet accepted" if cmd.accept else "SafeMeet declined",
                body="Your meetup proposal was accepted."
                if cmd.accept
                else "Your meetup proposal was declined.",
                data={"conversationId": str(meetup.conversation_id), "meetupId": str(meetup.id)},
            )
            await self._uow.commit()
        return closed


@dataclass(frozen=True, slots=True)
class CreateMeetingVenueCommand:
    name: str
    address: str
    city: str
    latitude: float
    longitude: float
    area: str | None = None
    notes: str | None = None


class CreateMeetingVenue:
    """Staff-only: adds a public spot to the curated catalogue."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: CreateMeetingVenueCommand) -> MeetingVenue:
        async with self._uow:
            venue = await self._uow.meeting_venues.add(
                MeetingVenue(
                    id=self._ids.new(),
                    name=cmd.name,
                    address=cmd.address,
                    city=cmd.city,
                    area=cmd.area,
                    latitude=cmd.latitude,
                    longitude=cmd.longitude,
                    is_active=True,
                    notes=cmd.notes,
                    created_at=self._clock.now(),
                )
            )
            await self._uow.commit()
        return venue


class ListMeetingVenuesAdmin:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, limit: int = 50, offset: int = 0) -> list[MeetingVenue]:
        bounded = max(1, min(limit, 100))
        async with self._uow:
            return await self._uow.meeting_venues.list_all(limit=bounded, offset=max(0, offset))


class SetVenueActive:
    """Staff-only: deactivates (or reactivates) a venue rather than
    deleting it, so past meetups keep a valid reference to it."""

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, venue_id: UUID, *, is_active: bool) -> MeetingVenue:
        async with self._uow:
            venue = await self._uow.meeting_venues.get(venue_id)
            if venue is None:
                raise EntityNotFound("meeting venue", venue_id)
            updated = await self._uow.meeting_venues.set_active(venue_id, is_active=is_active)
            await self._uow.commit()
        return updated


__all__ = [
    "CreateMeetingVenue",
    "CreateMeetingVenueCommand",
    "ListMeetingVenuesAdmin",
    "ListMeetupsForConversation",
    "ListNearbyVenues",
    "ProposeMeetup",
    "ProposeMeetupCommand",
    "RespondToMeetup",
    "RespondToMeetupCommand",
    "SetVenueActive",
]
