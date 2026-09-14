"""SafeMeet endpoints (feature SAFE-01).

Venue suggestions and meetup proposals live under /conversations and
/meetups, the same shape OFF-01's offers use - a meetup is conversation
-scoped the same way an offer is. Venue browsing (GET /meeting-venues) is
open to any signed-in user; curating the catalogue is admin.py's job
(POST/PATCH require safemeet:manage).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query

from trustlens.core.application.use_cases.safemeet import (
    ListMeetupsForConversation,
    ListNearbyVenues,
    ProposeMeetup,
    ProposeMeetupCommand,
    RespondToMeetup,
    RespondToMeetupCommand,
)
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.common import envelope
from trustlens_api.api.v1.schemas.safemeet import (
    MeetingVenueResponse,
    MeetupResponse,
    ProposeMeetupRequest,
    RespondToMeetupRequest,
)

router = APIRouter(tags=["SafeMeet"])


def _to_venue_response(venue: Any) -> MeetingVenueResponse:
    return MeetingVenueResponse(
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


def _to_meetup_response(meetup: Any) -> MeetupResponse:
    return MeetupResponse(
        id=meetup.id,
        conversation_id=meetup.conversation_id,
        listing_id=meetup.listing_id,
        buyer_id=meetup.buyer_id,
        seller_id=meetup.seller_id,
        proposed_by=meetup.proposed_by,
        venue_id=meetup.venue_id,
        proposed_time=meetup.proposed_time,
        status=meetup.status.value,
        created_at=meetup.created_at,
        message=meetup.message,
        responded_at=meetup.responded_at,
    )


@router.get("/meeting-venues", summary="Platform-suggested public meetup spots near a city")
async def list_nearby_venues(
    actor: ActorDep,
    uow: UowDep,
    meta: MetaDep,
    city: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=5, ge=1, le=10),
) -> dict[str, Any]:
    assert actor.user_id is not None
    venues = await ListNearbyVenues(uow=uow).execute(city=city, limit=limit)
    return envelope(
        [_to_venue_response(v).model_dump(by_alias=True) for v in venues],
        request_id=meta.request_id,
    )


@router.post("/conversations/{conversation_id}/meetups", summary="Propose a SafeMeet")
async def propose_meetup(
    conversation_id: UUID,
    body: ProposeMeetupRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    meetup = await ProposeMeetup(uow=uow, clock=container.clock, ids=container.ids).execute(
        ProposeMeetupCommand(
            conversation_id=conversation_id,
            proposed_by=actor.user_id,
            venue_id=body.venue_id,
            proposed_time=body.proposed_time,
            message=body.message,
        )
    )
    return envelope(
        _to_meetup_response(meetup).model_dump(by_alias=True), request_id=meta.request_id
    )


@router.get(
    "/conversations/{conversation_id}/meetups",
    summary="The SafeMeet proposal history for one conversation",
)
async def list_meetups(
    conversation_id: UUID, actor: ActorDep, uow: UowDep, meta: MetaDep
) -> dict[str, Any]:
    assert actor.user_id is not None
    meetups = await ListMeetupsForConversation(uow=uow).execute(conversation_id, actor.user_id)
    return envelope(
        [_to_meetup_response(m).model_dump(by_alias=True) for m in meetups],
        request_id=meta.request_id,
    )


@router.post("/meetups/{meetup_id}/respond", summary="Accept or decline a proposed SafeMeet")
async def respond_to_meetup(
    meetup_id: UUID,
    body: RespondToMeetupRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    meetup = await RespondToMeetup(uow=uow, clock=container.clock, ids=container.ids).execute(
        RespondToMeetupCommand(meetup_id=meetup_id, responder_id=actor.user_id, accept=body.accept)
    )
    return envelope(
        _to_meetup_response(meetup).model_dump(by_alias=True), request_id=meta.request_id
    )


__all__ = ["router"]
