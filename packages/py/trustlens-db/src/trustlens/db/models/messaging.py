"""Messaging models. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from trustlens.db.base import (
    Base,
    uuid_fk,
    uuid_pk,
)


class ConversationModel(Base):
    """A buyer<->seller thread, optionally anchored to the listing that
    started it. `last_message_at` is denormalised for one-query inbox
    sorting - the alternative is a correlated subquery per row."""

    __tablename__ = "conversations"

    id: Mapped[UUID] = uuid_pk()
    listing_id: Mapped[UUID | None] = uuid_fk("listings.id", ondelete="SET NULL", nullable=True)
    seller_id: Mapped[UUID] = uuid_fk("seller_profiles.id")
    buyer_id: Mapped[UUID] = uuid_fk("users.id")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    #: Captured from the listing at creation time (SOC-01) - the FK above
    #: is live and SETs NULL on delete, so this is what keeps a thread's
    #: displayed subject stable even if the listing is later edited or removed.
    listing_title_snapshot: Mapped[str | None] = mapped_column(String(200))
    listing_price_snapshot: Mapped[float | None] = mapped_column(Numeric(14, 2))
    listing_currency_snapshot: Mapped[str | None] = mapped_column(String(3))
    muted_by_buyer: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    muted_by_seller: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        Index("ix_conversations_buyer", "buyer_id", "last_message_at"),
        Index("ix_conversations_seller", "seller_id", "last_message_at"),
        Index(
            "uq_conversations_buyer_seller_listing",
            "buyer_id",
            "seller_id",
            "listing_id",
            unique=True,
        ),
    )


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = uuid_pk()
    conversation_id: Mapped[UUID] = uuid_fk("conversations.id")
    sender_id: Mapped[UUID] = uuid_fk("users.id")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    #: Set when the OTHER participant views the thread - never by the sender
    #: reading their own message.
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    edited_body: Mapped[str | None] = mapped_column(Text)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_for_everyone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(10), nullable=False, server_default="text")
    client_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    reply_to_id: Mapped[UUID | None] = mapped_column(ForeignKey("messages.id"))
    forwarded_from_id: Mapped[UUID | None] = mapped_column(ForeignKey("messages.id"))
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        Index("uq_messages_sender_client", "sender_id", "client_id", unique=True),
    )


class ConversationPreferenceModel(Base):
    """Private bookmark for one authenticated conversation participant."""

    __tablename__ = "conversation_preferences"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversations.id"), primary_key=True)
    important: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


class ChatLifecycleModel(Base):
    __tablename__ = "chat_lifecycle"
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    inactive_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class ChatClearModel(Base):
    __tablename__ = "chat_clears"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversations.id"), primary_key=True)
    cleared_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    previous_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    undo_token: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    undo_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChatVoiceModel(Base):
    __tablename__ = "chat_voices"
    message_id: Mapped[UUID] = mapped_column(ForeignKey("messages.id"), primary_key=True)
    bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    original_key: Mapped[str] = mapped_column(Text, nullable=False)
    playback_key: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    waveform: Mapped[list] = mapped_column(JSONB, nullable=False)


class ChatVersionModel(Base):
    __tablename__ = "chat_versions"
    id: Mapped[UUID] = uuid_pk()
    message_id: Mapped[UUID] = uuid_fk("messages.id")
    actor_id: Mapped[UUID] = uuid_fk("users.id")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_chat_versions_message", "message_id", "created_at"),)


class ChatAuditModel(Base):
    __tablename__ = "chat_audit"
    id: Mapped[UUID] = uuid_pk()
    actor_id: Mapped[UUID] = uuid_fk("users.id")
    conversation_id: Mapped[UUID] = uuid_fk("conversations.id")
    message_id: Mapped[UUID | None] = uuid_fk("messages.id", nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_chat_audit_conversation", "conversation_id", "created_at"),)


class ChatCaseModel(Base):
    __tablename__ = "chat_cases"
    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id"), primary_key=True)
    conversation_id: Mapped[UUID] = uuid_fk("conversations.id")
    message_id: Mapped[UUID | None] = uuid_fk("messages.id", nullable=True)
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
