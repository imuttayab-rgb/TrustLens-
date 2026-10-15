"""The human verdict must update the score's authoritative verification row."""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest

from trustlens.core.application.use_cases.admin.review_queue import (
    DecideReviewCase,
    DecideReviewCaseCommand,
)
from trustlens.core.domain.entities import (
    IdentityVerification,
    Listing,
    ListingAnalysis,
    ReviewCase,
    SellerProfile,
)
from trustlens.core.domain.enums import (
    ListingSource,
    ListingStatus,
    ReviewCaseType,
    ReviewStatus,
    VerificationStatus,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("approve", [True, False])
async def test_review_updates_seller_and_verification(approve: bool) -> None:
    now = datetime.now(UTC)
    seller_id, verification_id, reviewer_id = UUID(int=1), UUID(int=2), UUID(int=3)
    verification = IdentityVerification(
        id=verification_id, seller_id=seller_id,
        decision=VerificationStatus.PENDING, created_at=now,
        raw_result={"hold_id_file_id": str(UUID(int=4))},
    )
    seller = SellerProfile(
        id=seller_id, user_id=UUID(int=5), handle="test-only",
        display_name="Test Only", account_opened_at=now, created_at=now,
        identity_status=VerificationStatus.PENDING,
        phone_status=VerificationStatus.VERIFIED,
        email_status=VerificationStatus.VERIFIED,
    )
    case = ReviewCase(
        id=UUID(int=6), seller_id=seller_id,
        case_type=ReviewCaseType.IDENTITY_REVIEW,
        status=ReviewStatus.QUEUED, created_at=now,
        related_entity_type="identity_verifications",
        related_entity_id=verification_id,
    )
    updates: dict[str, Any] = {}
    queued: list[dict[str, Any]] = []

    class Repo:
        def __init__(self, name: str): self.name = name
        async def get(self, _id: UUID) -> Any:
            return {"review_cases": case, "sellers": seller}[self.name]
        async def get_latest_verification_by_id(self, _id: UUID) -> Any: return verification
        async def update(self, value: Any) -> Any:
            updates[self.name] = value
            return value
        async def update_verification(self, value: Any) -> Any:
            updates["identities"] = value
            return value
        async def list_documents(self, _seller_id: UUID) -> list[Any]: return []
        async def record(self, value: Any) -> None: updates["audit_logs"] = value

    safe_listing = Listing(
        id=UUID(int=8), seller_id=seller_id, title="Synthetic item", description="No real data",
        status=ListingStatus.DRAFT if approve else ListingStatus.ACTIVE,
        # Complete synthetic ad (Post-an-Ad v2): video id, map pin, private address.
        video_file_id=UUID(int=55), latitude=31.5, longitude=74.3,
        address_line="Test address only",
        source=ListingSource.MANUAL, created_at=now,
        latest_analysis=ListingAnalysis(
            id=UUID(int=9), listing_id=UUID(int=8), analyzer_type="test",
            provider="synthetic", model_name="test", risk_score=3,
            confidence=1.0, analysed_at=now,
        ),
    )

    class Listings:
        async def list_for_seller(self, _seller_id: UUID, *, limit: int, offset: int) -> list[Any]:
            return [safe_listing] if offset == 0 else []

        async def get(self, _listing_id: UUID) -> Listing:
            return safe_listing

        async def count_images(self, _listing_id: UUID) -> int:
            return 1

        async def set_publication_status_if_current(self, *_: Any, **kwargs: Any) -> bool:
            updates["publication"] = kwargs["to_status"]
            return True

    class UnitOfWork:
        review_cases = Repo("review_cases")
        sellers = Repo("sellers")
        identities = Repo("identities")
        audit_logs = Repo("audit_logs")
        listings = Listings()
        async def __aenter__(self) -> UnitOfWork: return self
        async def __aexit__(self, *_: Any) -> None: pass
        async def commit(self) -> None: updates["committed"] = True

    class Queue:
        async def enqueue(self, name: str, **kwargs: Any) -> None:
            queued.append({"name": name, **kwargs})

    result = await DecideReviewCase(
        uow=cast(Any, UnitOfWork()), queue=cast(Any, Queue()),
        clock=cast(Any, SimpleNamespace(now=lambda: now)),
        ids=cast(Any, SimpleNamespace(new=lambda: UUID(int=7))),
    ).execute(DecideReviewCaseCommand(case.id, reviewer_id, approve, "Reviewed four images"))

    expected = VerificationStatus.VERIFIED if approve else VerificationStatus.REJECTED
    assert result.identity_updated
    assert updates["sellers"].identity_status is expected
    assert updates["identities"].decision is expected
    assert updates["identities"].decision_source == "MANUAL"
    assert updates["identities"].decided_by == reviewer_id
    assert updates["identities"].raw_result == verification.raw_result
    assert updates["publication"] is (
        ListingStatus.ACTIVE if approve else ListingStatus.DRAFT
    )
    assert updates["committed"]
    assert queued == [{
        "name": "scoring.recompute_trust_score", "seller_id": str(seller_id),
        "trigger": "MANUAL",
    }]
