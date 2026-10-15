"""A human approval must clear a real-OCR "unreadable" front document.

Real OCR can fail on a genuine card (glare, blur, layout). Once a reviewer has
inspected the images and approved, the CNIC front must stop scoring as
"could not be read". A rejection must leave the document untouched.
"""

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
    IdentityDocument,
    IdentityVerification,
    ReviewCase,
    SellerProfile,
)
from trustlens.core.domain.enums import (
    DocumentType,
    ReviewCaseType,
    ReviewStatus,
    VerificationStatus,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("approve", [True, False])
async def test_approval_marks_unreadable_front_verified(approve: bool) -> None:
    now = datetime.now(UTC)
    seller_id, verification_id, front_id = UUID(int=1), UUID(int=2), UUID(int=3)
    front = IdentityDocument(
        id=front_id, seller_id=seller_id, document_type=DocumentType.CNIC_FRONT,
        file_id=UUID(int=4), status=VerificationStatus.FAILED, created_at=now,
    )
    back = IdentityDocument(
        id=UUID(int=5), seller_id=seller_id, document_type=DocumentType.CNIC_BACK,
        file_id=UUID(int=6), status=VerificationStatus.FAILED, created_at=now,
    )
    verification = IdentityVerification(
        id=verification_id, seller_id=seller_id, decision=VerificationStatus.PENDING,
        created_at=now, front_document_id=front_id,
    )
    seller = SellerProfile(
        id=seller_id, user_id=UUID(int=7), handle="synthetic", display_name="Synthetic",
        account_opened_at=now, created_at=now, identity_status=VerificationStatus.PENDING,
    )
    case = ReviewCase(
        id=UUID(int=8), seller_id=seller_id, case_type=ReviewCaseType.IDENTITY_REVIEW,
        status=ReviewStatus.QUEUED, created_at=now,
        related_entity_type="identity_verifications", related_entity_id=verification_id,
    )
    updated_documents: list[IdentityDocument] = []

    class Repo:
        def __init__(self, name: str) -> None:
            self.name = name

        async def get(self, _id: UUID) -> Any:
            return {"review_cases": case, "sellers": seller}[self.name]

        async def update(self, value: Any) -> Any:
            return value

        async def get_latest_verification_by_id(self, _id: UUID) -> Any:
            return verification

        async def update_verification(self, value: Any) -> Any:
            return value

        async def list_documents(self, _seller_id: UUID) -> list[IdentityDocument]:
            return [front, back]

        async def update_document(self, value: IdentityDocument) -> IdentityDocument:
            updated_documents.append(value)
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
        uow=cast(Any, UnitOfWork()), queue=cast(Any, Queue()),
        clock=cast(Any, SimpleNamespace(now=lambda: now)),
        ids=cast(Any, SimpleNamespace(new=lambda: UUID(int=9))),
    ).execute(
        DecideReviewCaseCommand(
            case_id=case.id, reviewer_id=UUID(int=10), approve=approve,
            note="Synthetic reviewer note for a test-only case.",
        )
    )

    if approve:
        # Only the front document named by this verification is changed.
        assert [d.id for d in updated_documents] == [front_id]
        assert updated_documents[0].status == VerificationStatus.VERIFIED
    else:
        assert updated_documents == []
