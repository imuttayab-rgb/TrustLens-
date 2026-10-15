"""Accounts models. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import (
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
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    uuid_fk,
    uuid_pk,
)
from .common import pg_enum


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


class PrivateAccountSettingsModel(Base):
    __tablename__ = "private_account_settings"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    date_of_birth: Mapped[str | None] = mapped_column(String(10))
    gender: Mapped[str | None] = mapped_column(String(40))
    addresses: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AccountDeletionRequestModel(Base):
    __tablename__ = "account_deletion_requests"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING_REVIEW")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
