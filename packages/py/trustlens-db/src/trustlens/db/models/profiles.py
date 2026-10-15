"""Profiles models. Preserve table names and transaction behavior across imports."""

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
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT
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
    #: Individual vs company (BUS-01) - the four columns below only mean
    #: anything once this is BUSINESS.
    account_type: Mapped[e.SellerAccountType] = mapped_column(
        pg_enum(e.SellerAccountType, "seller_account_type"),
        nullable=False,
        default=e.SellerAccountType.INDIVIDUAL,
    )
    business_legal_name: Mapped[str | None] = mapped_column(String(200))
    business_registration_number: Mapped[str | None] = mapped_column(String(80))
    business_document_file_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL")
    )
    business_verification_status: Mapped[e.VerificationStatus] = mapped_column(
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


class AccountProfileModel(Base, TimestampMixin):
    __tablename__ = "account_profiles"
    username_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    public_name: Mapped[str | None] = mapped_column(String(150))
    name_status: Mapped[str] = mapped_column(String(20), nullable=False, default="NOT_STARTED")
    name_identity_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("identity_verifications.id", ondelete="SET NULL")
    )
    name_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    name_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_photo_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("profile_photos.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ProfilePhotoModel(Base, TimestampMixin):
    __tablename__ = "profile_photos"
    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id", ondelete="CASCADE")
    identity_id: Mapped[UUID] = uuid_fk("identity_verifications.id", ondelete="CASCADE")
    bucket: Mapped[str] = mapped_column(String(80), nullable=False)
    object_key: Mapped[str] = mapped_column(String(400), nullable=False, unique=True)
    sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED")
    engine: Mapped[str | None] = mapped_column(String(40))
    similarity: Mapped[float | None] = mapped_column(Numeric(5, 4))
    threshold: Mapped[float | None] = mapped_column(Numeric(5, 4))
    reason: Mapped[str | None] = mapped_column(String(100))
    consent_version: Mapped[str] = mapped_column(String(20), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_profile_photos_user_created", "user_id", "created_at"),)


class ProfileNameRequestModel(Base, TimestampMixin):
    __tablename__ = "profile_name_requests"
    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id", ondelete="CASCADE")
    identity_id: Mapped[UUID] = uuid_fk("identity_verifications.id", ondelete="CASCADE")
    requested_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="REVIEW")
    note: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    decided_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decision_note: Mapped[str | None] = mapped_column(String(1000))
    __table_args__ = (Index("ix_profile_name_requests_status_created", "status", "created_at"),)


class ProfileHandleAliasModel(Base):
    __tablename__ = "profile_handle_aliases"
    handle: Mapped[str] = mapped_column(CITEXT, primary_key=True)
    user_id: Mapped[UUID] = uuid_fk("users.id", ondelete="CASCADE")


class ListingPauseModel(Base):
    __tablename__ = "listing_pauses"
    listing_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True
    )
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DemoProfileAccessModel(Base):
    """Explicit pre-existing fixture allowlist; not a verification record."""

    __tablename__ = "demo_profile_access"
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    seller_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("seller_profiles.id", ondelete="CASCADE"), nullable=False
    )
    batch: Mapped[str] = mapped_column(String(80), nullable=False)
    enrolled_email: Mapped[str] = mapped_column(String(254), nullable=False)
    fixture_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    account_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
