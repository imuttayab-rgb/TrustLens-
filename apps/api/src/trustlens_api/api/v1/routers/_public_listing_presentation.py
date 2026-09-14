"""Shared PublicListingSummary -> response mapping.

Used by both the anonymous catalog browse (public_listings.py) and the
authenticated favorites list (me.py) - same projection, same presigned-URL
handling, so it lives once rather than being copied twice and drifting.
"""

from __future__ import annotations

from typing import Any

from trustlens.core.domain.entities import PublicListingSummary
from trustlens_api.api.deps import ContainerDep, UowDep
from trustlens_api.api.v1.schemas.public_listing import PublicListingResponse


async def image_url(container: ContainerDep, uow: UowDep, file_id: Any) -> str | None:
    if file_id is None:
        return None
    stored = await uow.files.get(file_id)
    if stored is None:
        return None
    ttl = container.settings.storage.storage_presign_ttl_seconds
    return await container.storage.presign_download(
        bucket=stored.bucket, object_key=stored.object_key, ttl_seconds=ttl
    )


async def thumbnail_url(
    container: ContainerDep, uow: UowDep, file_id: Any, thumbnail_object_key: str | None
) -> str | None:
    if file_id is None or thumbnail_object_key is None:
        return None
    stored = await uow.files.get(file_id)
    if stored is None:
        return None
    ttl = container.settings.storage.storage_presign_ttl_seconds
    return await container.storage.presign_download(
        bucket=stored.bucket, object_key=thumbnail_object_key, ttl_seconds=ttl
    )


async def to_public_listing_response(
    item: PublicListingSummary, container: ContainerDep, uow: UowDep
) -> PublicListingResponse:
    return PublicListingResponse(
        id=item.id,
        title=item.title,
        price=item.price,
        currency=item.currency,
        category=item.category,
        condition=item.condition,
        city=item.city,
        area=item.area,
        created_at=item.created_at,
        seller_handle=item.seller_handle,
        seller_display_name=item.seller_display_name,
        status=item.status,
        negotiable=item.negotiable,
        risk_level=item.risk_level,
        identity_verified=item.identity_verified,
        phone_verified=item.phone_verified,
        image_url=await image_url(container, uow, item.primary_image_file_id),
        thumbnail_url=await thumbnail_url(
            container, uow, item.primary_image_file_id, item.primary_image_thumbnail_key
        ),
        latitude=item.latitude,
        longitude=item.longitude,
    )


__all__ = ["image_url", "thumbnail_url", "to_public_listing_response"]
