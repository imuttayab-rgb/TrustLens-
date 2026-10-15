"""The public listing catalog (buyer-facing browse/search).

Same reasoning as `public_scores.py`: this is a page an anonymous buyer opens
directly - "browse what's for sale" - not a partner integration, so it gets
its own anonymous, IP-rate-limited door rather than being bolted onto the
seller-scoped `GET /listings`.
"""

from __future__ import annotations

from typing import Any
import json
from trustlens.core.domain.errors import ValidationError
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


@router.get("/public/recommendations", summary="Related eligible listings, deduplicated by purpose")
async def public_recommendations(
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    listing_id: UUID | None = Query(default=None, alias="listingId"),
    category_node_id: str | None = Query(default=None, max_length=240, alias="categoryNodeId"),
    category: str | None = Query(default=None, max_length=80),
    q: str | None = Query(default=None, max_length=200),
    city: str | None = Query(default=None, max_length=80),
    area: str | None = Query(default=None, max_length=120),
    min_price: float | None = Query(default=None, ge=0, alias="minPrice"),
    max_price: float | None = Query(default=None, ge=0, alias="maxPrice"),
    near_latitude: float | None = Query(default=None, ge=-90, le=90, alias="nearLatitude"),
    near_longitude: float | None = Query(default=None, ge=-180, le=180, alias="nearLongitude"),
    radius_km: float | None = Query(default=None, gt=0, le=500, alias="radiusKm"),
    exclude: str = Query(default="", max_length=8000),
    limit: int = Query(default=4, ge=1, le=20),
) -> dict[str, Any]:
    from trustlens.core.catalogue import category_node
    from trustlens.core.catalogue.recommendations import (
        recommendation_plan,
        same_search,
        RecommendationQuery,
    )

    await _throttle(container, meta)
    facts = {}
    seen = set(exclude.split(","))
    if listing_id:
        source = await GetPublicListing(uow=uow).execute(listing_id)
        category_node_id, category, facts = (
            source.category_node_id,
            source.category,
            source.category_data,
        )
        seen.add(str(listing_id))
        city = city or source.city
    category_node(category_node_id)
    plans = recommendation_plan(category_node_id, facts, q, detail=bool(listing_id))
    if not plans and category:
        plans = [RecommendationQuery("alternatives", None)]
    output = []
    for plan in plans:
        # Accessories have their own price scale; a phone's minimum price would
        # otherwise exclude a compatible case. The UI labels this explicitly.
        is_accessory = plan.key == "compatible-accessories"
        items = []
        for offset in (0, 50, 100):
            page = await BrowsePublicListings(uow=uow).execute(
                BrowsePublicListingsQuery(
                    category_node_id=plan.node,
                    category=None if plan.node else category,
                    q=plan.q,
                    facets=plan.facets,
                    city=city,
                    area=area,
                    min_price=None if is_accessory else min_price,
                    max_price=None if is_accessory else max_price,
                    near_latitude=near_latitude,
                    near_longitude=near_longitude,
                    radius_km=radius_km,
                    limit=50,
                    offset=offset,
                )
            )
            for item in page.items:
                if str(item.id) in seen or (not listing_id and q and same_search(item.title, q)):
                    continue
                seen.add(str(item.id))
                items.append(item)
                if len(items) >= limit:
                    break
            if len(items) >= limit or offset + 50 >= page.total:
                break
        if items:
            output.append(
                {
                    "key": plan.key,
                    "categoryNodeId": plan.node,
                    "query": plan.q,
                    "facets": plan.facets,
                    "accessoryBudgetIndependent": is_accessory,
                    "items": [
                        (await to_public_listing_response(item, container, uow)).model_dump(
                            by_alias=True
                        )
                        for item in items
                    ],
                }
            )
    return envelope(output, request_id=meta.request_id)


@router.get(
    "/public/catalogue-options", summary="Confirmed brand/model suggestions from eligible listings"
)
async def catalogue_options(
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    category_node_id: str = Query(max_length=240, alias="categoryNodeId"),
    field: str = Query(max_length=40),
    parent_value: str | None = Query(default=None, max_length=160, alias="parentValue"),
    q: str = Query(default="", max_length=80),
) -> dict[str, Any]:
    from trustlens.core.catalogue import category_fields

    await _throttle(container, meta)
    fields = {f["key"] for f in category_fields(category_node_id)}
    if field not in {"brand", "make", "model", "compatible_model"} or field not in fields:
        raise ValidationError("Choose a supported product field.", field="field")
    parent_key = (
        ("make" if "make" in fields else "brand") if field == "model" and parent_value else None
    )
    values = await uow.listings.category_field_options(
        category_node_id, field, parent_key=parent_key, parent_value=parent_value, query=q
    )
    return envelope(values, request_id=meta.request_id)


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
    category_node_id: str | None = Query(default=None, max_length=240, alias="categoryNodeId"),
    facets: str | None = Query(default=None, max_length=3000),
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

    try:
        parsed_facets = json.loads(facets) if facets else {}
        if not isinstance(parsed_facets, dict):
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "Specification filters must be a JSON object.", field="facets"
        ) from exc

    page = await BrowsePublicListings(uow=uow).execute(
        BrowsePublicListingsQuery(
            category=category,
            category_node_id=category_node_id,
            facets=parsed_facets,
            q=q,
            city=city,
            area=area,
            min_price=min_price,
            max_price=max_price,
            seller_handle=seller,
            attribute_key=attribute_key,
            attribute_value=attribute_value,
            include_sold=False,
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
        category_node_id=detail.category_node_id,
        category_data=detail.category_data,
        public_phone=detail.public_phone,
        condition=detail.condition,
        city=detail.city,
        area=detail.area,
        created_at=detail.created_at,
        seller_handle=detail.seller_handle,
        seller_display_name=detail.seller_display_name,
        seller_photo_url=f"/api/v1/public/profiles/{detail.seller_user_id}/photo"
        if detail.seller_user_id
        else None,
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
        from fastapi import HTTPException

        raise HTTPException(
            503, "Abuse protection temporarily unavailable", headers={"Retry-After": "30"}
        ) from None

    if not allowed:
        raise RateLimitExceeded(
            f"Rate limit of {limits.anon_per_minute} requests per minute exceeded.",
            retry_after=retry_after,
        )


__all__ = ["router"]


@router.get(
    "/public/motor-dealers", summary="Verified business sellers with visible motor listings"
)
async def motor_dealers(
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    limit: int = Query(default=12, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    city: str | None = Query(default=None, max_length=80),
    q: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    await _throttle(container, meta)
    rows = await uow.listings.public_dealers(limit=limit, offset=offset, city=city, q=q)
    return envelope(
        [
            {
                "handle": row["handle"],
                "displayName": row["display_name"],
                "city": row["city"],
                "activeListings": row["active_listings"],
                "profileUrl": "/profile/" + str(row["user_id"]),
                "photoUrl": "/api/v1/public/profiles/" + str(row["user_id"]) + "/photo",
            }
            for row in rows
        ],
        request_id=meta.request_id,
    )
