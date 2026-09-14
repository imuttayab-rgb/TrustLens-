"""Listing request and response models (feature F5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from trustlens.core.application.use_cases.listings import (
    MAX_DESCRIPTION_CHARS,
    MAX_TITLE_CHARS,
)
from trustlens_api.api.v1.schemas.common import Schema


class ListingWriteRequest(Schema):
    """Create or replace a listing.

    Every field here is attacker-controlled - a seller writes it and an LLM
    later reads it. The length caps are the first line of defence: they bound
    what can be pushed into a prompt at all. The second line is that the
    analyser's verdict can only move one bounded signal (ADR-0002).
    """

    title: str = Field(min_length=3, max_length=MAX_TITLE_CHARS)
    description: str = Field(min_length=10, max_length=MAX_DESCRIPTION_CHARS)
    price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    category: str | None = Field(default=None, max_length=80)
    condition: str | None = Field(default=None, max_length=50)
    city: str | None = Field(default=None, max_length=80)
    area: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    negotiable: bool = False
    #: Freeform spec bag - {"Brand": "Samsung", "RAM": "8GB"} - no
    #: per-category schema (LST-01).
    attributes: dict[str, str] = Field(default_factory=dict, max_length=20)
    video_file_id: UUID | None = None


class ListingAnalysisResponse(Schema):
    """What the analysers concluded, as evidence rather than a verdict."""

    risk_score: float
    confidence: float
    analyzer_type: str
    provider: str
    model_name: str
    analysed_at: datetime
    summary: str | None = None
    labels: list[dict[str, Any]] = Field(default_factory=list)
    price_deviation_pct: float | None = None


class ListingResponse(Schema):
    id: UUID
    seller_id: UUID
    title: str
    description: str
    status: str
    source: str
    created_at: datetime
    price: float | None = None
    currency: str | None = None
    category: str | None = None
    condition: str | None = None
    city: str | None = None
    area: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    country_code: str | None = None
    negotiable: bool = False
    attributes: dict[str, str] = Field(default_factory=dict)
    video_file_id: UUID | None = None
    updated_at: datetime | None = None
    analysis: ListingAnalysisResponse | None = None


__all__ = [
    "ListingAnalysisResponse",
    "ListingResponse",
    "ListingWriteRequest",
]
