"""Identity verification use cases (feature F1: CNIC OCR + face match).

The submit path is deliberately fast and asynchronous: it validates, records
PENDING rows and enqueues a job, returning in ~50 ms. OCR and face matching
take 15-30 seconds and carry ~2.5 GB of ML dependencies, so they run in the
worker (ADR-0003).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from trustlens.core.application.services.listing_publication import sync_listing_publication
from trustlens.core.domain.entities import (
    IdentityDocument,
    IdentityVerification,
    SellerProfile,
)
from trustlens.core.domain.enums import (
    ConsentType,
    DocumentType,
    FilePurpose,
    ReviewCaseType,
    ReviewStatus,
    VerificationStatus,
)
from trustlens.core.domain.errors import (
    ConsentRequired,
    EntityNotFound,
    InvalidStateError,
    ValidationError,
)
from trustlens.core.domain.events import (
    DuplicateIdentityDetected,
    IdentityRejected,
    IdentitySubmitted,
    IdentityVerified,
)
from trustlens.core.domain.ports import Clock, IdGenerator, JobQueue, UnitOfWork

#: Files must be uploaded (via a presigned URL) before this call, and each
#: must carry the purpose it is being submitted as - a client cannot pass a
#: listing image as a CNIC.
_REQUIRED_PURPOSES: dict[str, FilePurpose] = {
    "cnic_front_file_id": FilePurpose.CNIC_FRONT,
    "cnic_back_file_id": FilePurpose.CNIC_BACK,
    "selfie_file_id": FilePurpose.SELFIE,
}


@dataclass(frozen=True, slots=True)
class SubmitIdentityCommand:
    seller_id: UUID
    cnic_front_file_id: UUID
    cnic_back_file_id: UUID
    selfie_file_id: UUID
    hold_id_file_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class SubmitIdentityResult:
    verification_id: UUID
    job_id: str
    status: VerificationStatus


class SubmitIdentityDocuments:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        queue: JobQueue,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._uow = uow
        self._queue = queue
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: SubmitIdentityCommand) -> SubmitIdentityResult:
        now = self._clock.now()

        async with self._uow:
            seller = await self._uow.sellers.get(cmd.seller_id)
            if seller is None:
                raise EntityNotFound("seller", cmd.seller_id)

            # Biometric consent gate. Comparing a face against a national ID
            # photo is biometric processing; doing it without recorded,
            # versioned consent is not acceptable regardless of jurisdiction.
            if not await self._uow.consents.has_granted(
                seller.user_id, consent_type=ConsentType.BIOMETRIC_PROCESSING.value
            ):
                raise ConsentRequired(ConsentType.BIOMETRIC_PROCESSING.value)

            if seller.identity_status == VerificationStatus.PROCESSING:
                raise InvalidStateError("An identity check is already running for this account.")
            if seller.identity_status == VerificationStatus.VERIFIED:
                raise InvalidStateError("This account's identity is already verified.")

            files = await self._validate_files(cmd, seller.user_id)

            documents = [
                await self._uow.identities.add_document(
                    IdentityDocument(
                        id=self._ids.new(),
                        seller_id=cmd.seller_id,
                        document_type=doc_type,
                        file_id=file_id,
                        status=VerificationStatus.PENDING,
                        created_at=now,
                    )
                )
                for doc_type, file_id in (
                    (DocumentType.CNIC_FRONT, cmd.cnic_front_file_id),
                    (DocumentType.CNIC_BACK, cmd.cnic_back_file_id),
                    (DocumentType.SELFIE, cmd.selfie_file_id),
                )
            ]
            front, back, selfie = documents

            verification = await self._uow.identities.add_verification(
                IdentityVerification(
                    id=self._ids.new(),
                    seller_id=cmd.seller_id,
                    decision=VerificationStatus.PROCESSING,
                    created_at=now,
                    front_document_id=front.id,
                    back_document_id=back.id,
                    selfie_document_id=selfie.id,
                    # The optional fourth image has no OCR/document record. The
                    # private JSONB metadata binds it to this exact attempt;
                    # user ownership and purpose are validated below first.
                    raw_result=(
                        {"hold_id_file_id": str(cmd.hold_id_file_id)}
                        if cmd.hold_id_file_id is not None else {}
                    ),
                )
            )

            await self._uow.sellers.update(
                dataclasses.replace(
                    seller, identity_status=VerificationStatus.PROCESSING, updated_at=now
                )
            )
            await self._uow.publish(
                IdentitySubmitted(
                    aggregate_id=cmd.seller_id,
                    occurred_at=now,
                    payload={"verification_id": str(verification.id)},
                )
            )
            await self._uow.commit()

        job_id = await self._queue.enqueue(
            "identity.verify",
            verification_id=str(verification.id),
            seller_id=str(cmd.seller_id),
        )
        _ = files  # validated above; the worker re-reads them from storage
        return SubmitIdentityResult(
            verification_id=verification.id,
            job_id=job_id,
            status=VerificationStatus.PROCESSING,
        )

    async def _validate_files(self, cmd: SubmitIdentityCommand, user_id: UUID) -> list[object]:
        """Ownership and purpose checks.

        Without the ownership check this is an IDOR: a seller could submit
        another user's uploaded CNIC as their own.
        """
        validated: list[object] = []
        purposes = dict(_REQUIRED_PURPOSES)
        if cmd.hold_id_file_id is not None:
            purposes["hold_id_file_id"] = FilePurpose.HOLD_ID
        file_ids = [getattr(cmd, key) for key in purposes]
        if len(set(file_ids)) != len(file_ids):
            raise ValidationError("Each identity image must be a different upload.")
        for field_name, expected_purpose in purposes.items():
            file_id: UUID = getattr(cmd, field_name)
            stored = await self._uow.files.get(file_id)
            if stored is None:
                raise ValidationError("Uploaded file not found.", field=field_name)
            if stored.owner_user_id != user_id:
                raise ValidationError("Uploaded file not found.", field=field_name)
            if stored.purpose != expected_purpose:
                raise ValidationError(
                    f"Expected a {expected_purpose.value} upload.", field=field_name
                )
            validated.append(stored)
        return validated


# ── Worker-side finalisation ─────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FinalizeIdentityCommand:
    """Applied by the worker once OCR and face matching have completed."""

    verification_id: UUID
    ocr_confidence: float | None
    face_similarity: float | None
    face_distance: float | None
    threshold: float
    review_lower_bound: float
    liveness_passed: bool | None
    cnic_hash: bytes | None
    document_expired: bool
    engine: str
    engine_version: str
    raw: dict[str, object]
    #: Structural cross-checks on the parsed CNIC (format, gender digit vs the
    #: printed field). Computed in the adapter layer and passed in as plain
    #: data so the domain stays free of OCR concerns.
    cnic_needs_review: bool = False
    cnic_check_failures: tuple[str, ...] = ()
    # A still image of a person holding a card is not certified liveness. The
    # ORB/face signals help a human; this pilot never auto-awards verified.
    hold_review_required: bool = False
    hold_card_found: bool = False
    holder_face_similarity: float | None = None


@dataclass(frozen=True, slots=True)
class FinalizeIdentityResult:
    decision: VerificationStatus
    requires_manual_review: bool
    duplicate_accounts: int = 0


class FinalizeIdentityVerification:
    """Turns raw AI evidence into a verification decision.

    Note what this does *not* do: it never computes a score. It records a
    decision and lets the scoring engine price it (ADR-0002).
    """

    def __init__(self, *, uow: UnitOfWork, queue: JobQueue, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._queue = queue
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: FinalizeIdentityCommand) -> FinalizeIdentityResult:
        now = self._clock.now()

        async with self._uow:
            verification = await self._uow.identities.get_latest_verification_by_id(
                cmd.verification_id
            )
            if verification is None:
                raise EntityNotFound("identity_verification", cmd.verification_id)

            seller = await self._uow.sellers.get(verification.seller_id)
            if seller is None:
                raise EntityNotFound("seller", verification.seller_id)

            duplicates = 0
            if cmd.cnic_hash is not None:
                duplicates = await self._uow.identities.count_sellers_with_cnic_hash(
                    cmd.cnic_hash, excluding_seller_id=seller.id
                )

            decision, needs_review, reason = self._decide(cmd, duplicates)

            await self._uow.identities.update_verification(
                dataclasses.replace(
                    verification,
                    decision=decision,
                    face_similarity=cmd.face_similarity,
                    face_distance=cmd.face_distance,
                    threshold_used=cmd.threshold,
                    liveness_passed=cmd.liveness_passed,
                    face_match_engine=cmd.engine,
                    engine_version=cmd.engine_version,
                    decision_reason=reason,
                    decision_source="AUTO",
                    # Do not lose the fourth-file link when the worker saves
                    # OCR/matcher evidence after the upload is processed.
                    raw_result={**verification.raw_result, **cmd.raw},
                    verified_at=now if decision == VerificationStatus.VERIFIED else None,
                )
            )
            updated_seller = await self._uow.sellers.update(
                dataclasses.replace(seller, identity_status=decision, updated_at=now)
            )
            # Publication changes atomically with the identity verdict. Do
            # not rely on a browser hiding an unverified seller's listing.
            await sync_listing_publication(self._uow, updated_seller, now=now)

            if needs_review:
                await self._open_review_case(seller, cmd, duplicates, now)

            if duplicates >= 1:
                await self._uow.publish(
                    DuplicateIdentityDetected(
                        aggregate_id=seller.id,
                        occurred_at=now,
                        payload={"linked_accounts": duplicates},
                    )
                )

            event_cls = (
                IdentityVerified if decision == VerificationStatus.VERIFIED else IdentityRejected
            )
            await self._uow.publish(
                event_cls(
                    aggregate_id=seller.id,
                    occurred_at=now,
                    payload={"decision": decision.value, "reason": reason},
                )
            )
            await self._uow.commit()

        await self._queue.enqueue(
            "scoring.recompute_trust_score", seller_id=str(seller.id), trigger="SIGNAL_CHANGE"
        )
        return FinalizeIdentityResult(decision, needs_review, duplicates)

    def _decide(
        self, cmd: FinalizeIdentityCommand, duplicates: int
    ) -> tuple[VerificationStatus, bool, str]:
        # Expiry first. The worker sets `document_expired` only from REAL OCR
        # that read the expiry reliably (clear photo, consistent sides, all
        # three dates present); fake OCR never sets it. An expired card is a
        # seller-fixable fact a reviewer cannot overturn, so it is rejected
        # even when the face could not be compared, and the seller may
        # immediately resubmit with a valid card.
        if cmd.document_expired:
            return VerificationStatus.REJECTED, False, "The submitted ID has expired."
        # An unreadable upload is a photograph problem, not a fraud finding.
        # FAILED would cap the Trust Score for a blurry image, and the seller
        # cannot appeal against "we could not read it" - so this waits for a
        # human instead of penalising them (P1-05).
        if cmd.ocr_confidence is None or cmd.face_similarity is None:
            return (
                VerificationStatus.PENDING,
                True,
                "The documents could not be read automatically; sent for manual review.",
            )
        if duplicates >= 1:
            return (
                VerificationStatus.REJECTED,
                True,
                "This ID is already registered to another account.",
            )
        # The card contradicts itself - most often OCR mis-reading the gender
        # field, occasionally a crude forgery. Neither is safe to auto-decide.
        if cmd.cnic_needs_review:
            return (
                VerificationStatus.PENDING,
                True,
                "The ID details could not be confirmed; sent for manual review.",
            )
        if cmd.hold_review_required:
            return (
                VerificationStatus.PENDING,
                True,
                "ID beside face captured; card and face evidence awaits human review.",
            )
        if cmd.face_similarity >= cmd.threshold:
            return VerificationStatus.VERIFIED, False, "Selfie matches the ID photo."
        # Borderline goes to a human. Face matching has known demographic
        # error-rate disparities, and a false rejection here costs a real
        # person their ability to trade.
        if cmd.face_similarity >= cmd.review_lower_bound:
            return (
                VerificationStatus.PENDING,
                True,
                "Selfie partly matches the ID photo; sent for manual review.",
            )
        return VerificationStatus.REJECTED, False, "Selfie does not match the ID photo."

    @staticmethod
    def _review_reason(cmd: FinalizeIdentityCommand, duplicates: int) -> str:
        """Why a human is being asked to look, in the reviewer's own terms."""
        if duplicates >= 1:
            return "Duplicate CNIC across accounts"
        if cmd.ocr_confidence is None or cmd.face_similarity is None:
            return "Documents could not be read automatically"
        if cmd.raw.get("ocr_engine") == "fake":
            return "Demo OCR is simulated; inspect the physical ID manually"
        if cmd.cnic_check_failures:
            # review_cases.trigger_reason is VARCHAR(120); never let a long
            # list of codes fail the whole verification transaction.
            reason = f"CNIC cross-check failed: {', '.join(cmd.cnic_check_failures)}"
            return reason if len(reason) <= 120 else reason[:117] + "..."
        if cmd.hold_review_required:
            if not cmd.hold_card_found or cmd.holder_face_similarity is None:
                return "Held card or applicant face could not be confirmed automatically"
            if cmd.holder_face_similarity < cmd.threshold:
                return "Held-card applicant face differs from the separate selfie"
            return "Held-card image requires a human identity review"
        return "Borderline face-match similarity"

    async def _open_review_case(
        self,
        seller: SellerProfile,
        cmd: FinalizeIdentityCommand,
        duplicates: int,
        now: datetime,
    ) -> None:
        from trustlens.core.domain.entities import ReviewCase

        await self._uow.review_cases.add(
            ReviewCase(
                id=self._ids.new(),
                seller_id=seller.id,
                case_type=(
                    ReviewCaseType.FRAUD_FLAG if duplicates >= 1 else ReviewCaseType.IDENTITY_REVIEW
                ),
                status=ReviewStatus.QUEUED,
                created_at=now,
                priority=2 if duplicates >= 1 else 5,
                trigger_reason=self._review_reason(cmd, duplicates),
                related_entity_type="identity_verifications",
                related_entity_id=cmd.verification_id,
            )
        )


__all__ = [
    "FinalizeIdentityCommand",
    "FinalizeIdentityResult",
    "FinalizeIdentityVerification",
    "SubmitIdentityCommand",
    "SubmitIdentityDocuments",
    "SubmitIdentityResult",
]
