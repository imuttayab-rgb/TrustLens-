"""Buyer<->seller messaging request/response models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from trustlens.core.application.use_cases.messaging import MAX_MESSAGE_CHARS
from trustlens_api.api.v1.schemas.common import Schema


class SendMessageRequest(Schema):
    body: str = Field(default="", max_length=MAX_MESSAGE_CHARS)
    client_id: UUID | None = None
    reply_to_id: UUID | None = None
    forward_id: UUID | None = None
    #: Exactly one of these two, enforced in the use case (not here) so the
    #: error carries the same field-level detail the rest of the API uses.
    conversation_id: UUID | None = None
    listing_id: UUID | None = None


class MessageResponse(Schema):
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    body: str
    created_at: datetime
    read_at: datetime | None = None


class ConversationResponse(Schema):
    id: UUID
    listing_id: UUID | None = None
    listing_title: str | None = None
    counterpart_name: str
    counterpart_user_id: UUID
    last_message_at: datetime
    last_message_preview: str | None = None
    unread_count: int = 0
    created_at: datetime
    muted: bool = False
    #: Only set when the counterpart is the seller side of this
    #: conversation - a buyer counterpart has no trust score to show.
    counterpart_seller_handle: str | None = None
    counterpart_risk_level: str | None = None
    counterpart_score: int | None = None


class SetMutedRequest(Schema):
    muted: bool


__all__ = ["ConversationResponse", "MessageResponse", "SendMessageRequest", "SetMutedRequest"]
