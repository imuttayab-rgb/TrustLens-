"""The public listing catalog (buyer-facing browse/search).

Same reasoning as `public_scores.py`: this is a page an anonymous buyer opens
directly - "browse what's for sale" - not a partner integration, so it gets
its own anonymous, IP-rate-limited door rather than being bolted onto the
seller-scoped `GET /listings`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from trustlens.core.application.use_cases.listings import (
    BrowsePublicListings,
    BrowsePublicListingsQuery,
)
from trustlens.core.domain.entities import PublicListingSummary
from trustlens.core.domain.errors import RateLimitExceeded
from trustlens.shared.logging import get_logger
from trustlens_api.api.deps import ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.common import PageMeta, envelope
from trustlens_api.api.v1.schemas.public_listing import PublicListingResponse

log = get_logger(__name__)

router = APIRouter(tags=["Public Page"])


async def _image_url(container: ContainerDep, uow: UowDep, file_id: Any) -> str | None:
    if file_id is None:
        return None
    stored = await uow.files.get(file_id)
    if stored is None:
        return None
    ttl = container.settings.storage.storage_presign_ttl_seconds
    return await container.storage.presign_download(
        bucket=stored.bucket, object_key=stored.object_key, ttl_seconds=ttl
    )


async def _to_response(
    item: PublicListingSummary, container: ContainerDep, uow: UowDep
) -> PublicListingResponse:
    return PublicListingResponse(
        id=item.id,
        title=item.title,
        price=item.price,
        currency=item.currency,
        category=item.category,
        city=item.city,
        created_at=item.created_at,
        seller_handle=item.seller_handle,
        seller_display_name=item.seller_display_name,
        image_url=await _image_url(container, uow, item.primary_image_file_id),
    )


@router.get(
    "/public/listings",
    summary="Browse and search active listings (no auth)",
    description=(
        "Powers the marketplace browse/search page. Anonymous, and rate "
        "limited per IP. Only ACTIVE listings are ever returned - a listing "
        "still being analysed, flagged, or removed never appears here."
    ),
)
async def browse_public_listings(
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    category: str | None = Query(default=None, max_length=80),
    q: str | None = Query(default=None, max_length=200, alias="q"),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    await _throttle(container, meta)

    page = await BrowsePublicListings(uow=uow).execute(
        BrowsePublicListingsQuery(category=category, q=q, limit=limit, offset=offset)
    )
    items = [await _to_response(item, container, uow) for item in page.items]

    return envelope(
        [item.model_dump(by_alias=True) for item in items],
        request_id=meta.request_id,
        pagination=PageMeta.build(
            page=(page.offset // page.limit) + 1,
            per_page=page.limit,
            total=page.total,
        ),
    )


async def _throttle(container: ContainerDep, meta: MetaDep) -> None:
    """Per-IP limit, failing open - the same policy as the public score read.

    A browse/search page is exactly the kind of surface a scraper hits hard,
    but a Redis blip must not turn the marketplace's front door into an
    error page, so the limiter degrades rather than blocks when it is down.
    """
    limits = container.settings.rate_limit
    if not limits.enabled or meta.ip is None:
        return

    try:
        allowed, _remaining, retry_after = await container.rate_limiter.hit(
            f"anon:listings:{meta.ip}", limit=limits.anon_per_minute, window_seconds=60
        )
    except Exception:
        log.warning("anon_rate_limit_unavailable_failing_open", ip=meta.ip)
        return

    if not allowed:
        raise RateLimitExceeded(
            f"Rate limit of {limits.anon_per_minute} requests per minute exceeded.",
            retry_after=retry_after,
        )


__all__ = ["router"]
