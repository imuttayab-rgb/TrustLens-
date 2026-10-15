"""Partners models. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from trustlens.core.domain import enums as e
from trustlens.db.base import (
    AuditMixin,
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    uuid_fk,
    uuid_pk,
)
from .common import pg_enum


class ApiClientModel(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "api_clients"

    id: Mapped[UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    marketplace_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("marketplaces.id", ondelete="SET NULL")
    )
    contact_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    rate_limit_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    monthly_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=10_000)
    allowed_origins: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    allowed_ips: Mapped[list[str]] = mapped_column(ARRAY(INET), default=list)
    webhook_secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)

    keys: Mapped[list[ApiKeyModel]] = relationship(
        back_populates="client", cascade="all, delete-orphan", lazy="selectin"
    )


class ApiKeyModel(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = uuid_pk()
    api_client_id: Mapped[UUID] = uuid_fk("api_clients.id")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    #: Stored in the clear and indexed so lookup is one equality match; the
    #: secret half is argon2-hashed and compared in constant time.
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    key_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    status: Mapped[e.ApiKeyStatus] = mapped_column(
        pg_enum(e.ApiKeyStatus, "api_key_status"), nullable=False, default=e.ApiKeyStatus.ACTIVE
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_ip: Mapped[str | None] = mapped_column(INET)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))

    client: Mapped[ApiClientModel] = relationship(back_populates="keys")

    __table_args__ = (
        Index(
            "ix_api_keys_client_active",
            "api_client_id",
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )


class ApiRequestLog(Base):
    """Append-only, partitioned monthly. Powers quota, abuse detection, usage."""

    __tablename__ = "api_request_logs"

    id: Mapped[UUID] = uuid_pk()
    api_key_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    api_client_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(60))
    seller_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    error_code: Mapped[str | None] = mapped_column(String(60))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_api_request_logs_key_occurred", "api_key_id", "occurred_at"),)


class WebhookEndpointModel(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "webhook_endpoints"

    id: Mapped[UUID] = uuid_pk()
    api_client_id: Mapped[UUID] = uuid_fk("api_clients.id")
    url: Mapped[str] = mapped_column(Text, nullable=False)
    events: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class WebhookDeliveryModel(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[UUID] = uuid_pk()
    webhook_endpoint_id: Mapped[UUID] = uuid_fk("webhook_endpoints.id")
    event_type: Mapped[e.WebhookEvent] = mapped_column(
        pg_enum(e.WebhookEvent, "webhook_event"), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[e.DeliveryStatus] = mapped_column(
        pg_enum(e.DeliveryStatus, "delivery_status"),
        nullable=False,
        default=e.DeliveryStatus.PENDING,
    )
    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response_status: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
