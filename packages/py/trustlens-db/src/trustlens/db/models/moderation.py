"""Moderation models. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from trustlens.core.domain import enums as e
from trustlens.db.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    uuid_fk,
    uuid_pk,
)
from .common import pg_enum


class ReportModel(Base):
    """A report against a listing, seller, message, or something else
    (MOD-01). `target_id` is untyped beyond a UUID - `target_type` names
    what it points to, the same pattern `ReviewCaseModel.related_entity_*`
    already uses."""

    __tablename__ = "reports"

    id: Mapped[UUID] = uuid_pk()
    reporter_id: Mapped[UUID] = uuid_fk("users.id")
    target_type: Mapped[e.ReportTargetType] = mapped_column(
        pg_enum(e.ReportTargetType, "report_target_type"), nullable=False
    )
    target_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    category: Mapped[e.ReportCategory] = mapped_column(
        pg_enum(e.ReportCategory, "report_category"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[e.ReportStatus] = mapped_column(
        pg_enum(e.ReportStatus, "report_status"), nullable=False, default=e.ReportStatus.OPEN
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    resolution_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_reports_queue", "status", "created_at"),
        Index("ix_reports_reporter", "reporter_id", "created_at"),
        Index("ix_reports_target", "target_type", "target_id"),
    )


class BlockModel(Base):
    """One user refusing further contact from another. Directional -
    `blocker_id` blocked `blocked_id`; messaging enforcement checks both
    directions rather than relying on symmetry here."""

    __tablename__ = "blocks"

    id: Mapped[UUID] = uuid_pk()
    blocker_id: Mapped[UUID] = uuid_fk("users.id")
    blocked_id: Mapped[UUID] = uuid_fk("users.id")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("uq_blocks_blocker_blocked", "blocker_id", "blocked_id", unique=True),)


class AppealModel(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "appeals"

    id: Mapped[UUID] = uuid_pk()
    seller_id: Mapped[UUID] = uuid_fk("seller_profiles.id")
    #: The specific computation under appeal. Appealing "my score" is
    #: meaningless once it changes; appealing THIS one is reviewable.
    trust_score_id: Mapped[UUID] = uuid_fk("trust_scores.id", ondelete="RESTRICT")
    submitted_by: Mapped[UUID] = uuid_fk("users.id", ondelete="RESTRICT")
    reason_category: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[e.AppealStatus] = mapped_column(
        pg_enum(e.AppealStatus, "appeal_status"), nullable=False, default=e.AppealStatus.OPEN
    )
    assigned_to: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[str | None] = mapped_column(String(20))
    resulting_score_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    messages: Mapped[list[AppealMessageModel]] = relationship(
        back_populates="appeal", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_appeals_status_submitted", "status", "submitted_at"),
        Index(
            "ix_appeals_assigned_open",
            "assigned_to",
            postgresql_where=text("status IN ('OPEN','UNDER_REVIEW','NEEDS_INFO')"),
        ),
        Index("ix_appeals_seller", "seller_id"),
    )


class AppealMessageModel(Base):
    __tablename__ = "appeal_messages"

    id: Mapped[UUID] = uuid_pk()
    appeal_id: Mapped[UUID] = uuid_fk("appeals.id")
    sender_id: Mapped[UUID] = uuid_fk("users.id", ondelete="RESTRICT")
    sender_role: Mapped[e.UserRole] = mapped_column(
        pg_enum(e.UserRole, "user_role"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[dict[str, Any]] = mapped_column(JSONB, default=list)
    #: Reviewer notes the seller must not see.
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    appeal: Mapped[AppealModel] = relationship(back_populates="messages")


class ReviewCaseModel(Base, TimestampMixin):
    """The admin work queue.

    Separate from appeals because most review work is system-initiated (a
    device cluster tripped a rule), not seller-initiated.
    """

    __tablename__ = "review_cases"

    id: Mapped[UUID] = uuid_pk()
    seller_id: Mapped[UUID] = uuid_fk("seller_profiles.id")
    case_type: Mapped[e.ReviewCaseType] = mapped_column(
        pg_enum(e.ReviewCaseType, "review_case_type"), nullable=False
    )
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=5)
    status: Mapped[e.ReviewStatus] = mapped_column(
        pg_enum(e.ReviewStatus, "review_status"), nullable=False, default=e.ReviewStatus.QUEUED
    )
    trigger_reason: Mapped[str | None] = mapped_column(String(120))
    related_entity_type: Mapped[str | None] = mapped_column(String(60))
    related_entity_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    assigned_to: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision: Mapped[str | None] = mapped_column(String(20))
    decision_note: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))

    __table_args__ = (
        Index("ix_review_cases_queue", "status", "priority", "created_at"),
        Index("ix_review_cases_seller", "seller_id"),
    )
