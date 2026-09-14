"""Buyer<->seller messaging (feature F5c).

Polled, not websocket-backed - a websocket server is real infrastructure
(sticky sessions, a separate deploy target, a reconnect story), and this
product already has a polling pattern for exactly this shape of problem
(job status). A 5-10s poll on an open conversation is indistinguishable
from real-time to a person typing a reply, and it costs nothing new to run.

A conversation is created lazily, alongside its first message, anchored to
the listing that started it - there is no "start an empty conversation"
action, because an empty thread is not a useful thing to list in an inbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from trustlens.core.application.notifications import notify
from trustlens.core.domain.entities import Conversation, ConversationSummary, Message
from trustlens.core.domain.errors import EntityNotFound, PermissionDenied, ValidationError
from trustlens.core.domain.ports import Clock, IdGenerator, UnitOfWork

MAX_MESSAGE_CHARS = 4000


def _clean_body(body: str) -> str:
    text = body.strip()
    if not text:
        raise ValidationError("A message cannot be empty.", field="body")
    if len(text) > MAX_MESSAGE_CHARS:
        raise ValidationError(f"Keep messages under {MAX_MESSAGE_CHARS} characters.", field="body")
    return text


@dataclass(frozen=True, slots=True)
class SendMessageCommand:
    sender_id: UUID
    body: str
    #: Reply into an existing thread.
    conversation_id: UUID | None = None
    #: Start a new thread anchored to this listing - required when
    #: conversation_id is not given.
    listing_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class SendMessageResult:
    conversation_id: UUID
    message: Message


class SendMessage:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: SendMessageCommand) -> SendMessageResult:
        body = _clean_body(cmd.body)
        now = self._clock.now()

        async with self._uow:
            conversation = await self._resolve_conversation(cmd, now)

            message = await self._uow.messaging.add_message(
                Message(
                    id=self._ids.new(),
                    conversation_id=conversation.id,
                    sender_id=cmd.sender_id,
                    body=body,
                    created_at=now,
                )
            )
            await self._uow.messaging.touch_conversation(conversation.id, at=now)
            await self._notify_recipient(conversation, cmd.sender_id, body)
            await self._uow.commit()

        return SendMessageResult(conversation_id=conversation.id, message=message)

    async def _notify_recipient(
        self, conversation: Conversation, sender_id: UUID, body: str
    ) -> None:
        participants = await self._uow.messaging.get_participants(conversation.id)
        if participants is None:
            return
        buyer_user_id, seller_user_id = participants
        recipient_id = seller_user_id if sender_id == buyer_user_id else buyer_user_id
        # A conversation this side has muted (SOC-01) should not also ping
        # their notification center - that is the whole point of muting it.
        muted = (
            conversation.muted_by_seller
            if recipient_id == seller_user_id
            else conversation.muted_by_buyer
        )
        if muted:
            return
        await notify(
            self._uow,
            self._ids,
            self._clock,
            user_id=recipient_id,
            type="MESSAGE_RECEIVED",
            title="New message",
            body=body[:140],
            data={"conversationId": str(conversation.id)},
        )

    async def _resolve_conversation(self, cmd: SendMessageCommand, now: datetime) -> Conversation:
        if cmd.conversation_id is not None:
            conversation = await self._uow.messaging.get_conversation(cmd.conversation_id)
            if conversation is None:
                raise EntityNotFound("conversation", cmd.conversation_id)
            participants = await self._uow.messaging.get_participants(conversation.id)
            if participants is None or cmd.sender_id not in participants:
                raise PermissionDenied("This conversation belongs to someone else.")
            other = next(p for p in participants if p != cmd.sender_id)
            if await self._uow.blocks.is_blocked_either_way(cmd.sender_id, other):
                # A blocked user must not be able to route around it by
                # replying into a thread that predates the block - checked
                # both directions, since either party may have blocked.
                raise PermissionDenied("You cannot message this user.")
            return conversation

        if cmd.listing_id is None:
            raise ValidationError(
                "Provide either a conversation to reply to or a listing to message about.",
                field="listingId",
            )

        listing = await self._uow.listings.get(cmd.listing_id)
        if listing is None:
            raise EntityNotFound("listing", cmd.listing_id)

        seller = await self._uow.sellers.get(listing.seller_id)
        if seller is not None and seller.user_id == cmd.sender_id:
            raise ValidationError("You cannot message yourself about your own listing.")
        if seller is not None and await self._uow.blocks.is_blocked_either_way(
            cmd.sender_id, seller.user_id
        ):
            raise PermissionDenied("You cannot message this user.")

        existing = await self._uow.messaging.find_conversation(
            buyer_id=cmd.sender_id, seller_id=listing.seller_id, listing_id=listing.id
        )
        if existing is not None:
            return existing

        return await self._uow.messaging.create_conversation(
            Conversation(
                id=self._ids.new(),
                seller_id=listing.seller_id,
                buyer_id=cmd.sender_id,
                created_at=now,
                last_message_at=now,
                listing_id=listing.id,
                listing_title=listing.title,
                listing_price=listing.price.amount if listing.price is not None else None,
                listing_currency=listing.price.currency if listing.price is not None else None,
            )
        )


@dataclass(frozen=True, slots=True)
class ListConversationsQuery:
    user_id: UUID
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class ConversationPage:
    items: tuple[ConversationSummary, ...]
    total: int
    limit: int
    offset: int


class ListConversations:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, query: ListConversationsQuery) -> ConversationPage:
        limit = max(1, min(query.limit, 50))
        offset = max(0, query.offset)
        async with self._uow:
            items = await self._uow.messaging.list_conversations_for_user(
                query.user_id, limit=limit, offset=offset
            )
            total = await self._uow.messaging.count_conversations_for_user(query.user_id)
        return ConversationPage(items=tuple(items), total=total, limit=limit, offset=offset)


@dataclass(frozen=True, slots=True)
class ListMessagesQuery:
    conversation_id: UUID
    reader_id: UUID
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class MessagePage:
    items: tuple[Message, ...]
    total: int
    limit: int
    offset: int


class ListMessages:
    """Reading a thread also marks the other party's messages read - the
    same "opening it is acknowledging it" behaviour as any inbox."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, query: ListMessagesQuery) -> MessagePage:
        limit = max(1, min(query.limit, 100))
        offset = max(0, query.offset)

        async with self._uow:
            participants = await self._uow.messaging.get_participants(query.conversation_id)
            if participants is None:
                raise EntityNotFound("conversation", query.conversation_id)
            if query.reader_id not in participants:
                raise PermissionDenied("This conversation belongs to someone else.")

            await self._uow.messaging.mark_read(
                query.conversation_id, reader_id=query.reader_id, at=self._clock.now()
            )
            items = await self._uow.messaging.list_messages(
                query.conversation_id, limit=limit, offset=offset
            )
            await self._uow.commit()

        return MessagePage(items=tuple(items), total=len(items), limit=limit, offset=offset)


@dataclass(frozen=True, slots=True)
class SetConversationMutedCommand:
    conversation_id: UUID
    user_id: UUID
    muted: bool


class SetConversationMuted:
    """Mutes/unmutes one side of a thread (SOC-01) - block already exists for
    "stop this person entirely"; this is the lighter "stop pestering me
    about it" case, e.g. a haggling buyer who won't take no for an answer."""

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, cmd: SetConversationMutedCommand) -> None:
        async with self._uow:
            participants = await self._uow.messaging.get_participants(cmd.conversation_id)
            if participants is None:
                raise EntityNotFound("conversation", cmd.conversation_id)
            if cmd.user_id not in participants:
                raise PermissionDenied("This conversation belongs to someone else.")
            await self._uow.messaging.set_muted(
                cmd.conversation_id, user_id=cmd.user_id, muted=cmd.muted
            )
            await self._uow.commit()


__all__ = [
    "MAX_MESSAGE_CHARS",
    "ConversationPage",
    "ListConversations",
    "ListConversationsQuery",
    "ListMessages",
    "ListMessagesQuery",
    "MessagePage",
    "SendMessage",
    "SendMessageCommand",
    "SendMessageResult",
    "SetConversationMuted",
    "SetConversationMutedCommand",
]
