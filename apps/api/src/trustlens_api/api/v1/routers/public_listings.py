"""The public listing catalog (buyer-facing browse/search).

Same reasoning as `public_scores.py`: this is a page an anonymous buyer opens
directly - "browse what's for sale" - not a partner integration, so it gets
its own anonymous, IP-rate-limited door rather than being bolted onto the
seller-scoped `GET /listings`.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query

from trustlens.core.application.use_cases.listings import (
    BrowsePublicListings,
    BrowsePublicListingsQuery,
    GetPublicListing,
)
from trustlens.core.domain.errors import RateLimitExceeded
from trustlens.shared.logging import get_logger
from trustlens_api.api.deps import ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.routers._public_listing_presentation import (
    image_url,
    thumbnail_url,
    to_public_listing_response,
)
from trustlens_api.api.v1.schemas.common import PageMeta, envelope
from trustlens_api.api.v1.schemas.public_listing import (
    PublicListingDetailResponse,
    PublicListingImageResponse,
)

log = get_logger(__name__)

router = APIRouter(tags=["Public Page"])


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
    city: str | None = Query(default=None, max_length=80),
    area: str | None = Query(default=None, max_length=120),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    seller: str | None = Query(
        default=None,
        max_length=64,
        description="Filter to one seller's listings, by handle - the public storefront. "
        "Unlike the anonymous catalog, this also includes their reserved/sold history.",
    ),
    attribute_key: str | None = Query(default=None, max_length=80, alias="attributeKey"),
    attribute_value: str | None = Query(default=None, max_length=200, alias="attributeValue"),
    near_latitude: float | None = Query(default=None, ge=-90, le=90, alias="nearLatitude"),
    near_longitude: float | None = Query(default=None, ge=-180, le=180, alias="nearLongitude"),
    radius_km: float | None = Query(default=None, gt=0, le=500, alias="radiusKm"),
    condition: str | None = Query(default=None, max_length=20),
    min_trust_score: int | None = Query(default=None, ge=0, le=100, alias="minTrustScore"),
    max_trust_score: int | None = Query(default=None, ge=0, le=100, alias="maxTrustScore"),
    verified_only: bool = Query(default=False, alias="verifiedOnly"),
    sort: str = Query(default="newest"),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    await _throttle(container, meta)

    page = await BrowsePublicListings(uow=uow).execute(
        BrowsePublicListingsQuery(
            category=category,
            q=q,
            city=city,
            area=area,
            min_price=min_price,
            max_price=max_price,
            seller_handle=seller,
            attribute_key=attribute_key,
            attribute_value=attribute_value,
            include_sold=seller is not None,
            near_latitude=near_latitude,
            near_longitude=near_longitude,
            radius_km=radius_km,
            condition=condition,
            min_trust_score=min_trust_score,
            max_trust_score=max_trust_score,
            verified_only=verified_only,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    )
    items = [await to_public_listing_response(item, container, uow) for item in page.items]

    return envelope(
        [item.model_dump(by_alias=True) for item in items],
        request_id=meta.request_id,
        pagination=PageMeta.build(
            page=(page.offset // page.limit) + 1,
            per_page=page.limit,
            total=page.total,
        ),
    )


@router.get(
    "/public/listings/{listing_id}",
    summary="View a listing (no auth)",
    description=(
        "The full listing page a catalog card opens into. Anonymous, rate "
        "limited per IP. Returns 404 for anything not ACTIVE - a listing "
        "still being analysed, flagged, or removed is treated as not found, "
        "the same as one that never existed."
    ),
)
async def get_public_listing(
    listing_id: UUID,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    await _throttle(container, meta)

    detail = await GetPublicListing(uow=uow).execute(listing_id)
    images = []
    for image in detail.images:
        url = await image_url(container, uow, image.file_id)
        if url is None:
            continue
        images.append(
            PublicListingImageResponse(
                image_url=url,
                thumbnail_url=await thumbnail_url(
                    container, uow, image.file_id, image.thumbnail_object_key
                ),
                is_primary=image.is_primary,
            )
        )
    response = PublicListingDetailResponse(
        id=detail.id,
        title=detail.title,
        description=detail.description,
        price=detail.price,
        currency=detail.currency,
        category=detail.category,
        condition=detail.condition,
        city=detail.city,
        area=detail.area,
        created_at=detail.created_at,
        seller_handle=detail.seller_handle,
        seller_display_name=detail.seller_display_name,
        status=detail.status,
        negotiable=detail.negotiable,
        attributes=detail.attributes,
        video_url=await image_url(container, uow, detail.video_file_id),
        risk_level=detail.risk_level,
        identity_verified=detail.identity_verified,
        phone_verified=detail.phone_verified,
        images=images,
        latitude=detail.latitude,
        longitude=detail.longitude,
    )
    return envelope(response.model_dump(by_alias=True), request_id=meta.request_id)


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
