"""Favorites request/response models."""

from __future__ import annotations

from uuid import UUID

from trustlens_api.api.v1.schemas.common import Schema


class AddFavoriteRequest(Schema):
    listing_id: UUID


class FavoriteIdsResponse(Schema):
    listing_ids: list[UUID]


__all__ = ["AddFavoriteRequest", "FavoriteIdsResponse"]
