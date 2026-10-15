"""Server-enforced prerequisites for publishing a seller's listings.

A Trust Score is *not* an identity certificate: it may be normalized over partial
signals, and a new seller cannot yet earn listing/age evidence. Publication is
instead controlled by the explicit verification states and the listing's own
analysis result. This module never trusts a frontend badge or score.
"""

from __future__ import annotations

from datetime import datetime

from trustlens.core.catalogue import media_policy, required_category_details
from trustlens.core.domain.entities import Listing, SellerProfile
from trustlens.core.domain.enums import ListingStatus
from trustlens.core.domain.ports import UnitOfWork

SAFE_LISTING_RISK_LIMIT = 60.0


def seller_can_publish(seller: SellerProfile) -> bool:
    """All three contact/identity steps and the absence of a fraud flag are required.

    In the local FYP environment OTP/OCR adapters may still be demo adapters;
    a VERIFIED state here means the configured workflow finished, *not* that a
    government issuer or a telecom network attested to the person.
    """
    return seller.is_fully_verified and not seller.is_flagged and seller.deleted_at is None


#: Post-an-Ad v2: what a NEW publication needs so a buyer can recognise the
#: exact item. Kept as stable machine codes; the seller UI words them.
MEDIA_PHOTO = "photo"
MEDIA_VIDEO = "video"
MEDIA_LOCATION = "location"


def listing_media_missing(listing: Listing, image_count: int) -> list[str]:
    """Return which of photo / video / location a listing still lacks.

    Rule (server-enforced, not just a form check): at least one photo, one
    short product video, and a full address that was placed on the map
    (latitude + longitude + the private address line). Photos stay capped at
    ten by the image endpoint; there is deliberately no minimum above one.

    Only used when a listing is about to BECOME public (analysis result or
    draft release). Listings that were already ACTIVE before this rule are
    not taken down retroactively, so existing demo ads keep working.
    """
    missing: list[str] = []
    # Services/jobs do not claim to be physical goods. Identity, name, photo,
    # account eligibility, abuse analysis and attached-photo protection STILL apply.
    if media_policy(listing.category_node_id) in {'service', 'job', 'transfer'}:
        if not (listing.city or '').strip():
            missing.append(MEDIA_LOCATION)
        if required_category_details(listing.category_node_id, listing.category_data):
            missing.append('category_details')
        return missing
    if required_category_details(listing.category_node_id, listing.category_data):
        missing.append('category_details')
    if image_count < 1:
        missing.append(MEDIA_PHOTO)
    if listing.video_file_id is None:
        missing.append(MEDIA_VIDEO)
    if (
        listing.latitude is None
        or listing.longitude is None
        or not (listing.address_line or "").strip()
    ):
        missing.append(MEDIA_LOCATION)
    return missing


async def sync_listing_publication(
    uow: UnitOfWork, seller: SellerProfile, *, now: datetime
) -> tuple[int, int]:
    """Release analysed, safe drafts; take ACTIVE listings off sale on revocation.

    Call inside the SAME database transaction that changes a verification
    status. A draft is promoted only when a completed analysis exists and its
    measured risk is below the worker's scam threshold. FLAGGED, REMOVED,
    RESERVED and SOLD are never auto-promoted or rewritten. Pagination bounds
    memory while allowing sellers with more than one page of drafts to finish.
    Public SQL queries additionally enforce this policy at read time, so even
    a race or a legacy ACTIVE row cannot be shown to buyers.
    """
    publish = seller_can_publish(seller)
    released = withheld = 0
    offset = 0
    page_size = 100
    while True:
        page = await uow.listings.list_for_seller(seller.id, limit=page_size, offset=offset)
        for listing in page:
            if not publish and listing.status == ListingStatus.ACTIVE:
                # The list projection does not include latest_analysis. Read
                # the full entity before the guarded status-only update.
                current = await uow.listings.get(listing.id)
                if current is not None and current.status == ListingStatus.ACTIVE:
                    changed = await uow.listings.set_publication_status_if_current(
                        current.id,
                        from_status=ListingStatus.ACTIVE,
                        to_status=ListingStatus.DRAFT,
                        expected_version=current.version,
                        expected_analysis_id=(
                            current.latest_analysis.id if current.latest_analysis else None
                        ),
                        at=now,
                    )
                    withheld += int(changed)
            elif publish and listing.status == ListingStatus.DRAFT:
                # list_for_seller doesn't hydrate the analysis; get() does.
                current = await uow.listings.get(listing.id)
                if (
                    current is not None
                    and current.status == ListingStatus.DRAFT
                    and current.latest_analysis is not None
                    and current.latest_analysis.risk_score < SAFE_LISTING_RISK_LIMIT
                    # A verified seller's draft still needs its photo, video
                    # and map location before it can be released to buyers.
                    and not listing_media_missing(
                        current, await uow.listings.count_images(current.id)
                    )
                ):
                    changed = await uow.listings.set_publication_status_if_current(
                        current.id,
                        from_status=ListingStatus.DRAFT,
                        to_status=ListingStatus.ACTIVE,
                        expected_version=current.version,
                        expected_analysis_id=current.latest_analysis.id,
                        at=now,
                    )
                    released += int(changed)
        if len(page) < page_size:
            break
        offset += page_size
    return released, withheld


__all__ = [
    "MEDIA_LOCATION",
    "MEDIA_PHOTO",
    "MEDIA_VIDEO",
    "SAFE_LISTING_RISK_LIMIT",
    "listing_media_missing",
    "seller_can_publish",
    "sync_listing_publication",
]
