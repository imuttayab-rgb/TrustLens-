"""SQLAlchemy declarative base, naming conventions and shared column mixins."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, MetaData, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

#: Explicit constraint naming, so Alembic can autogenerate reliable
#: down-migrations. Without this, dropping an unnamed constraint later
#: requires hand-written SQL and a guess at what Postgres called it.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    type_annotation_map = {
        dict[str, Any]: JSONB,
        list[str]: JSONB,
    }

    def __repr__(self) -> str:
        identifier = getattr(self, "id", None)
        return f"<{type(self).__name__} {identifier}>"


def uuid_pk() -> Mapped[UUID]:
    """Primary key column. Values are UUIDv7, generated in the application.

    Generated app-side rather than by the database so a use case can build a
    complete entity graph before flushing, and so tests can use a deterministic
    id sequence.
    """
    return mapped_column(PgUUID(as_uuid=True), primary_key=True)


def uuid_fk(target: str, *, ondelete: str = "CASCADE", nullable: bool = False) -> Mapped[UUID]:
    return mapped_column(
        PgUUID(as_uuid=True), ForeignKey(target, ondelete=ondelete), nullable=nullable
    )


class TimestampMixin:
    """created_at / updated_at, always timezone-aware.

    TIMESTAMPTZ, never TIMESTAMP: a naive timestamp silently adopts the
    server's timezone and becomes unusable the moment a deployment moves.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Soft delete for business entities.

    Deliberately NOT applied to trust_scores, trust_score_signals, audit_logs,
    access_events or api_request_logs: those are the evidence trail, and
    deleting them destroys the ability to defend a score in an appeal.

    Uniqueness under soft delete uses partial indexes
    (`... WHERE deleted_at IS NULL`) so a deleted account frees its email for
    re-registration without a unique violation.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class AuditMixin:
    created_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    updated_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)


class VersionMixin:
    """Optimistic locking for rows two admins might edit at once.

    SQLAlchemy raises StaleDataError on a version mismatch, which the API
    surfaces as a 409 with the current value rather than silently applying a
    lost update.
    """

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__ = {"version_id_col": None}  # set per-model where needed


__all__ = [
    "NAMING_CONVENTION",
    "AuditMixin",
    "Base",
    "SoftDeleteMixin",
    "TimestampMixin",
    "VersionMixin",
    "uuid_fk",
    "uuid_pk",
]
