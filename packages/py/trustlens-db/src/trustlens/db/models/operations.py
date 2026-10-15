"""Operations models. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from trustlens.core.domain import enums as e
from trustlens.db.base import (
    Base,
    uuid_fk,
    uuid_pk,
)
from .common import pg_enum


class AuditLogModel(Base):
    """Append-only. No update or delete path exists in the application."""

    __tablename__ = "audit_logs"

    id: Mapped[UUID] = uuid_pk()
    actor_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    actor_type: Mapped[e.ActorType] = mapped_column(
        pg_enum(e.ActorType, "actor_type"), nullable=False, default=e.ActorType.USER
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(60))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id", "occurred_at"),
        Index("ix_audit_logs_actor", "actor_id", "occurred_at"),
    )


class OutboxEvent(Base):
    """Transactional outbox.

    Domain events are written in the SAME transaction as the state change and
    relayed by a poller. Without this, "score updated but the webhook never
    fired" (or the reverse) is only a matter of time.
    """

    __tablename__ = "outbox_events"

    id: Mapped[UUID] = uuid_pk()
    aggregate_type: Mapped[str] = mapped_column(String(60), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_outbox_unpublished",
            "occurred_at",
            postgresql_where=text("published_at IS NULL"),
        ),
    )


class JobRunModel(Base):
    """ARQ state mirrored into Postgres.

    Redis can evict; a seller polling "is my verification done?" and an admin
    looking at dead letters both need durable answers.
    """

    __tablename__ = "job_runs"

    id: Mapped[UUID] = uuid_pk()
    job_name: Mapped[str] = mapped_column(String(80), nullable=False)
    job_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    status: Mapped[e.JobStatus] = mapped_column(
        pg_enum(e.JobStatus, "job_status"), nullable=False, default=e.JobStatus.QUEUED
    )
    related_entity_type: Mapped[str | None] = mapped_column(String(60))
    related_entity_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    attempt: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    error_type: Mapped[str | None] = mapped_column(String(80))
    request_id: Mapped[str | None] = mapped_column(String(60))
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_job_runs_status_queued", "status", "queued_at"),
        Index("ix_job_runs_entity", "related_entity_type", "related_entity_id"),
    )


class NotificationModel(Base):
    __tablename__ = "notifications"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="IN_APP")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_notifications_user_unread",
            "user_id",
            "created_at",
            postgresql_where=text("read_at IS NULL"),
        ),
    )
