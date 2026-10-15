"""Private-draft/publication lifecycle tests; no real account or ID media."""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import pytest

from trustlens.core.application.services.listing_publication import (
    listing_media_missing,
    seller_can_publish,
    sync_listing_publication,
)
from trustlens.core.domain.entities import Listing, ListingAnalysis, SellerProfile
from trustlens.core.domain.enums import ListingSource, ListingStatus, VerificationStatus

NOW = datetime(2026, 10, 1, tzinfo=UTC)


def seller(**changes: Any) -> SellerProfile:
    base = SellerProfile(
        id=UUID(int=1), user_id=UUID(int=2), handle="synthetic-seller",
        display_name="Synthetic", account_opened_at=NOW, created_at=NOW,
        identity_status=VerificationStatus.VERIFIED,
        phone_status=VerificationStatus.VERIFIED,
        email_status=VerificationStatus.VERIFIED,
    )
    return dataclasses.replace(base, **changes)


def listing(number: int, status: ListingStatus, risk: float | None) -> Listing:
    analysis = (
        ListingAnalysis(
            id=UUID(int=10_000 + number), listing_id=UUID(int=number),
            analyzer_type="test", provider="synthetic", model_name="synthetic",
            risk_score=risk, confidence=1.0, analysed_at=NOW,
        )
        if risk is not None else None
    )
    return Listing(
        id=UUID(int=number), seller_id=UUID(int=1), title="Synthetic item",
        description="No real user data", status=status,
        source=ListingSource.MANUAL, created_at=NOW, latest_analysis=analysis,
        # Complete synthetic ad (Post-an-Ad v2): video id, map pin, private address.
        video_file_id=UUID(int=90_000 + number), latitude=31.5, longitude=74.3,
        address_line="Test address only",
    )


class FakeListings:
    def __init__(self, entries: list[Listing]):
        self.entries = {entry.id: entry for entry in entries}
        self.changes: list[tuple[ListingStatus, ListingStatus]] = []
        #: Listings with NO photo; every other synthetic listing has one.
        self.without_photos: set[UUID] = set()

    async def list_for_seller(self, _id: UUID, *, limit: int, offset: int) -> list[Listing]:
        # The SQL list projection has NO hydrated latest_analysis.
        rows = list(self.entries.values())[offset : offset + limit]
        return [dataclasses.replace(row, latest_analysis=None) for row in rows]

    async def get(self, listing_id: UUID) -> Listing | None:
        return self.entries.get(listing_id)

    async def count_images(self, listing_id: UUID) -> int:
        return 0 if listing_id in self.without_photos else 1

    async def set_publication_status_if_current(
        self, listing_id: UUID, *, from_status: ListingStatus, to_status: ListingStatus,
        expected_version: int, expected_analysis_id: UUID | None, at: datetime,
    ) -> bool:
        current = self.entries[listing_id]
        current_analysis_id = current.latest_analysis.id if current.latest_analysis else None
        if (current.status, current.version, current_analysis_id) != (
            from_status, expected_version, expected_analysis_id,
        ):
            return False
        self.changes.append((from_status, to_status))
        self.entries[listing_id] = dataclasses.replace(
            current, status=to_status, updated_at=at, version=current.version + 1,
        )
        return True


@pytest.mark.parametrize("missing", ["identity_status", "phone_status", "email_status"])
def test_each_check_is_mandatory(missing: str) -> None:
    assert not seller_can_publish(seller(**{missing: VerificationStatus.PENDING}))


def test_no_score_threshold_and_flag_blocks() -> None:
    assert seller_can_publish(seller())  # No Trust Score exists yet.
    assert not seller_can_publish(seller(is_flagged=True))
    assert not seller_can_publish(seller(deleted_at=NOW))


@pytest.mark.asyncio
async def test_low_risk_drafts_release_only_after_final_check() -> None:
    repository = FakeListings([
        listing(10, ListingStatus.DRAFT, 20),
        listing(11, ListingStatus.DRAFT, 60),
        listing(12, ListingStatus.DRAFT, None),
        listing(13, ListingStatus.FLAGGED, 20),
        listing(14, ListingStatus.RESERVED, 20),
    ])
    uow = cast(Any, type("Uow", (), {"listings": repository})())
    assert await sync_listing_publication(
        uow, seller(email_status=VerificationStatus.PENDING), now=NOW,
    ) == (0, 0)
    assert await sync_listing_publication(uow, seller(), now=NOW) == (1, 0)
    assert repository.entries[UUID(int=10)].status is ListingStatus.ACTIVE
    assert repository.entries[UUID(int=10)].latest_analysis is not None
    for other in (11, 12, 13, 14):
        assert repository.entries[UUID(int=other)].status is not ListingStatus.ACTIVE
    assert await sync_listing_publication(uow, seller(), now=NOW) == (0, 0)


@pytest.mark.asyncio
async def test_revocation_withholds_active_and_preserves_analysis_for_reapproval() -> None:
    repository = FakeListings([listing(20, ListingStatus.ACTIVE, 17)])
    uow = cast(Any, type("Uow", (), {"listings": repository})())
    assert await sync_listing_publication(
        uow, seller(identity_status=VerificationStatus.REJECTED), now=NOW,
    ) == (0, 1)
    assert repository.entries[UUID(int=20)].latest_analysis is not None
    assert await sync_listing_publication(uow, seller(), now=NOW) == (1, 0)
    assert repository.entries[UUID(int=20)].status is ListingStatus.ACTIVE


@pytest.mark.asyncio
async def test_all_pages_release_and_flagged_seller_stays_private() -> None:
    repository = FakeListings([listing(i, ListingStatus.DRAFT, 4) for i in range(100, 202)])
    uow = cast(Any, type("Uow", (), {"listings": repository})())
    assert await sync_listing_publication(uow, seller(is_flagged=True), now=NOW) == (0, 0)
    assert await sync_listing_publication(uow, seller(), now=NOW) == (102, 0)


def test_media_rule_needs_photo_video_and_full_location() -> None:
    complete = listing(1, ListingStatus.DRAFT, 5)
    assert listing_media_missing(complete, 1) == []
    assert listing_media_missing(complete, 10) == []  # ten is the cap, not a problem
    assert listing_media_missing(complete, 0) == ["photo"]
    assert listing_media_missing(dataclasses.replace(complete, video_file_id=None), 1) == ["video"]
    for field in ("latitude", "longitude", "address_line"):
        assert listing_media_missing(dataclasses.replace(complete, **{field: None}), 1) == [
            "location"
        ]
    assert listing_media_missing(dataclasses.replace(complete, address_line="   "), 1) == [
        "location"
    ]


@pytest.mark.asyncio
async def test_verified_seller_draft_without_media_is_not_released() -> None:
    no_video = dataclasses.replace(listing(30, ListingStatus.DRAFT, 5), video_file_id=None)
    no_pin = dataclasses.replace(listing(31, ListingStatus.DRAFT, 5), latitude=None)
    no_photo = listing(32, ListingStatus.DRAFT, 5)
    complete = listing(33, ListingStatus.DRAFT, 5)
    repository = FakeListings([no_video, no_pin, no_photo, complete])
    repository.without_photos.add(no_photo.id)
    uow = cast(Any, type("Uow", (), {"listings": repository})())
    assert await sync_listing_publication(uow, seller(), now=NOW) == (1, 0)
    assert repository.entries[complete.id].status is ListingStatus.ACTIVE
    for held in (no_video, no_pin, no_photo):
        assert repository.entries[held.id].status is ListingStatus.DRAFT
