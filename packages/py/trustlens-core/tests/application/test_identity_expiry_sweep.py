"""ID card expiry AFTER verification (backend only).

Covers three rules:

1. Evidence: only REAL OCR expiry dates on the CNIC sides of the LATEST
   verification count; fake/demo OCR and superseded submissions never do.
2. Daily sweep: a VERIFIED seller whose card has since expired becomes
   EXPIRED, their ACTIVE listings return to private drafts, an audit entry
   is written without the date/number, and a rescore is queued.
3. Reviewer guard: a human cannot approve a card real OCR read as expired.

All data is synthetic; no real CNIC, name or face is used.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest

from trustlens.core.application.services.identity_expiry import lapsed_expiry, real_ocr_expiry
from trustlens.core.application.use_cases.admin.review_queue import (
    DecideReviewCase,
    DecideReviewCaseCommand,
)
from trustlens.core.application.use_cases.verification.identity_expiry import (
    ExpireLapsedIdentities,
)
from trustlens.core.domain.entities import (
    IdentityDocument,
    IdentityVerification,
    OcrFields,
    ReviewCase,
    SellerProfile,
)
from trustlens.core.domain.enums import (
    DocumentType,
    ListingStatus,
    ReviewCaseType,
    ReviewStatus,
    VerificationStatus,
)
from trustlens.core.domain.errors import InvalidStateError

NOW = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
TODAY = NOW.date()
SELLER_ID, FRONT_ID, BACK_ID, VERIFICATION_ID = UUID(int=1), UUID(int=2), UUID(int=3), UUID(int=4)


def document(
    doc_id: UUID,
    doc_type: DocumentType,
    *,
    expiry: date | None,
    engine: str | None = "rapidocr",
) -> IdentityDocument:
    return IdentityDocument(
        id=doc_id,
        seller_id=SELLER_ID,
        document_type=doc_type,
        file_id=UUID(int=90 + doc_id.int),
        status=VerificationStatus.VERIFIED,
        created_at=NOW,
        ocr_engine=engine,
        fields=OcrFields(expiry_date=expiry),
    )


def verification(
    decision: VerificationStatus = VerificationStatus.VERIFIED,
) -> IdentityVerification:
    return IdentityVerification(
        id=VERIFICATION_ID,
        seller_id=SELLER_ID,
        decision=decision,
        created_at=NOW,
        front_document_id=FRONT_ID,
        back_document_id=BACK_ID,
    )


def seller(status: VerificationStatus = VerificationStatus.VERIFIED) -> SellerProfile:
    return SellerProfile(
        id=SELLER_ID,
        user_id=UUID(int=7),
        handle="synthetic",
        display_name="Synthetic",
        account_opened_at=NOW,
        created_at=NOW,
        identity_status=status,
        phone_status=VerificationStatus.VERIFIED,
        email_status=VerificationStatus.VERIFIED,
    )


# ── 1. Evidence rules ────────────────────────────────────────────────


class TestEvidence:
    def test_real_ocr_past_expiry_is_lapsed(self) -> None:
        docs = [document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2025, 1, 1))]
        assert lapsed_expiry(verification(), docs, TODAY) == date(2025, 1, 1)

    def test_card_is_valid_through_its_expiry_date(self) -> None:
        docs = [document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=TODAY)]
        assert lapsed_expiry(verification(), docs, TODAY) is None

    def test_future_expiry_is_not_lapsed(self) -> None:
        docs = [document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2031, 3, 15))]
        assert lapsed_expiry(verification(), docs, TODAY) is None

    @pytest.mark.parametrize("engine", ["fake", "demo", None])
    def test_simulated_or_unknown_engine_never_counts(self, engine: str | None) -> None:
        docs = [document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2020, 1, 1), engine=engine)]
        assert lapsed_expiry(verification(), docs, TODAY) is None

    def test_superseded_submission_is_ignored(self) -> None:
        """An old expired card must not revoke a seller who re-verified."""
        old = document(UUID(int=50), DocumentType.CNIC_FRONT, expiry=date(2020, 1, 1))
        new = document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2031, 1, 1))
        assert lapsed_expiry(verification(), [old, new], TODAY) is None

    def test_earliest_of_front_and_back_is_used(self) -> None:
        docs = [
            document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2031, 1, 1)),
            document(BACK_ID, DocumentType.CNIC_BACK, expiry=date(2026, 5, 1)),
        ]
        assert real_ocr_expiry(verification(), docs) == date(2026, 5, 1)

    def test_no_verification_means_no_evidence(self) -> None:
        docs = [document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2020, 1, 1))]
        assert lapsed_expiry(None, docs, TODAY) is None


# ── 2. Daily sweep ───────────────────────────────────────────────────


class SweepWorld:
    """In-memory unit of work holding one synthetic seller and two listings."""

    def __init__(self, *, seller_status: VerificationStatus, docs: list[IdentityDocument]) -> None:
        self.seller = seller(seller_status)
        self.docs = docs
        self.listings = {
            UUID(int=20): SimpleNamespace(
                id=UUID(int=20), status=ListingStatus.ACTIVE, version=3, latest_analysis=None
            ),
            UUID(int=21): SimpleNamespace(
                id=UUID(int=21), status=ListingStatus.SOLD, version=1, latest_analysis=None
            ),
        }
        self.audits: list[Any] = []
        self.enqueued: list[tuple[str, dict[str, Any]]] = []
        self.commits = 0
        world = self

        class Sellers:
            async def get(self, _id: UUID) -> SellerProfile:
                return world.seller

            async def update(self, value: SellerProfile) -> SellerProfile:
                world.seller = value
                return value

        class Identities:
            async def list_verified_sellers_with_lapsed_id(self, **_: Any) -> list[UUID]:
                return [SELLER_ID]  # the SQL pre-filter is tested separately

            async def get_latest_verification(self, _id: UUID) -> IdentityVerification:
                return verification()

            async def list_documents(self, _id: UUID) -> list[IdentityDocument]:
                return world.docs

        class Listings:
            async def list_for_seller(self, *_: Any, **__: Any) -> list[Any]:
                return list(world.listings.values())

            async def get(self, listing_id: UUID) -> Any:
                return world.listings[listing_id]

            async def set_publication_status_if_current(
                self,
                listing_id: UUID,
                *,
                from_status: ListingStatus,
                to_status: ListingStatus,
                **_: Any,
            ) -> bool:
                listing = world.listings[listing_id]
                if listing.status != from_status:
                    return False
                listing.status = to_status
                return True

        class Audits:
            async def record(self, entry: Any) -> None:
                world.audits.append(entry)

        class UnitOfWork:
            sellers = Sellers()
            identities = Identities()
            listings = Listings()
            audit_logs = Audits()

            async def __aenter__(self) -> UnitOfWork:
                return self

            async def __aexit__(self, *_: Any) -> None:
                return None

            async def commit(self) -> None:
                world.commits += 1

        class Queue:
            async def enqueue(self, name: str, **kwargs: Any) -> None:
                world.enqueued.append((name, kwargs))

        self.use_case = ExpireLapsedIdentities(
            uow=cast(Any, UnitOfWork()),
            queue=cast(Any, Queue()),
            clock=cast(Any, SimpleNamespace(now=lambda: NOW)),
            ids=cast(Any, SimpleNamespace(new=lambda: UUID(int=99))),
        )


class TestSweep:
    @pytest.mark.asyncio
    async def test_expired_card_revokes_and_hides_listings(self) -> None:
        world = SweepWorld(
            seller_status=VerificationStatus.VERIFIED,
            docs=[document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2026, 9, 30))],
        )
        result = await world.use_case.execute()

        assert (result.checked, result.expired, result.listings_withheld) == (1, 1, 1)
        assert world.seller.identity_status is VerificationStatus.EXPIRED
        assert world.listings[UUID(int=20)].status is ListingStatus.DRAFT
        assert world.listings[UUID(int=21)].status is ListingStatus.SOLD  # untouched
        assert world.commits == 1
        assert [name for name, _ in world.enqueued] == ["scoring.recompute_trust_score"]
        (audit,) = world.audits
        assert audit.action == "identity.document_expired"
        assert audit.actor_id is None
        # No personal data in the audit trail: no date, number or name.
        assert "2026-09-30" not in repr(audit.after)
        assert audit.after["identity_status"] == "EXPIRED"

    @pytest.mark.asyncio
    async def test_fake_ocr_date_never_revokes(self) -> None:
        world = SweepWorld(
            seller_status=VerificationStatus.VERIFIED,
            docs=[
                document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2020, 1, 1), engine="fake")
            ],
        )
        result = await world.use_case.execute()
        assert result.expired == 0
        assert world.seller.identity_status is VerificationStatus.VERIFIED
        assert world.listings[UUID(int=20)].status is ListingStatus.ACTIVE
        assert world.audits == [] and world.enqueued == [] and world.commits == 0

    @pytest.mark.asyncio
    async def test_seller_no_longer_verified_is_skipped(self) -> None:
        world = SweepWorld(
            seller_status=VerificationStatus.PENDING,
            docs=[document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2020, 1, 1))],
        )
        result = await world.use_case.execute()
        assert result.expired == 0
        assert world.seller.identity_status is VerificationStatus.PENDING

    @pytest.mark.asyncio
    async def test_running_twice_is_idempotent(self) -> None:
        world = SweepWorld(
            seller_status=VerificationStatus.VERIFIED,
            docs=[document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2026, 9, 30))],
        )
        await world.use_case.execute()
        second = await world.use_case.execute()
        assert second.expired == 0
        assert len(world.audits) == 1


# ── 3. Reviewer guard ────────────────────────────────────────────────


async def decide(*, approve: bool, docs: list[IdentityDocument]) -> SellerProfile:
    state = {"seller": seller(VerificationStatus.PENDING)}
    case = ReviewCase(
        id=UUID(int=8),
        seller_id=SELLER_ID,
        case_type=ReviewCaseType.IDENTITY_REVIEW,
        status=ReviewStatus.QUEUED,
        created_at=NOW,
        related_entity_type="identity_verifications",
        related_entity_id=VERIFICATION_ID,
    )

    class Repo:
        def __init__(self, name: str) -> None:
            self.name = name

        async def get(self, _id: UUID) -> Any:
            return case if self.name == "review_cases" else state["seller"]

        async def update(self, value: Any) -> Any:
            if self.name == "sellers":
                state["seller"] = value
            return value

        async def get_latest_verification_by_id(self, _id: UUID) -> IdentityVerification:
            return verification(VerificationStatus.PENDING)

        async def update_verification(self, value: Any) -> Any:
            return value

        async def list_documents(self, _id: UUID) -> list[IdentityDocument]:
            return docs

        async def update_document(self, value: Any) -> Any:
            return value

        async def record(self, _value: Any) -> None:
            return None

    class Listings:
        async def list_for_seller(self, *_: Any, **__: Any) -> list[Any]:
            return []

    class UnitOfWork:
        review_cases = Repo("review_cases")
        sellers = Repo("sellers")
        identities = Repo("identities")
        audit_logs = Repo("audit_logs")
        listings = Listings()

        async def __aenter__(self) -> UnitOfWork:
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def commit(self) -> None:
            return None

    class Queue:
        async def enqueue(self, *_: Any, **__: Any) -> None:
            return None

    await DecideReviewCase(
        uow=cast(Any, UnitOfWork()),
        queue=cast(Any, Queue()),
        clock=cast(Any, SimpleNamespace(now=lambda: NOW)),
        ids=cast(Any, SimpleNamespace(new=lambda: UUID(int=9))),
    ).execute(
        DecideReviewCaseCommand(
            case_id=case.id,
            reviewer_id=UUID(int=10),
            approve=approve,
            note="Synthetic reviewer note for a test-only case.",
        )
    )
    return state["seller"]


class TestReviewerGuard:
    @pytest.mark.asyncio
    async def test_cannot_approve_real_ocr_expired_card(self) -> None:
        docs = [document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2025, 1, 1))]
        with pytest.raises(InvalidStateError, match="expired"):
            await decide(approve=True, docs=docs)

    @pytest.mark.asyncio
    async def test_can_reject_real_ocr_expired_card(self) -> None:
        docs = [document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2025, 1, 1))]
        result = await decide(approve=False, docs=docs)
        assert result.identity_status is VerificationStatus.REJECTED

    @pytest.mark.asyncio
    async def test_fake_ocr_date_does_not_block_approval(self) -> None:
        docs = [document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2020, 1, 1), engine="fake")]
        result = await decide(approve=True, docs=docs)
        assert result.identity_status is VerificationStatus.VERIFIED

    @pytest.mark.asyncio
    async def test_valid_card_can_be_approved(self) -> None:
        docs = [document(FRONT_ID, DocumentType.CNIC_FRONT, expiry=date(2031, 1, 1))]
        result = await decide(approve=True, docs=docs)
        assert result.identity_status is VerificationStatus.VERIFIED
