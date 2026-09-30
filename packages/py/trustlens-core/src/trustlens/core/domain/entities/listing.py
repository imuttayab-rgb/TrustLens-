"""Listing entities and AI analysis results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from trustlens.core.domain.enums import ListingSource, ListingStatus
from trustlens.core.domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class ListingImage:
    id: UUID
    listing_id: UUID
    file_id: UUID
    position: int
    created_at: datetime
    width: int | None = None
    height: int | None = None
    #: Computed at upload time even though reverse-image search is future
    #: scope: hashes cannot be backfilled once images are purged under the
    #: retention policy, so computing now preserves the option cheaply.
    perceptual_hash: bytes | None = None
    sha256: bytes | None = None
    is_primary: bool = False
    #: A resized (~400px) derivative, stored alongside the original under a
    #: `_thumb` suffix on the same object key - cards load this, not the
    #: full-size upload. None on rows written before thumbnailing existed,
    #: or if generation failed (non-fatal, same as a missing perceptual hash).
    thumbnail_object_key: str | None = None


@dataclass(frozen=True, slots=True)
class ScamLabel:
    """One finding from the LLM or the classifier, with its evidence."""

    code: str
    confidence: float
    evidence: str | None = None


@dataclass(frozen=True, slots=True)
class ListingAnalysis:
    """An AI verdict on one listing. Append-only.

    Re-analysing writes a new row and repoints `listings.latest_analysis_id`,
    so "what the AI said, and when" survives every model and prompt upgrade.

    Note this is *evidence*, not a score: `risk_score` here is a listing-level
    signal input that the scoring policy converts into points (ADR-0002).
    """

    id: UUID
    listing_id: UUID
    analyzer_type: str
    provider: str
    model_name: str
    risk_score: float
    confidence: float
    analysed_at: datetime
    model_version: str | None = None
    prompt_version: str | None = None
    labels: tuple[ScamLabel, ...] = ()
    findings: dict[str, Any] = field(default_factory=dict)
    price_deviation_pct: float | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0

    @property
    def label_codes(self) -> frozenset[str]:
        return frozenset(label.code for label in self.labels)


@dataclass(frozen=True, slots=True)
class Listing:
    id: UUID
    seller_id: UUID
    title: str
    description: str
    status: ListingStatus
    source: ListingSource
    created_at: datetime
    marketplace_id: UUID | None = None
    external_listing_ref: str | None = None
    price: Money | None = None
    category: str | None = None
    condition: str | None = None
    city: str | None = None
    area: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    country_code: str | None = None
    external_url: str | None = None
    posted_at: datetime | None = None
    #: Whether the seller will accept offers below the listed price - shown
    #: as a badge; OFF-01's offer flow works either way, this is purely a
    #: buyer-facing signal of intent.
    negotiable: bool = False
    #: Freeform key/value specs (e.g. {"Brand": "Samsung", "RAM": "8GB"}) -
    #: no per-category schema, so a seller can describe anything without a
    #: migration, and MKT-01's attribute search matches on these keys.
    attributes: dict[str, str] = field(default_factory=dict)
    video_file_id: UUID | None = None
    images: tuple[ListingImage, ...] = ()
    latest_analysis: ListingAnalysis | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    version: int = 1

    @property
    def is_analysed(self) -> bool:
        return self.latest_analysis is not None


@dataclass(frozen=True, slots=True)
class PublicListingSummary:
    """What an anonymous buyer sees in the catalog/search results.

    Deliberately thin: no description, no seller contact details, no
    analysis internals - just enough to decide whether to open the listing.
    Only ever built from an ACTIVE listing (see BrowsePublicListings).
    """

    id: UUID
    title: str
    price: float | None
    currency: str | None
    category: str | None
    city: str | None
    area: str | None
    created_at: datetime
    seller_id: UUID
    seller_handle: str
    seller_display_name: str
    condition: str | None = None
    #: ACTIVE/RESERVED/SOLD as a plain string - a buyer's own favorites and
    #: a seller's storefront both now show a deal in progress or done, not
    #: just what's currently buyable.
    status: str = "ACTIVE"
    negotiable: bool = False
    risk_level: str | None = None
    #: Alongside `risk_level`, not instead of it - the band is what a
    #: `RiskBadge` always shows (WCAG 1.4.1, colour is never the only
    #: signal), the number is the honest "Trust 92" a buyer also wants.
    score: int | None = None
    identity_verified: bool = False
    phone_verified: bool = False
    primary_image_file_id: UUID | None = None
    primary_image_thumbnail_key: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True, slots=True)
class PublicListingImage:
    file_id: UUID
    is_primary: bool
    thumbnail_object_key: str | None = None


@dataclass(frozen=True, slots=True)
class PublicListingDetail:
    """The full "view this listing" page a buyer opens from the catalog.

    Unlike PublicListingSummary this does carry the description and every
    image, not just the primary one - a buyer deciding whether to message a
    seller needs the whole listing, not a card's worth. Still no seller
    contact details: that boundary doesn't move just because the page got
    bigger. Reachable for a RESERVED/SOLD listing too (a direct link a buyer
    already has should not 404 just because the deal moved on), never from
    search.
    """

    id: UUID
    title: str
    description: str
    price: float | None
    currency: str | None
    category: str | None
    city: str | None
    area: str | None
    created_at: datetime
    seller_id: UUID
    seller_handle: str
    seller_display_name: str
    condition: str | None = None
    status: str = "ACTIVE"
    negotiable: bool = False
    attributes: dict[str, str] = field(default_factory=dict)
    video_file_id: UUID | None = None
    risk_level: str | None = None
    identity_verified: bool = False
    phone_verified: bool = False
    images: tuple[PublicListingImage, ...] = ()
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True, slots=True)
class Favorite:
    """A buyer's saved listing - a bookmark, not scored evidence.

    Unlike a listing or a verification decision, removing one is a real
    delete: there is no appeal, audit trail or trust-score input that
    depends on a favorite ever having existed.
    """

    id: UUID
    user_id: UUID
    listing_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SavedSearch:
    """A buyer's remembered browse filter (FAV-01), re-runnable with one
    click instead of rebuilding a search from scratch. Mirrors the
    filterable fields of `BrowsePublicListingsQuery`, minus sort/paging and
    the newer attribute/radius filters - the ones a buyer is most likely to
    want reproduced verbatim."""

    id: UUID
    user_id: UUID
    name: str
    category: str | None = None
    q: str | None = None
    city: str | None = None
    area: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    created_at: datetime | None = None


__all__ = [
    "Favorite",
    "Listing",
    "ListingAnalysis",
    "ListingImage",
    "PublicListingDetail",
    "PublicListingImage",
    "PublicListingSummary",
    "SavedSearch",
    "ScamLabel",
]
