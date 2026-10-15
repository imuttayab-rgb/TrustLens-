"""Verification models. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import date, datetime
from typing import Any
from uuid import UUID
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from trustlens.core.domain import enums as e
from trustlens.db.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    uuid_fk,
    uuid_pk,
)
from .common import pg_enum


class StoredFileModel(Base, TimestampMixin):
    """Every binary in one table, so the retention job has one place to look."""

    __tablename__ = "files"

    id: Mapped[UUID] = uuid_pk()
    owner_user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    purpose: Mapped[e.FilePurpose] = mapped_column(
        pg_enum(e.FilePurpose, "file_purpose"), nullable=False
    )
    storage_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="s3")
    bucket: Mapped[str] = mapped_column(String(80), nullable=False)
    object_key: Mapped[str] = mapped_column(String(400), nullable=False, unique=True)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    scan_status: Mapped[e.ScanStatus] = mapped_column(
        pg_enum(e.ScanStatus, "scan_status"), nullable=False, default=e.ScanStatus.PENDING
    )
    is_encrypted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Set for sensitive purposes; the purge job deletes the object and marks
    #: the row, leaving derived hashes and scores intact.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_files_owner_purpose", "owner_user_id", "purpose"),
        Index(
            "ix_files_expiry",
            "expires_at",
            postgresql_where=text("expires_at IS NOT NULL AND deleted_at IS NULL"),
        ),
    )


class IdentityDocumentModel(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "identity_documents"

    id: Mapped[UUID] = uuid_pk()
    seller_id: Mapped[UUID] = uuid_fk("seller_profiles.id")
    document_type: Mapped[e.DocumentType] = mapped_column(
        pg_enum(e.DocumentType, "document_type"), nullable=False
    )
    file_id: Mapped[UUID] = uuid_fk("files.id", ondelete="RESTRICT")
    status: Mapped[e.VerificationStatus] = mapped_column(
        pg_enum(e.VerificationStatus, "verification_status"), nullable=False
    )
    ocr_engine: Mapped[str | None] = mapped_column(String(40))
    ocr_engine_version: Mapped[str | None] = mapped_column(String(20))
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    ocr_raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    extracted_name: Mapped[str | None] = mapped_column(String(150))
    #: AES-256-GCM envelope-encrypted. Never returned by any API.
    extracted_cnic_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    #: HMAC blind index. This is what makes duplicate-CNIC detection possible
    #: in O(log n) while the number itself stays encrypted at rest - the single
    #: most valuable index in the schema for fraud detection.
    extracted_cnic_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    extracted_dob_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    extracted_expiry: Mapped[date | None] = mapped_column(Date)
    quality_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    rejection_reason: Mapped[str | None] = mapped_column(String(120))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_identity_documents_cnic_hash", "extracted_cnic_hash"),
        Index("ix_identity_documents_seller_type", "seller_id", "document_type"),
    )


class IdentityVerificationModel(Base, TimestampMixin):
    __tablename__ = "identity_verifications"

    id: Mapped[UUID] = uuid_pk()
    seller_id: Mapped[UUID] = uuid_fk("seller_profiles.id")
    front_document_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("identity_documents.id", ondelete="SET NULL")
    )
    back_document_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("identity_documents.id", ondelete="SET NULL")
    )
    selfie_document_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("identity_documents.id", ondelete="SET NULL")
    )
    face_match_engine: Mapped[str | None] = mapped_column(String(40))
    engine_version: Mapped[str | None] = mapped_column(String(20))
    face_similarity: Mapped[float | None] = mapped_column(Numeric(5, 4))
    face_distance: Mapped[float | None] = mapped_column(Numeric(5, 4))
    #: Stored alongside the similarity on purpose: without it, a past
    #: rejection becomes indefensible once the threshold is retuned.
    threshold_used: Mapped[float | None] = mapped_column(Numeric(5, 4))
    liveness_passed: Mapped[bool | None] = mapped_column(Boolean)
    name_match_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    decision: Mapped[e.VerificationStatus] = mapped_column(
        pg_enum(e.VerificationStatus, "verification_status"), nullable=False
    )
    decision_source: Mapped[str] = mapped_column(String(10), nullable=False, default="AUTO")
    decided_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decision_reason: Mapped[str | None] = mapped_column(Text)
    raw_result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_identity_verifications_seller_created", "seller_id", "created_at"),)


class PhoneNumberModel(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "phone_numbers"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    e164: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Hashed duplicate for reuse detection across accounts.
    phone_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    carrier_name: Mapped[str | None] = mapped_column(String(80))
    #: VOIP here is precisely the "throwaway phone number" fraud pattern.
    line_type: Mapped[e.LineType] = mapped_column(
        pg_enum(e.LineType, "line_type"), nullable=False, default=e.LineType.UNKNOWN
    )
    is_disposable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    country_code: Mapped[str | None] = mapped_column(String(2))
    lookup_raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    lookup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_phone_numbers_user_e164",
            "user_id",
            "e164",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_phone_numbers_hash", "phone_hash"),
    )


class EmailAddressModel(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "email_addresses"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    email_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    domain: Mapped[str | None] = mapped_column(String(255))
    is_disposable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mx_valid: Mapped[bool | None] = mapped_column(Boolean)
    domain_age_days: Mapped[int | None] = mapped_column(Integer)
    lookup_raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    lookup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_email_addresses_user_email",
            "user_id",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_email_addresses_hash", "email_hash"),
        Index("ix_email_addresses_domain", "domain"),
    )


class DeviceModel(Base, TimestampMixin):
    __tablename__ = "devices"

    id: Mapped[UUID] = uuid_pk()
    fingerprint_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    user_agent: Mapped[str | None] = mapped_column(Text)
    browser: Mapped[str | None] = mapped_column(String(60))
    browser_version: Mapped[str | None] = mapped_column(String(30))
    os: Mapped[str | None] = mapped_column(String(60))
    os_version: Mapped[str | None] = mapped_column(String(30))
    device_type: Mapped[str | None] = mapped_column(String(30))
    screen_resolution: Mapped[str | None] = mapped_column(String(20))
    timezone: Mapped[str | None] = mapped_column(String(60))
    languages: Mapped[str | None] = mapped_column(String(120))
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_emulator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserDevice(Base):
    """The many-to-many that detects "multiple accounts from one device"."""

    __tablename__ = "user_devices"

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    device_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    session_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_trusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_user_devices_device", "device_id"),)


class IpAddressModel(Base, TimestampMixin):
    """One row per distinct IP, so a metered lookup happens once."""

    __tablename__ = "ip_addresses"

    id: Mapped[UUID] = uuid_pk()
    ip: Mapped[str] = mapped_column(INET, nullable=False, unique=True)
    ip_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=4)
    asn: Mapped[int | None] = mapped_column(Integer)
    asn_org: Mapped[str | None] = mapped_column(String(150))
    country_code: Mapped[str | None] = mapped_column(String(2))
    region: Mapped[str | None] = mapped_column(String(80))
    city: Mapped[str | None] = mapped_column(String(80))
    is_vpn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_proxy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_tor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_datacenter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    abuse_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="offline")
    lookup_raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    looked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_ip_addresses_vpn", "is_vpn", postgresql_where=text("is_vpn")),)


class AccessEventModel(Base):
    """Append-only. Partitioned monthly by occurred_at (see database/sql/partitions)."""

    __tablename__ = "access_events"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    device_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    ip_address_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    ip: Mapped[str | None] = mapped_column(INET)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(60))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_access_events_user_occurred", "user_id", "occurred_at"),)
