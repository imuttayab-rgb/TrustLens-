"""Buyer<->seller messaging endpoints.

Everything lives under /me/conversations: any signed-in user (buyer or
seller) may hold conversations, the same way /me/favorites asks nothing
about role. Polled by the frontend, not pushed - see the use-case module
for why.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, status

from trustlens.core.application.use_cases.messaging import (
    ListConversations,
    ListConversationsQuery,
    ListMessages,
    ListMessagesQuery,
    SendMessage,
    SendMessageCommand,
    SetConversationMuted,
    SetConversationMutedCommand,
)
from trustlens.core.domain.errors import RateLimitExceeded
from trustlens.shared.logging import get_logger
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.common import PageMeta, envelope
from trustlens_api.api.v1.schemas.messaging import (
    ConversationResponse,
    MessageResponse,
    SendMessageRequest,
    SetMutedRequest,
)

log = get_logger(__name__)

router = APIRouter(tags=["Messaging"])


async def _throttle_send(container: ContainerDep, actor: ActorDep) -> None:
    """Per-sender limit against message spam/flooding (SOC-01) - separate
    from the anonymous per-IP limiters elsewhere, since the attacker here is
    a signed-in account, not an anonymous scraper. Fails open, same policy
    as every other rate limit in this codebase: a Redis blip must not stop
    real conversations from sending."""
    limits = container.settings.rate_limit
    if not limits.enabled or actor.user_id is None:
        return
    try:
        allowed, _remaining, retry_after = await container.rate_limiter.hit(
            f"message:send:{actor.user_id}",
            limit=limits.message_send_per_minute,
            window_seconds=60,
        )
    except Exception:
        log.warning("message_send_throttle_unavailable_failing_open", user_id=str(actor.user_id))
        return
    if not allowed:
        raise RateLimitExceeded(
            "You're sending messages too quickly. Slow down a moment.",
            retry_after=retry_after,
        )


def _to_message_response(message: Any) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        body=message.body,
        created_at=message.created_at,
        read_at=message.read_at,
    )


def _to_conversation_response(summary: Any) -> ConversationResponse:
    c = summary.conversation
    return ConversationResponse(
        id=c.id,
        listing_id=c.listing_id,
        listing_title=summary.listing_title,
        counterpart_name=summary.counterpart_name,
        counterpart_user_id=summary.counterpart_user_id,
        last_message_at=c.last_message_at,
        last_message_preview=summary.last_message_preview,
        unread_count=summary.unread_count,
        created_at=c.created_at,
        muted=summary.muted,
    )


@router.post(
    "/me/conversations",
    status_code=status.HTTP_201_CREATED,
    summary="Send a message, starting a new conversation or replying to one",
)
async def send_message(
    body: SendMessageRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    await _throttle_send(container, actor)
    result = await SendMessage(uow=uow, clock=container.clock, ids=container.ids).execute(
        SendMessageCommand(
            sender_id=actor.user_id,
            body=body.body,
            conversation_id=body.conversation_id,
            listing_id=body.listing_id,
        )
    )
    return envelope(
        {
            "conversationId": str(result.conversation_id),
            "message": _to_message_response(result.message).model_dump(by_alias=True),
        },
        request_id=meta.request_id,
    )


@router.get("/me/conversations", summary="List my conversations")
async def list_conversations(
    actor: ActorDep,
    uow: UowDep,
    meta: MetaDep,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    assert actor.user_id is not None
    page = await ListConversations(uow=uow).execute(
        ListConversationsQuery(user_id=actor.user_id, limit=limit, offset=offset)
    )
    return envelope(
        [_to_conversation_response(item).model_dump(by_alias=True) for item in page.items],
        request_id=meta.request_id,
        pagination=PageMeta.build(
            page=(page.offset // page.limit) + 1, per_page=page.limit, total=page.total
        ),
    )


@router.get(
    "/me/conversations/{conversation_id}/messages",
    summary="Read a conversation (marks the other party's messages as read)",
)
async def list_messages(
    conversation_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    assert actor.user_id is not None
    page = await ListMessages(uow=uow, clock=container.clock).execute(
        ListMessagesQuery(
            conversation_id=conversation_id, reader_id=actor.user_id, limit=limit, offset=offset
        )
    )
    return envelope(
        [_to_message_response(item).model_dump(by_alias=True) for item in page.items],
        request_id=meta.request_id,
    )


@router.put(
    "/me/conversations/{conversation_id}/muted",
    summary="Mute or unmute a conversation",
    description=(
        "A lighter tool than blocking (MOD-01) - stops this thread from "
        "standing out in the inbox without cutting the other party off."
    ),
)
async def set_conversation_muted(
    conversation_id: UUID,
    body: SetMutedRequest,
    actor: ActorDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    await SetConversationMuted(uow=uow).execute(
        SetConversationMutedCommand(
            conversation_id=conversation_id, user_id=actor.user_id, muted=body.muted
        )
    )
    return envelope({"muted": body.muted}, request_id=meta.request_id)


__all__ = ["router"]
