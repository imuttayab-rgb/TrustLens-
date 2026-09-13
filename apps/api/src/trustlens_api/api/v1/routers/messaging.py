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
)
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.common import PageMeta, envelope
from trustlens_api.api.v1.schemas.messaging import (
    ConversationResponse,
    MessageResponse,
    SendMessageRequest,
)

router = APIRouter(tags=["Messaging"])


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


__all__ = ["router"]
