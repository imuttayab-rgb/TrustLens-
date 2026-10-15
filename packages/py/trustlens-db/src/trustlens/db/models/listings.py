"""Listings models. Preserve table names and transaction behavior across imports."""

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
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
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
    category_node_id: Mapped[str | None] = mapped_column(String(240), index=True)
    category_schema_version: Mapped[int | None] = mapped_column(Integer)
    category_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    show_phone: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    condition: Mapped[str | None] = mapped_column(String(40))
    city: Mapped[str | None] = mapped_column(String(80))
    #: The OLX-style picker's second step - see PAKISTAN_LOCATIONS in
    #: packages/constants. Independent of city so a listing can carry one
    #: without the other on rows written before this column existed.
    area: Mapped[str | None] = mapped_column(String(120))
    #: Private full address typed by the seller; never exposed publicly.
    address_line: Mapped[str | None] = mapped_column(String(300))
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

    is_removed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

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


class PhotoGuardStateModel(Base):
    __tablename__ = "photo_guard_state"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PhotoFingerprintModel(Base):
    __tablename__ = "photo_fingerprints"
    image_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("listing_images.id", ondelete="CASCADE"), primary_key=True
    )
    owner_user_id: Mapped[UUID] = uuid_fk("users.id", ondelete="RESTRICT")
    digests: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    bands: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    fingerprint: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    __table_args__ = (
        Index("ix_photo_digests", "digests", postgresql_using="gin"),
        Index("ix_photo_bands", "bands", postgresql_using="gin"),
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


class SavedSearchModel(Base):
    """A buyer's remembered browse filter (FAV-01) - re-runnable with one
    click. Same "bookmark, not evidence" reasoning as FavoriteModel."""

    __tablename__ = "saved_searches"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_node_id: Mapped[str | None] = mapped_column(String(240))
    facets: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    category: Mapped[str | None] = mapped_column(String(80))
    q: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(80))
    area: Mapped[str | None] = mapped_column(String(120))
    min_price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    max_price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_saved_searches_user_created", "user_id", "created_at"),)
