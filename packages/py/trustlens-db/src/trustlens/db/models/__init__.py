"""SQLAlchemy models - the full TrustLens schema.

Every table from docs/05. Grouped by aggregate rather than split across many
files, because the schema is read as a whole far more often than it is edited
in one place.

Two invariants here are enforced by the DATABASE, not by application code,
because they are the ones that must never be violated:

* `uq_trust_scores_current` - a seller has at most one current score.
* `ck_trust_scores_override_reason` - an overridden score always carries a
  written reason.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
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


def pg_enum(enum_cls: type, name: str) -> SAEnum:
    """Native PostgreSQL ENUM.

    `values_callable` stores the enum *values*, not the Python member names,
    so the database column reads the same as the API payload.
    """
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda x: [member.value for member in x],
        native_enum=True,
        create_type=False,
    )


# ═══════════════════════════════════════════════════════════════════
#  Identity & access
# ═══════════════════════════════════════════════════════════════════


class User(Base, TimestampMixin, SoftDeleteMixin):
    """One account table for every persona.

    Separate buyers/sellers/admins tables would mean writing auth three times,
    and a person can legitimately be both a buyer and a seller.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = uuid_pk()
    # CITEXT so 'A@x.com' and 'a@x.com' are the same account.
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_hash: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[e.AccountStatus] = mapped_column(
        pg_enum(e.AccountStatus, "account_status"), nullable=False, default=e.AccountStatus.PENDING
    )
    #: Denormalised for fast routing; user_roles remains authoritative.
    primary_role: Mapped[e.UserRole] = mapped_column(
        pg_enum(e.UserRole, "user_role"), nullable=False, default=e.UserRole.BUYER
    )
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mfa_secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    failed_login_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    roles: Mapped[list[UserRoleLink]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        # Partial unique: a soft-deleted account frees its email for
        # re-registration without a constraint violation.
        Index("uq_users_email", "email", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_users_status", "status"),
        Index("ix_users_created_at", "created_at"),
        Index(
            "ix_users_full_name_trgm",
            "full_name",
            postgresql_using="gin",
            postgresql_ops={"full_name": "gin_trgm_ops"},
        ),
    )


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[UUID] = uuid_pk()
    key: Mapped[e.UserRole] = mapped_column(
        pg_enum(e.UserRole, "user_role"), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    permissions: Mapped[list[RolePermission]] = relationship(
        back_populates="role", cascade="all, delete-orphan", lazy="selectin"
    )


class Permission(Base, TimestampMixin):
    """`resource:action[:scope]` - see docs/09 for the full matrix."""

    __tablename__ = "permissions"

    id: Mapped[UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    resource: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )

    role: Mapped[Role] = relationship(back_populates="permissions")
    permission: Mapped[Permission] = relationship(lazy="joined")


class UserRoleLink(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    granted_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    #: Temporary elevation without a schema change.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship(lazy="joined")


class RefreshToken(Base):
    """Rotating refresh tokens with family-based reuse detection (ADR-0006)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    #: Only the hash is stored - the raw token exists solely in the cookie.
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    #: Rotation family. Replaying a rotated token revokes every descendant.
    family_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("refresh_tokens.id", ondelete="SET NULL")
    )
    device_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL")
    )
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_refresh_tokens_user_active",
            "user_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index("ix_refresh_tokens_family_id", "family_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )


class VerificationTokenModel(Base):
    """Email verification, password reset and email change.

    One table for three flows because they are structurally identical - three
    tables would be three copies of the same expiry/consumption bug surface.
    """

    __tablename__ = "verification_tokens"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    purpose: Mapped[e.TokenPurpose] = mapped_column(
        pg_enum(e.TokenPurpose, "token_purpose"), nullable=False
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    target: Mapped[str] = mapped_column(CITEXT, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_verification_tokens_user_purpose", "user_id", "purpose"),)


class MfaRecoveryCodeModel(Base):
    """One-time backup codes for staff MFA (BLK-04). A confirmed enrollment
    replaces the whole set; each row is used at most once."""

    __tablename__ = "mfa_recovery_codes"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    code_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_mfa_recovery_codes_user", "user_id"),)


class OtpCodeModel(Base):
    """Phone OTP (feature F2).

    The code is HMAC-hashed with a pepper held OUTSIDE the database, so a
    database leak does not hand out live codes.
    """

    __tablename__ = "otp_codes"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    phone_number_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("phone_numbers.id", ondelete="CASCADE")
    )
    purpose: Mapped[e.OtpPurpose] = mapped_column(
        pg_enum(e.OtpPurpose, "otp_purpose"), nullable=False
    )
    code_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=5)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_provider: Mapped[str | None] = mapped_column(String(30))
    delivery_status: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_otp_codes_user_purpose_created", "user_id", "purpose", "created_at"),
    )


class ConsentModel(Base):
    """Versioned consent records.

    Exists specifically because TrustLens processes biometric data (a face
    compared against a national ID photo). Explicit, versioned, timestamped
    consent is both an ethical baseline and a legal one.
    """

    __tablename__ = "consents"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    consent_type: Mapped[e.ConsentType] = mapped_column(
        pg_enum(e.ConsentType, "consent_type"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_consents_user_type", "user_id", "consent_type"),)


# ═══════════════════════════════════════════════════════════════════
#  Seller domain
# ═══════════════════════════════════════════════════════════════════


class Marketplace(Base, TimestampMixin):
    __tablename__ = "marketplaces"

    id: Mapped[UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    website_url: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(String(2))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SellerProfile(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "seller_profiles"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    handle: Mapped[str] = mapped_column(CITEXT, nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    business_type: Mapped[str | None] = mapped_column(String(50))
    marketplace_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("marketplaces.id", ondelete="SET NULL")
    )
    #: How a partner marketplace looks a seller up - their id, not ours.
    external_seller_ref: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(80))
    country_code: Mapped[str | None] = mapped_column(String(2))
    bio: Mapped[str | None] = mapped_column(Text)
    account_opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_trust_score_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    #: Denormalised for one-round-trip dashboard reads. Written in the same
    #: transaction as the authoritative rows, so they cannot drift.
    identity_status: Mapped[e.VerificationStatus] = mapped_column(
        pg_enum(e.VerificationStatus, "verification_status"),
        nullable=False,
        default=e.VerificationStatus.NOT_STARTED,
    )
    phone_status: Mapped[e.VerificationStatus] = mapped_column(
        pg_enum(e.VerificationStatus, "verification_status"),
        nullable=False,
        default=e.VerificationStatus.NOT_STARTED,
    )
    email_status: Mapped[e.VerificationStatus] = mapped_column(
        pg_enum(e.VerificationStatus, "verification_status"),
        nullable=False,
        default=e.VerificationStatus.NOT_STARTED,
    )
    is_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index(
            "uq_seller_profiles_handle",
            "handle",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_seller_profiles_external_ref",
            "marketplace_id",
            "external_seller_ref",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND external_seller_ref IS NOT NULL"),
        ),
        Index("ix_seller_profiles_user_id", "user_id", unique=True),
        Index("ix_seller_profiles_flagged", "is_flagged", postgresql_where=text("is_flagged")),
        Index(
            "ix_seller_profiles_display_name_trgm",
            "display_name",
            postgresql_using="gin",
            postgresql_ops={"display_name": "gin_trgm_ops"},
        ),
    )


# ═══════════════════════════════════════════════════════════════════
#  Verification evidence
# ═══════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════
#  Listings
# ═══════════════════════════════════════════════════════════════════


class ListingModel(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "listings"

    id: Mapped[UUID] = uuid_pk()
    seller_id: Mapped[UUID] = uuid_fk("seller_profiles.id")
    marketplace_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("marketplaces.id", ondelete="SET NULL")
    )
    external_listing_ref: Mapped[str | None] = mapped_column(String(160))
    source: Mapped[e.ListingSource] = mapped_column(
        pg_enum(e.ListingSource, "listing_source"), nullable=False, default=e.ListingSource.MANUAL
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    category: Mapped[str | None] = mapped_column(String(80))
    condition: Mapped[str | None] = mapped_column(String(40))
    city: Mapped[str | None] = mapped_column(String(80))
    #: The OLX-style picker's second step - see PAKISTAN_LOCATIONS in
    #: packages/constants. Independent of city so a listing can carry one
    #: without the other on rows written before this column existed.
    area: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    country_code: Mapped[str | None] = mapped_column(String(2))
    external_url: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[e.ListingStatus] = mapped_column(
        pg_enum(e.ListingStatus, "listing_status"), nullable=False, default=e.ListingStatus.DRAFT
    )
    latest_analysis_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    negotiable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attributes: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    video_file_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_listings_seller_created", "seller_id", "created_at"),
        Index("ix_listings_status", "status"),
        Index("ix_listings_city_area", "city", "area"),
        Index(
            "uq_listings_external_ref",
            "marketplace_id",
            "external_listing_ref",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND external_listing_ref IS NOT NULL"),
        ),
        Index(
            "ix_listings_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )


class ListingImageModel(Base):
    __tablename__ = "listing_images"

    id: Mapped[UUID] = uuid_pk()
    listing_id: Mapped[UUID] = uuid_fk("listings.id")
    file_id: Mapped[UUID] = uuid_fk("files.id", ondelete="RESTRICT")
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    #: Computed at upload even though reverse-image search is future scope:
    #: hashes cannot be backfilled once images are purged under the retention
    #: policy, so computing now preserves the option for free.
    perceptual_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    sha256: Mapped[bytes | None] = mapped_column(LargeBinary)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    thumbnail_object_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_listing_images_listing", "listing_id"),
        Index("ix_listing_images_phash", "perceptual_hash"),
    )


class ListingAnalysisModel(Base):
    """Append-only AI evidence. Re-analysis writes a new row."""

    __tablename__ = "listing_analyses"

    id: Mapped[UUID] = uuid_pk()
    listing_id: Mapped[UUID] = uuid_fk("listings.id")
    analyzer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(40))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    labels: Mapped[dict[str, Any]] = mapped_column(JSONB, default=list)
    findings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    price_deviation_pct: Mapped[float | None] = mapped_column(Numeric(6, 2))
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0)
    analysed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_listing_analyses_listing_analysed", "listing_id", "analysed_at"),)


# ═══════════════════════════════════════════════════════════════════
#  Buyer interactions
# ═══════════════════════════════════════════════════════════════════


class FavoriteModel(Base):
    """A buyer's saved listing.

    A plain bookmark, not scored evidence - unlike a listing or a
    verification decision, unfavoriting is a real delete rather than
    something worth retaining. No soft delete, no updated_at.
    """

    __tablename__ = "favorites"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    listing_id: Mapped[UUID] = uuid_fk("listings.id")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_favorites_user_created", "user_id", "created_at"),
        Index("uq_favorites_user_listing", "user_id", "listing_id", unique=True),
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

    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)


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


class OfferModel(Base):
    """An offer or counter-offer inside a conversation (OFF-01). A counter
    is a new row with parent_offer_id set - the original is closed out
    (COUNTERED), never edited."""

    __tablename__ = "offers"

    id: Mapped[UUID] = uuid_pk()
    conversation_id: Mapped[UUID] = uuid_fk("conversations.id")
    listing_id: Mapped[UUID] = uuid_fk("listings.id")
    buyer_id: Mapped[UUID] = uuid_fk("users.id")
    seller_id: Mapped[UUID] = uuid_fk("users.id")
    offered_by: Mapped[UUID] = uuid_fk("users.id")
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")
    status: Mapped[e.OfferStatus] = mapped_column(
        pg_enum(e.OfferStatus, "offer_status"), nullable=False, default=e.OfferStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    parent_offer_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("offers.id", ondelete="SET NULL")
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_offers_conversation", "conversation_id", "created_at"),
        # At most one open offer per listing at a time - a partial index
        # rather than a plain unique constraint, since closed offers must
        # pile up (the negotiation history) without blocking the next one.
        Index(
            "uq_offers_listing_open",
            "listing_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
    )


class TransactionModel(Base):
    """Created the moment an offer is accepted; reserves the listing."""

    __tablename__ = "transactions"

    id: Mapped[UUID] = uuid_pk()
    listing_id: Mapped[UUID] = uuid_fk("listings.id")
    buyer_id: Mapped[UUID] = uuid_fk("users.id")
    seller_id: Mapped[UUID] = uuid_fk("users.id")
    offer_id: Mapped[UUID] = uuid_fk("offers.id")
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")
    status: Mapped[e.TransactionStatus] = mapped_column(
        pg_enum(e.TransactionStatus, "transaction_status"),
        nullable=False,
        default=e.TransactionStatus.INITIATED,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_transactions_buyer", "buyer_id", "created_at"),
        Index("ix_transactions_seller", "seller_id", "created_at"),
    )


class MeetingVenueModel(Base):
    """A staff-curated public meetup spot (SAFE-01) - never a party's home
    address. Deactivated rather than deleted, so past meetups keep a valid
    FK to whatever venue they were actually proposed at."""

    __tablename__ = "meeting_venues"

    id: Mapped[UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    area: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_meeting_venues_city", "city", "is_active"),)


class MeetupModel(Base):
    """A specific place+time proposed for one conversation's handover
    (SAFE-01). Mutual accept, not a one-sided offer: `status` only moves to
    ACCEPTED when the other party responds yes to this exact proposal."""

    __tablename__ = "meetups"

    id: Mapped[UUID] = uuid_pk()
    conversation_id: Mapped[UUID] = uuid_fk("conversations.id")
    listing_id: Mapped[UUID] = uuid_fk("listings.id")
    buyer_id: Mapped[UUID] = uuid_fk("users.id")
    seller_id: Mapped[UUID] = uuid_fk("users.id")
    proposed_by: Mapped[UUID] = uuid_fk("users.id")
    venue_id: Mapped[UUID] = uuid_fk("meeting_venues.id")
    proposed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[e.MeetupStatus] = mapped_column(
        pg_enum(e.MeetupStatus, "meetup_status"), nullable=False, default=e.MeetupStatus.PROPOSED
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    message: Mapped[str | None] = mapped_column(Text)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_meetups_conversation", "conversation_id", "created_at"),
        # At most one open proposal per conversation at a time, same
        # partial-index pattern as uq_offers_listing_open.
        Index(
            "uq_meetups_conversation_open",
            "conversation_id",
            unique=True,
            postgresql_where=text("status = 'PROPOSED'"),
        ),
    )


class FollowModel(Base):
    """A buyer bookmarking a seller (REP-01) - distinct from `FavoriteModel`,
    which bookmarks a listing. A plain delete on unfollow, same as favorites."""

    __tablename__ = "follows"

    id: Mapped[UUID] = uuid_pk()
    follower_id: Mapped[UUID] = uuid_fk("users.id")
    seller_id: Mapped[UUID] = uuid_fk("users.id")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("uq_follows_follower_seller", "follower_id", "seller_id", unique=True),
        Index("ix_follows_seller", "seller_id"),
    )


class ReviewModel(Base):
    """One side of a blind, transaction-scoped review (REP-01). Visibility
    is not a column here - `list_visible_for_seller` only returns a row once
    the counterpart's review for the same transaction also exists, so there
    is nothing to keep in sync when the second side is submitted."""

    __tablename__ = "reviews"

    id: Mapped[UUID] = uuid_pk()
    transaction_id: Mapped[UUID] = uuid_fk("transactions.id")
    listing_id: Mapped[UUID] = uuid_fk("listings.id")
    reviewer_id: Mapped[UUID] = uuid_fk("users.id")
    reviewee_id: Mapped[UUID] = uuid_fk("users.id")
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="review_rating_in_range"),
        Index("uq_reviews_transaction_reviewer", "transaction_id", "reviewer_id", unique=True),
        Index("ix_reviews_reviewee", "reviewee_id", "created_at"),
    )


# ═══════════════════════════════════════════════════════════════════
#  Scoring
# ═══════════════════════════════════════════════════════════════════


class SignalDefinitionModel(Base, TimestampMixin):
    """The signal catalogue. Rows, not code (open/closed principle)."""

    __tablename__ = "signal_definitions"

    id: Mapped[UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    category: Mapped[e.SignalCategory] = mapped_column(
        pg_enum(e.SignalCategory, "signal_category"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    buyer_facing_description: Mapped[str] = mapped_column(Text, default="")
    max_points: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Failing a critical signal clamps the score to a hard cap.
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class ScoringModelRow(Base, TimestampMixin):
    __tablename__ = "scoring_models"

    id: Mapped[UUID] = uuid_pk()
    version: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    algorithm: Mapped[str] = mapped_column(String(30), nullable=False, default="WEIGHTED_SUM")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    weights: Mapped[list[ScoringWeightModel]] = relationship(
        back_populates="model", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        # At most one active model, enforced by the database rather than by
        # application convention.
        Index(
            "uq_scoring_models_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )


class ScoringWeightModel(Base, TimestampMixin):
    __tablename__ = "scoring_weights"

    id: Mapped[UUID] = uuid_pk()
    scoring_model_id: Mapped[UUID] = uuid_fk("scoring_models.id")
    signal_definition_id: Mapped[UUID] = uuid_fk("signal_definitions.id", ondelete="RESTRICT")
    weight: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    threshold_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    hard_cap_on_fail: Mapped[int | None] = mapped_column(SmallInteger)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    model: Mapped[ScoringModelRow] = relationship(back_populates="weights")
    definition: Mapped[SignalDefinitionModel] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("scoring_model_id", "signal_definition_id", name="uq_weight_per_signal"),
        CheckConstraint("weight >= 0", name="weight_non_negative"),
        CheckConstraint(
            "hard_cap_on_fail IS NULL OR (hard_cap_on_fail BETWEEN 0 AND 100)",
            name="cap_in_range",
        ),
    )


class TrustScoreModel(Base):
    """Immutable, append-only score computation."""

    __tablename__ = "trust_scores"

    id: Mapped[UUID] = uuid_pk()
    seller_id: Mapped[UUID] = uuid_fk("seller_profiles.id")
    scoring_model_id: Mapped[UUID] = uuid_fk("scoring_models.id", ondelete="RESTRICT")
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    risk_level: Mapped[e.RiskLevel] = mapped_column(
        pg_enum(e.RiskLevel, "risk_level"), nullable=False
    )
    raw_score: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    #: Sum of weights actually evaluated. Unavailable signals are excluded,
    #: so our provider outage never costs a seller points.
    available_weight: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    cap_applied: Mapped[int | None] = mapped_column(SmallInteger)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    trigger: Mapped[e.ScoreTrigger] = mapped_column(
        pg_enum(e.ScoreTrigger, "score_trigger"), nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text)
    overridden_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    signals: Mapped[list[TrustScoreSignalModel]] = relationship(
        back_populates="trust_score", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="score_in_range"),
        # Overriding a computed score must always carry a written reason.
        CheckConstraint(
            "NOT is_manual_override OR override_reason IS NOT NULL",
            name="override_reason_required",
        ),
        # Exactly one current score per seller - the invariant the whole read
        # path depends on.
        Index(
            "uq_trust_scores_current",
            "seller_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
        Index("ix_trust_scores_seller_computed", "seller_id", "computed_at"),
        Index(
            "ix_trust_scores_risk_current",
            "risk_level",
            postgresql_where=text("is_current"),
        ),
    )


class TrustScoreSignalModel(Base):
    """The explainability record. This table IS the explanation."""

    __tablename__ = "trust_score_signals"

    id: Mapped[UUID] = uuid_pk()
    trust_score_id: Mapped[UUID] = uuid_fk("trust_scores.id")
    signal_definition_id: Mapped[UUID] = uuid_fk("signal_definitions.id", ondelete="RESTRICT")
    #: Denormalised so an old breakdown row survives a definition rename.
    signal_code: Mapped[str] = mapped_column(String(60), nullable=False)
    category: Mapped[e.SignalCategory] = mapped_column(
        pg_enum(e.SignalCategory, "signal_category"), nullable=False
    )
    status: Mapped[e.SignalStatus] = mapped_column(
        pg_enum(e.SignalStatus, "signal_status"), nullable=False
    )
    weight: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    points_awarded: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    points_possible: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(60), nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    #: Non-PII supporting values only - this is exposed to buyers.
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    source_table: Mapped[str | None] = mapped_column(String(60))
    source_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    trust_score: Mapped[TrustScoreModel] = relationship(back_populates="signals")

    __table_args__ = (
        UniqueConstraint("trust_score_id", "signal_definition_id", name="uq_signal_per_score"),
        Index("ix_trust_score_signals_score", "trust_score_id"),
    )


# ═══════════════════════════════════════════════════════════════════
#  Appeals & moderation
# ═══════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════
#  Cross-cutting
# ═══════════════════════════════════════════════════════════════════


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


__all__ = [
    "AccessEventModel",
    "ApiClientModel",
    "ApiKeyModel",
    "ApiRequestLog",
    "AppealMessageModel",
    "AppealModel",
    "AuditLogModel",
    "Base",
    "BlockModel",
    "ConsentModel",
    "ConversationModel",
    "DeviceModel",
    "EmailAddressModel",
    "FavoriteModel",
    "FollowModel",
    "IdentityDocumentModel",
    "IdentityVerificationModel",
    "IpAddressModel",
    "JobRunModel",
    "ListingAnalysisModel",
    "ListingImageModel",
    "ListingModel",
    "Marketplace",
    "MeetingVenueModel",
    "MeetupModel",
    "MessageModel",
    "MfaRecoveryCodeModel",
    "NotificationModel",
    "OfferModel",
    "OtpCodeModel",
    "OutboxEvent",
    "Permission",
    "RefreshToken",
    "ReportModel",
    "ReviewCaseModel",
    "ReviewModel",
    "Role",
    "RolePermission",
    "ScoringModelRow",
    "ScoringWeightModel",
    "SellerProfile",
    "SignalDefinitionModel",
    "StoredFileModel",
    "TransactionModel",
    "TrustScoreModel",
    "TrustScoreSignalModel",
    "User",
    "UserDevice",
    "UserRoleLink",
    "VerificationTokenModel",
    "WebhookDeliveryModel",
    "WebhookEndpointModel",
]
