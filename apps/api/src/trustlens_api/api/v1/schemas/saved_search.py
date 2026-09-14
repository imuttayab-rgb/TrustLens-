"""Saved search (FAV-01) request/response models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from trustlens.core.application.use_cases.saved_searches import MAX_NAME_CHARS
from trustlens_api.api.v1.schemas.common import Schema


class CreateSavedSearchRequest(Schema):
    name: str = Field(min_length=1, max_length=MAX_NAME_CHARS)
    category: str | None = None
    q: str | None = None
    city: str | None = None
    area: str | None = None
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)


class SavedSearchResponse(Schema):
    id: UUID
    name: str
    category: str | None = None
    q: str | None = None
    city: str | None = None
    area: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    created_at: datetime | None = None


__all__ = ["CreateSavedSearchRequest", "SavedSearchResponse"]
