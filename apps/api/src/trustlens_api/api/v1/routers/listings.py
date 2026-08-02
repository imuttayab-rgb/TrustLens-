"""Listing endpoints (feature F5).

Ownership is enforced in the use cases, not here: a route-level permission
answers "may a seller manage listings", never "may this seller touch THIS
listing". Conflating the two is how IDOR gets shipped.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

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
from trustlens_api.api.deps import ContainerDep, MetaDep, SellerDep, UowDep, require_permissions
from trustlens_api.api.v1.schemas.common import JobAccepted, PageMeta, envelope
from trustlens_api.api.v1.schemas.listing import (
    ListingAnalysisResponse,
    ListingResponse,
    ListingWriteRequest,
)

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


__all__ = ["router"]
