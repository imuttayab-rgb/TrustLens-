"""Buyer<->seller messaging entities.

A conversation belongs to a buyer (any signed-in user) and a seller,
optionally anchored to the listing that started it. Polled, not
websocket-backed - see the messaging use cases for the reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Message:
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    body: str
    created_at: datetime
    read_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Conversation:
    id: UUID
    seller_id: UUID
    buyer_id: UUID
    created_at: datetime
    last_message_at: datetime
    listing_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    """A conversation plus what an inbox screen needs to render one row,
    without a second round trip per conversation."""

    conversation: Conversation
    #: The other party's display name, from the buyer's or seller's point
    #: of view depending on which one the current user is.
    counterpart_name: str
    listing_title: str | None
    last_message_preview: str | None
    unread_count: int


__all__ = ["Conversation", "ConversationSummary", "Message"]
