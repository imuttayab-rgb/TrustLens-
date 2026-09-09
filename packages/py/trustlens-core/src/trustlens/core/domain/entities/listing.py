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
    country_code: str | None = None
    external_url: str | None = None
    posted_at: datetime | None = None
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
    created_at: datetime
    seller_id: UUID
    seller_handle: str
    seller_display_name: str
    primary_image_file_id: UUID | None = None


__all__ = ["Listing", "ListingAnalysis", "ListingImage", "PublicListingSummary", "ScamLabel"]
