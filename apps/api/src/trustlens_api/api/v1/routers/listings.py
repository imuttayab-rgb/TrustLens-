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

#: Spec asks for 1-10, not the previous hard-coded 5 (LST-01).
MAX_LISTING_IMAGES = 10


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
        category_node_id=listing.category_node_id,
        category_schema_version=listing.category_schema_version,
        category_data=listing.category_data,
        show_phone=listing.show_phone,
        condition=listing.condition,
        city=listing.city,
        area=listing.area,
        address_line=listing.address_line,
        latitude=listing.latitude,
        longitude=listing.longitude,
        country_code=listing.country_code,
        negotiable=listing.negotiable,
        attributes=listing.attributes,
        video_file_id=listing.video_file_id,
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
        category_node_id=body.category_node_id,
        show_phone=body.show_phone,
        condition=body.condition,
        city=body.city,
        area=body.area,
        address_line=body.address_line,
        latitude=body.latitude,
        longitude=body.longitude,
        country_code=body.country_code,
        negotiable=body.negotiable,
        attributes=body.attributes,
        video_file_id=body.video_file_id,
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
        "Checks an owned upload against other accounts' indexed photos before "
        "attaching an immutable copy. Failed/busy checks do not attach the photo."
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
    from dataclasses import replace

    from anyio import to_thread

    from trustlens.core.domain.entities import ListingImage
    from trustlens.core.domain.errors import ConflictError, EntityNotFound, ValidationError
    from trustlens.db.photo_guard import PhotoIndex
    from trustlens_api.modules.photos.guard import prepare_photo, visually_matches

    listing = await GetListing(uow=uow).execute(listing_id=listing_id, seller_id=seller.id)
    if listing is None:
        raise EntityNotFound("listing", listing_id)
    stored_file = await uow.files.get(body.file_id)
    if stored_file is None or stored_file.owner_user_id != seller.user_id:
        raise EntityNotFound("file", body.file_id)
    if stored_file.purpose.value != "LISTING_IMAGE":
        raise ValidationError("Choose a listing photo.", field="fileId")

    index = PhotoIndex(uow.session)
    # A PostgreSQL transaction lock bounds processing across API processes and
    # closes the simultaneous-upload race. Taken BEFORE downloading any bytes.
    await index.lock()
    await index.require_ready()
    listing = await uow.listings.lock_owned_for_media(listing_id, seller.id)
    count = await uow.listings.count_images(listing_id)
    if count >= MAX_LISTING_IMAGES:
        raise ValidationError(
            f"An ad can have at most {MAX_LISTING_IMAGES} photos.", field="fileId"
        )
    raw = await container.storage.get(bucket=stored_file.bucket, object_key=stored_file.object_key)
    try:
        prepared = await to_thread.run_sync(prepare_photo, raw)
    except (ValueError, OSError) as exc:
        raise ValidationError(
            str(exc)
            if isinstance(exc, ValueError)
            else "This image could not be read. Choose a JPEG, PNG or WebP photo.",
            field="fileId",
        ) from None
    del raw
    if await index.exact_match(seller.user_id, prepared.digests):
        raise ConflictError(
            "This photo is already attached to another account's ad. "
            "Use your own original photo of the item.",
            details={"reason": "PHOTO_ALREADY_USED", "field": "fileId"},
        )
    candidates = await index.candidates(seller.user_id, prepared.bands)
    matched = await to_thread.run_sync(
        lambda: any(visually_matches(prepared.fingerprint, candidate) for candidate in candidates)
    )
    if matched:
        raise ConflictError(
            "This photo closely matches one used by another account and was not attached. "
            "Take a fresh photo of your item from a different angle. "
            "A visual match does not establish who owns the original.",
            details={"reason": "PHOTO_SIMILAR", "field": "fileId"},
        )

    # Never serve a mutable upload target: its presigned PUT may still be valid.
    # A fresh server-only key is written once; no upload URL is issued for it.
    now = container.clock.now()
    frozen_id = container.ids.new()
    frozen_key = f"listing_checked/{seller.user_id}/{frozen_id}.jpg"
    thumbnail_key = frozen_key + "_thumb.jpg"
    await container.storage.put(
        bucket=stored_file.bucket,
        object_key=frozen_key,
        data=prepared.jpeg,
        content_type="image/jpeg",
        # Public listing asset; keep private-document storage defaults intact.
        server_side_encryption=False,
    )
    await container.storage.put(
        bucket=stored_file.bucket,
        object_key=thumbnail_key,
        data=prepared.thumbnail,
        content_type="image/jpeg",
        # Public listing asset; keep private-document storage defaults intact.
        server_side_encryption=False,
    )
    frozen = replace(
        stored_file,
        id=frozen_id,
        object_key=frozen_key,
        mime_type="image/jpeg",
        size_bytes=len(prepared.jpeg),
        sha256=hashlib.sha256(prepared.jpeg).digest(),
        width=prepared.width,
        height=prepared.height,
        created_at=now,
    )
    await uow.files.add(frozen)
    image = ListingImage(
        id=container.ids.new(),
        listing_id=listing_id,
        file_id=frozen_id,
        position=count,
        created_at=now,
        width=prepared.width,
        height=prepared.height,
        perceptual_hash=prepared.legacy_dhash,
        sha256=frozen.sha256,
        is_primary=count == 0,
        thumbnail_object_key=thumbnail_key,
    )
    await uow.listings.create_image(image)
    await index.add(image.id, seller.user_id, prepared)
    await uow.commit()
    return envelope(
        {
            "imageId": str(image.id),
            "position": image.position,
            "isPrimary": image.is_primary,
            "width": image.width,
            "height": image.height,
            "isDuplicate": False,
            "duplicateOf": None,
            "photoCheck": "CLEAR",
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
        thumbnail_url = None
        if stored:
            url = await container.storage.presign_download(
                bucket=stored.bucket,
                object_key=stored.object_key,
                ttl_seconds=ttl,
            )
            if img.thumbnail_object_key:
                thumbnail_url = await container.storage.presign_download(
                    bucket=stored.bucket,
                    object_key=img.thumbnail_object_key,
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
                "thumbnailUrl": thumbnail_url,
            }
        )

    return envelope(result, request_id=meta.request_id)


__all__ = ["router"]


class ImageOrderRequest(Schema):
    image_ids: list[UUID] = Field(min_length=1, max_length=10)


@router.put('/{listing_id}/images/order', dependencies=[Depends(require_permissions('listing:write:self'))])
async def order_listing_images(listing_id: UUID, body: ImageOrderRequest, seller: SellerDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    await uow.listings.edit_images(listing_id, seller.id, order=body.image_ids)
    await uow.commit()
    return envelope({'saved': True}, request_id=meta.request_id)


@router.delete('/{listing_id}/images/{image_id}', dependencies=[Depends(require_permissions('listing:write:self'))])
async def remove_listing_image(listing_id: UUID, image_id: UUID, seller: SellerDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    await uow.listings.edit_images(listing_id, seller.id, remove_id=image_id)
    await uow.commit()
    return envelope({'removed': True, 'reanalysisRequired': True}, request_id=meta.request_id)
