"""Business seller verification (feature BUS-01).

Unlike identity verification, there is no automated OCR/face-match step
here - a business registration document always goes straight to a human
reviewer (`ReviewCaseType.BUSINESS_VERIFICATION`). That is a deliberate
simplification, the same reasoning VER-03/04 stayed out of scope for:
parsing and validating a company registration certificate is its own
specialized problem, and staff review is a perfectly adequate bar for
"does this business seem real" without building or buying that pipeline.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from uuid import UUID

from trustlens.core.domain.entities import ReviewCase
from trustlens.core.domain.enums import (
    FilePurpose,
    ReviewCaseType,
    ReviewStatus,
    SellerAccountType,
    VerificationStatus,
)
from trustlens.core.domain.errors import EntityNotFound, InvalidStateError, ValidationError
from trustlens.core.domain.ports import Clock, IdGenerator, UnitOfWork


@dataclass(frozen=True, slots=True)
class SubmitBusinessVerificationCommand:
    seller_id: UUID
    legal_name: str
    registration_number: str
    document_file_id: UUID


@dataclass(frozen=True, slots=True)
class SubmitBusinessVerificationResult:
    status: VerificationStatus


class SubmitBusinessVerification:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(
        self, cmd: SubmitBusinessVerificationCommand
    ) -> SubmitBusinessVerificationResult:
        legal_name = cmd.legal_name.strip()
        registration_number = cmd.registration_number.strip()
        if not legal_name:
            raise ValidationError("Enter the business's registered legal name.", field="legalName")
        if not registration_number:
            raise ValidationError(
                "Enter the business registration or tax number.", field="registrationNumber"
            )

        now = self._clock.now()
        async with self._uow:
            seller = await self._uow.sellers.get(cmd.seller_id)
            if seller is None:
                raise EntityNotFound("seller", cmd.seller_id)
            if seller.account_type != SellerAccountType.BUSINESS:
                raise InvalidStateError("Switch this account to a business account first.")
            if seller.business_verification_status == VerificationStatus.PENDING:
                raise InvalidStateError("A business verification is already pending review.")
            if seller.business_verification_status == VerificationStatus.VERIFIED:
                raise InvalidStateError("This business is already verified.")

            stored = await self._uow.files.get(cmd.document_file_id)
            if stored is None or stored.owner_user_id != seller.user_id:
                raise ValidationError("Uploaded file not found.", field="documentFileId")
            if stored.purpose != FilePurpose.BUSINESS_REGISTRATION:
                raise ValidationError(
                    f"Expected a {FilePurpose.BUSINESS_REGISTRATION.value} upload.",
                    field="documentFileId",
                )

            await self._uow.sellers.update(
                dataclasses.replace(
                    seller,
                    business_legal_name=legal_name,
                    business_registration_number=registration_number,
                    business_document_file_id=cmd.document_file_id,
                    business_verification_status=VerificationStatus.PENDING,
                    updated_at=now,
                )
            )
            await self._uow.review_cases.add(
                ReviewCase(
                    id=self._ids.new(),
                    seller_id=seller.id,
                    case_type=ReviewCaseType.BUSINESS_VERIFICATION,
                    status=ReviewStatus.QUEUED,
                    created_at=now,
                    priority=5,
                    trigger_reason="Business registration submitted for review",
                    related_entity_type="seller_profiles",
                    related_entity_id=seller.id,
                )
            )
            await self._uow.commit()
        return SubmitBusinessVerificationResult(status=VerificationStatus.PENDING)


__all__ = [
    "SubmitBusinessVerification",
    "SubmitBusinessVerificationCommand",
    "SubmitBusinessVerificationResult",
]
