"""Listing endpoints (feature F5).

Ownership is enforced in the use cases, not here: a route-level permission
answers "may a seller manage listings", never "may this seller touch THIS
listing". Conflating the two is how IDOR gets shipped.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import Field

from trustlens.core.application.use_cases.listings import (
    CreateListing,
    CreateListingCommand,
    DeleteListing,
    DeleteListingCommand,
    GetListing,
    ListingInput,
    ListSellerListings,
    ListSellerListingsQuery,
    RequestListingAnalysis,
    UpdateListing,
    UpdateListingCommand,
)
from trustlens.core.domain.entities import Listing
from trustlens.shared.logging import get_logger
from trustlens_api.api.deps import ContainerDep, MetaDep, SellerDep, UowDep, require_permissions
from trustlens_api.api.v1.schemas.common import JobAccepted, PageMeta, Schema, envelope
from trustlens_api.api.v1.schemas.listing import (
    ListingAnalysisResponse,
    ListingResponse,
    ListingWriteRequest,
)


class ListingImageRequest(Schema):
    """Reference to a file already uploaded via /files/upload-intent."""

    file_id: UUID = Field(description="The file_id returned by /files/upload-intent")


log = get_logger(__name__)

router = APIRouter(prefix="/listings", tags=["Listings"])


def _to_response(listing: Listing) -> ListingResponse:
    analysis = None
    if listing.latest_analysis is not None:
        a = listing.latest_analysis
        analysis = ListingAnalysisResponse(
            risk_score=a.risk_score,
            confidence=a.confidence,
            analyzer_type=a.analyzer_type,
            provider=a.provider,
            model_name=a.model_name,
            analysed_at=a.analysed_at,
            summary=getattr(a, "summary", None),
            labels=[
                {"code": label.code, "confidence": label.confidence, "evidence": label.evidence}
                for label in getattr(a, "labels", ()) or ()
            ],
            price_deviation_pct=getattr(a, "price_deviation_pct", None),
        )

    return ListingResponse(
        id=listing.id,
        seller_id=listing.seller_id,
        title=listing.title,
        description=listing.description,
        status=str(listing.status),
        source=str(listing.source),
        created_at=listing.created_at,
        price=listing.price.amount if listing.price else None,
        currency=listing.price.currency if listing.price else None,
        category=listing.category,
        condition=listing.condition,
        city=listing.city,
        area=listing.area,
        latitude=listing.latitude,
        longitude=listing.longitude,
        country_code=listing.country_code,
        updated_at=listing.updated_at,
        analysis=analysis,
    )


def _to_input(body: ListingWriteRequest) -> ListingInput:
    return ListingInput(
        title=body.title,
        description=body.description,
        price=body.price,
        currency=body.currency,
        category=body.category,
        condition=body.condition,
        city=body.city,
        area=body.area,
        latitude=body.latitude,
        longitude=body.longitude,
        country_code=body.country_code,
    )


@router.get("", summary="List your listings")
async def list_listings(
    seller: SellerDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    page = await ListSellerListings(uow=uow).execute(
        ListSellerListingsQuery(seller_id=seller.id, limit=limit, offset=offset)
    )
    _ = container
    return envelope(
        [_to_response(item) for item in page.items],
        request_id=meta.request_id,
        # `build` derives total_pages / has_next / has_prev; constructing
        # PageMeta directly leaves them unset and fails validation.
        pagination=PageMeta.build(
            page=(page.offset // page.limit) + 1,
            per_page=page.limit,
            total=page.total,
        ),
    )


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a listing",
    dependencies=[Depends(require_permissions("listing:write:self"))],
)
async def create_listing(
    body: ListingWriteRequest,
    seller: SellerDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    result = await CreateListing(
        uow=uow, queue=container.queue, clock=container.clock, ids=container.ids
    ).execute(CreateListingCommand(seller_id=seller.id, data=_to_input(body)))

    return envelope(
        {
            "listing": _to_response(result.listing),
            "job": JobAccepted(
                job_id=result.job_id or "",
                poll_url=f"/api/v1/jobs/{result.job_id}",
            ),
        },
        request_id=meta.request_id,
    )


@router.get("/{listing_id}", summary="Read one of your listings")
async def get_listing(
    listing_id: UUID,
    seller: SellerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    listing = await GetListing(uow=uow).execute(listing_id=listing_id, seller_id=seller.id)
    return envelope(_to_response(listing), request_id=meta.request_id)


@router.put(
    "/{listing_id}",
    summary="Update a listing",
    dependencies=[Depends(require_permissions("listing:write:self"))],
)
async def update_listing(
    listing_id: UUID,
    body: ListingWriteRequest,
    seller: SellerDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    result = await UpdateListing(uow=uow, queue=container.queue, clock=container.clock).execute(
        UpdateListingCommand(seller_id=seller.id, listing_id=listing_id, data=_to_input(body))
    )
    return envelope(
        {
            "listing": _to_response(result.listing),
            # Null when only non-analysed fields changed, so a client can tell
            # "re-analysing" from "saved" without guessing.
            "job": (
                JobAccepted(job_id=result.job_id, poll_url=f"/api/v1/jobs/{result.job_id}")
                if result.job_id
                else None
            ),
        },
        request_id=meta.request_id,
    )


@router.delete(
    "/{listing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a listing",
    dependencies=[Depends(require_permissions("listing:write:self"))],
)
async def delete_listing(
    listing_id: UUID,
    seller: SellerDep,
    container: ContainerDep,
    uow: UowDep,
) -> None:
    await DeleteListing(uow=uow, queue=container.queue, clock=container.clock).execute(
        DeleteListingCommand(seller_id=seller.id, listing_id=listing_id)
    )


@router.post(
    "/{listing_id}/analyse",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-run analysis on a listing",
    dependencies=[Depends(require_permissions("listing:analyse"))],
)
async def analyse_listing(
    listing_id: UUID,
    seller: SellerDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    job_id = await RequestListingAnalysis(uow=uow, queue=container.queue).execute(
        listing_id=listing_id, seller_id=seller.id
    )
    return envelope(
        JobAccepted(job_id=job_id, poll_url=f"/api/v1/jobs/{job_id}"),
        request_id=meta.request_id,
    )


@router.post(
    "/{listing_id}/images",
    status_code=status.HTTP_201_CREATED,
    summary="Add an image to a listing",
    description=(
        "Associates an already-uploaded file (obtained via /files/upload-intent "
        "with purpose=LISTING_IMAGE) with this listing and computes a perceptual "
        "hash for duplicate detection. A warning is returned if a near-identical "
        "image already exists in this seller's listings (Hamming distance ≤ 5)."
    ),
    dependencies=[Depends(require_permissions("listing:write:self"))],
)
async def add_listing_image(
    listing_id: UUID,
    body: ListingImageRequest,
    seller: SellerDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[Any, Any]:
    import hashlib
    from io import BytesIO

    import imagehash
    from PIL import Image

    from trustlens.core.domain.entities import ListingImage
    from trustlens.core.domain.errors import EntityNotFound, ValidationError

    # Ownership check: the listing must belong to this seller.
    listing = await GetListing(uow=uow).execute(listing_id=listing_id, seller_id=seller.id)
    if listing is None:
        raise EntityNotFound("listing", listing_id)

    # Max 5 images per listing.
    count = await uow.listings.count_images(listing_id)
    if count >= 5:
        raise ValidationError("A listing may have at most 5 images.", field="fileId")

    # Validate the file exists and belongs to this user.
    stored_file = await uow.files.get(body.file_id)
    if stored_file is None or stored_file.owner_user_id != seller.user_id:
        raise EntityNotFound("file", body.file_id)
    if stored_file.purpose.value != "LISTING_IMAGE":
        raise ValidationError(
            "File must have been uploaded with purpose=LISTING_IMAGE.", field="fileId"
        )

    # Download the image bytes to compute perceptual hash.
    # This is the only case where bytes pass through the API: the payload is
    # at most 10 MB, the hash computation is CPU-cheap, and the alternative
    # (a separate worker job) would add a round trip for a feature sellers see
    # immediately.
    phash_bytes: bytes | None = None
    sha256_bytes: bytes | None = None
    width: int | None = None
    height: int | None = None
    duplicate_of: str | None = None

    try:
        raw = await container.storage.get(
            bucket=stored_file.bucket,
            object_key=stored_file.object_key,
        )
        sha256_bytes = hashlib.sha256(raw).digest()
        img = Image.open(BytesIO(raw)).convert("RGB")
        width, height = img.size
        phash = imagehash.dhash(img, hash_size=8)
        phash_bytes = phash.hash.tobytes()

        # Duplicate detection across this seller's images.
        dupe = await uow.listings.find_near_duplicate_hash(
            phash_bytes,
            seller_id=seller.id,
        )
        if dupe is not None:
            duplicate_of = str(dupe.id)
    except Exception:
        # Hash failure is non-fatal: the image is still stored and associated.
        # The hash column stays None, and find_near_duplicate_hash skips None rows.
        log.warning("listing_image_hash_failed", listing_id=str(listing_id), exc_info=True)

    now = container.clock.now()
    image = ListingImage(
        id=container.ids.new(),
        listing_id=listing_id,
        file_id=body.file_id,
        position=count,  # append to end
        created_at=now,
        width=width,
        height=height,
        perceptual_hash=phash_bytes,
        sha256=sha256_bytes,
        is_primary=(count == 0),
    )
    await uow.listings.create_image(image)
    await uow.commit()

    return envelope(
        {
            "imageId": str(image.id),
            "position": image.position,
            "isPrimary": image.is_primary,
            "width": width,
            "height": height,
            "isDuplicate": duplicate_of is not None,
            "duplicateOf": duplicate_of,
        },
        request_id=meta.request_id,
    )


@router.get(
    "/{listing_id}/images",
    summary="List images for a listing",
    dependencies=[Depends(require_permissions("listing:write:self"))],
)
async def list_listing_images(
    listing_id: UUID,
    seller: SellerDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[Any, Any]:
    from trustlens.core.domain.errors import EntityNotFound

    listing = await GetListing(uow=uow).execute(listing_id=listing_id, seller_id=seller.id)
    if listing is None:
        raise EntityNotFound("listing", listing_id)

    images = await uow.listings.list_images(listing_id)
    ttl = container.settings.storage.storage_presign_ttl_seconds

    result = []
    for img in images:
        stored = await uow.files.get(img.file_id)
        url = None
        if stored:
            url = await container.storage.presign_download(
                bucket=stored.bucket,
                object_key=stored.object_key,
                ttl_seconds=ttl,
            )
        result.append(
            {
                "imageId": str(img.id),
                "position": img.position,
                "isPrimary": img.is_primary,
                "width": img.width,
                "height": img.height,
                "url": url,
            }
        )

    return envelope(result, request_id=meta.request_id)


__all__ = ["router"]
