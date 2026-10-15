"""Listing-analysis publication tests using synthetic sellers and no external AI calls."""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest

from trustlens.core.domain.entities import Listing, SellerProfile
from trustlens.core.domain.enums import ListingSource, ListingStatus, VerificationStatus
from trustlens_worker.jobs.listings import analyse_listing

NOW = datetime(2026, 10, 1, tzinfo=UTC)

#: A COMPLETE synthetic ad for the Post-an-Ad v2 rule: one video file id, a
#: map pin and a private address (no real media or address is used).
COMPLETE_AD: dict[str, Any] = {
    "video_file_id": UUID(int=77),
    "latitude": 31.47,
    "longitude": 74.41,
    "address_line": "Test House 1, Sample Street, Lahore",
}


def seller(verified: bool, *, flagged: bool = False) -> SellerProfile:
    return SellerProfile(
        id=UUID(int=2), user_id=UUID(int=3), handle="demo-synthetic",
        display_name="Synthetic", account_opened_at=NOW, created_at=NOW,
        identity_status=VerificationStatus.VERIFIED if verified else VerificationStatus.PENDING,
        phone_status=VerificationStatus.VERIFIED,
        email_status=VerificationStatus.VERIFIED,
        is_flagged=flagged,
    )


class FakeListings:
    def __init__(self, listing: Listing, image_count: int = 1):
        self.listing = listing
        self.image_count = image_count
        self.latest_analysis: Any = None
        self.was_rolled_back = False
        self.reject_stale = False

    async def get(self, _id: UUID) -> Listing:
        return self.listing

    async def count_images(self, _id: UUID) -> int:
        return self.image_count

    async def category_median_price(self, *_: Any, **__: Any) -> None:
        return None

    async def add_analysis(self, analysis: Any) -> Any:
        self.latest_analysis = analysis
        return analysis

    async def set_publication_status_if_current(
        self, _id: UUID, *, from_status: ListingStatus, to_status: ListingStatus,
        expected_version: int, expected_analysis_id: UUID | None, at: datetime,
    ) -> bool:
        assert self.listing.status is from_status
        assert self.listing.version == expected_version
        assert self.latest_analysis.id == expected_analysis_id
        if self.reject_stale:
            return False
        self.listing = dataclasses.replace(
            self.listing, status=to_status, latest_analysis=self.latest_analysis,
        )
        return True


class FakeUow:
    def __init__(self, listing: Listing, profile: SellerProfile):
        self.listings = FakeListings(listing)
        self.sellers = SimpleNamespace(get=self._get_seller)
        self.profile = profile
        self.committed = False

    async def _get_seller(self, _id: UUID) -> SellerProfile:
        return self.profile

    async def __aenter__(self) -> FakeUow:
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.listings.was_rolled_back = True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("verified", "flagged", "risk", "expected"),
    [
        (False, False, 8, ListingStatus.DRAFT),
        (True, True, 8, ListingStatus.DRAFT),
        (True, False, 8, ListingStatus.ACTIVE),
        (True, False, 60, ListingStatus.FLAGGED),
        (False, False, 60, ListingStatus.FLAGGED),
    ],
)
async def test_worker_requires_both_seller_checks_and_low_listing_risk(
    verified: bool, flagged: bool, risk: int, expected: ListingStatus
) -> None:
    item = Listing(
        id=UUID(int=1), seller_id=UUID(int=2), title="Synthetic test item",
        description="No real photos", status=ListingStatus.ANALYSING,
        source=ListingSource.MANUAL, created_at=NOW, **COMPLETE_AD,
    )
    uow = FakeUow(item, seller(verified, flagged=flagged))
    queued: list[str] = []

    async def analyze_listing_(*_: Any, **__: Any) -> Any:
        return SimpleNamespace(
            risk_score=risk, provider="synthetic", model_name="test", model_version="1",
            prompt_version="1", confidence=0.91, labels=(), findings={}, summary="test",
            raw={}, input_tokens=0, output_tokens=0, latency_ms=0, cost_usd=0.0,
        )

    async def predict(*_: Any, **__: Any) -> Any:
        return SimpleNamespace(scam_probability=0, model_version="1", label="safe")

    async def enqueue(name: str, **_: Any) -> None:
        queued.append(name)

    ctx = {
        "uow": lambda: uow,
        "clock": SimpleNamespace(now=lambda: NOW),
        "ids": SimpleNamespace(new=lambda: UUID(int=4)),
        "llm": SimpleNamespace(analyze_listing=analyze_listing_),
        "classifier": SimpleNamespace(predict=predict),
        "queue": SimpleNamespace(enqueue=enqueue),
    }
    await analyse_listing(cast(Any, ctx), listing_id=str(item.id))
    assert uow.listings.listing.status is expected
    assert uow.committed
    assert queued == ["scoring.recompute_trust_score"]


@pytest.mark.asyncio
async def test_stale_worker_result_rolls_back_instead_of_publishing() -> None:
    item = Listing(
        id=UUID(int=1), seller_id=UUID(int=2), title="Synthetic item",
        description="No real data", status=ListingStatus.ANALYSING,
        source=ListingSource.MANUAL, created_at=NOW,
    )
    uow = FakeUow(item, seller(True))
    uow.listings.reject_stale = True

    async def analyze_listing_(*_: Any, **__: Any) -> Any:
        return SimpleNamespace(
            risk_score=0, provider="synthetic", model_name="test", model_version="1",
            prompt_version="1", confidence=0.9, labels=(), findings={}, summary="test",
            raw={}, input_tokens=0, output_tokens=0, latency_ms=0, cost_usd=0.0,
        )

    async def predict(*_: Any, **__: Any) -> Any:
        return SimpleNamespace(scam_probability=0, model_version="1", label="safe")

    result = await analyse_listing(cast(Any, {
        "uow": lambda: uow,
        "clock": SimpleNamespace(now=lambda: NOW),
        "ids": SimpleNamespace(new=lambda: UUID(int=4)),
        "llm": SimpleNamespace(analyze_listing=analyze_listing_),
        "classifier": SimpleNamespace(predict=predict),
    }), listing_id=str(item.id))
    assert result == {"skipped": "listing changed during analysis"}
    assert uow.listings.was_rolled_back
    assert not uow.committed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("drop", "images"),
    [
        ("video_file_id", 1),   # no product video
        ("latitude", 1),        # never placed on the map
        ("address_line", 1),    # no full address typed
        (None, 0),              # no photo at all
    ],
)
async def test_verified_seller_incomplete_ad_stays_private(drop: str | None, images: int) -> None:
    """Post-an-Ad v2: photo + video + map location are required to go live."""
    fields = dict(COMPLETE_AD)
    if drop is not None:
        fields[drop] = None
    item = Listing(
        id=UUID(int=1), seller_id=UUID(int=2), title="Synthetic test item",
        description="No real photos", status=ListingStatus.ANALYSING,
        source=ListingSource.MANUAL, created_at=NOW, **fields,
    )
    uow = FakeUow(item, seller(True))
    uow.listings.image_count = images

    async def analyze_listing_(*_: Any, **__: Any) -> Any:
        return SimpleNamespace(
            risk_score=5, provider="synthetic", model_name="test", model_version="1",
            prompt_version="1", confidence=0.9, labels=(), findings={}, summary="test",
            raw={}, input_tokens=0, output_tokens=0, latency_ms=0, cost_usd=0.0,
        )

    async def predict(*_: Any, **__: Any) -> Any:
        return SimpleNamespace(scam_probability=0, model_version="1", label="safe")

    async def enqueue(*_: Any, **__: Any) -> None:
        return None

    await analyse_listing(cast(Any, {
        "uow": lambda: uow,
        "clock": SimpleNamespace(now=lambda: NOW),
        "ids": SimpleNamespace(new=lambda: UUID(int=4)),
        "llm": SimpleNamespace(analyze_listing=analyze_listing_),
        "classifier": SimpleNamespace(predict=predict),
        "queue": SimpleNamespace(enqueue=enqueue),
    }), listing_id=str(item.id))
    assert uow.listings.listing.status is ListingStatus.DRAFT
