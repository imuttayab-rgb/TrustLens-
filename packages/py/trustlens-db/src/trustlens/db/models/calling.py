"""Calling models. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from trustlens.db.base import (
    Base,
    uuid_fk,
    uuid_pk,
)


class ChatCallModel(Base):
    __tablename__ = "chat_calls"
    id: Mapped[UUID] = uuid_pk()
    conversation_id: Mapped[UUID] = uuid_fk("conversations.id")
    caller_id: Mapped[UUID] = uuid_fk("users.id")
    callee_id: Mapped[UUID] = uuid_fk("users.id")
    caller_device: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    callee_device: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    state: Mapped[str] = mapped_column(String(15), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(30))
    caller_muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    callee_muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    caller_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    callee_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    caller_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    callee_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    __table_args__ = (
        Index("ix_chat_calls_caller_state", "caller_id", "state"),
        Index("ix_chat_calls_callee_state", "callee_id", "state"),
        Index("ix_chat_calls_history", "conversation_id", "created_at"),
        CheckConstraint("caller_id <> callee_id", name="call_distinct_participants"),
        CheckConstraint(
            "state IN ('calling','ringing','connecting','active','ended')", name="call_state"
        ),
    )


class ChatCallRuntimeModel(Base):
    __tablename__ = "chat_call_runtime"
    call_id: Mapped[UUID] = mapped_column(ForeignKey("chat_calls.id"), primary_key=True)
    push_attempted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    room_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    caller_health: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    callee_health: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ChatPushSubscriptionModel(Base):
    __tablename__ = "chat_push_subscriptions"
    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    endpoint_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    encrypted_subscription: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_chat_push_user", "user_id", "enabled"),)
