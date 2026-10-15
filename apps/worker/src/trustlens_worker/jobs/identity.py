"""Identity verification job: OpenCV + EasyOCR + DeepFace (feature F1).

This is the heaviest job in the system (~15-30 s) and the reason the worker
exists at all. It produces EVIDENCE - an OCR confidence, a face similarity, a
CNIC hash - and hands the decision to a use case. It never computes a score.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from trustlens.ai.ocr.cnic_validation import ExpiryStatus
from trustlens.ai.ocr.cnic_validation import validate as validate_cnic
from trustlens.core.application.use_cases.verification.identity import (
    FinalizeIdentityCommand,
    FinalizeIdentityVerification,
)
from trustlens.core.domain.enums import DocumentType, FilePurpose, VerificationStatus
from trustlens.shared.logging import get_logger
from trustlens_worker.jobs.cnic_reading import ISSUE_EXPIRY_UNREADABLE, combine_cnic_sides
from trustlens_worker.jobs.hold_card import compare_card_frames

log = get_logger(__name__)


async def verify_identity(
    ctx: dict[str, Any], *, verification_id: str, seller_id: str
) -> dict[str, Any]:
    """OCR both CNIC sides, compare the selfie, then record a decision.

    Idempotent: re-running re-reads the same objects and rewrites the same
    derived fields. A retry after a crash is always safe.
    """
    settings = ctx["settings"]
    uow = ctx["uow"]()
    vid = UUID(verification_id)

    async with uow:
        verification = await uow.identities.get_latest_verification_by_id(vid)
        if verification is None:
            return {"skipped": "verification not found"}
        documents = {
            d.document_type: d for d in await uow.identities.list_documents(UUID(seller_id))
        }
        files = {doc_type: await uow.files.get(doc.file_id) for doc_type, doc in documents.items()}
        hold_file_id = verification.raw_result.get("hold_id_file_id")
        hold_file = await uow.files.get(UUID(hold_file_id)) if hold_file_id else None

    front_doc = documents.get(DocumentType.CNIC_FRONT)
    front_file = files.get(DocumentType.CNIC_FRONT)
    back_doc = documents.get(DocumentType.CNIC_BACK)
    back_file = files.get(DocumentType.CNIC_BACK)
    selfie_file = files.get(DocumentType.SELFIE)
    if front_doc is None or front_file is None or selfie_file is None:
        return {"skipped": "documents missing"}

    front_bytes = await ctx["storage"].get(
        bucket=front_file.bucket, object_key=front_file.object_key
    )
    selfie_bytes = await ctx["storage"].get(
        bucket=selfie_file.bucket, object_key=selfie_file.object_key
    )

    hold_result = None
    holder_face_similarity = None
    holder_face_detected = None
    if (
        hold_file_id and hold_file is not None
        and hold_file.purpose == FilePurpose.HOLD_ID
        and hold_file.owner_user_id == selfie_file.owner_user_id
    ):
        try:
            hold_bytes = await ctx["storage"].get(
                bucket=hold_file.bucket, object_key=hold_file.object_key
            )
            # ORB is only extra evidence; not card authenticity or liveness.
            hold_result = await asyncio.to_thread(compare_card_frames, front_bytes, hold_bytes)
            holder_face = await ctx["face"].compare(
                hold_bytes, selfie_bytes, threshold=settings.ai.face_match_threshold
            )
            holder_face_detected = holder_face.face_detected_in_document
            if holder_face.engine != "fake" and holder_face_detected:
                holder_face_similarity = holder_face.similarity
        except Exception as exc:
            # A bad fourth image is inconclusive; keep the first three.
            log.warning("hold_id_evidence_unavailable", error=type(exc).__name__)

    ocr = await ctx["ocr"].extract(front_bytes, document_type="CNIC_FRONT")
    # Fake OCR invents its ID number/expiry from image bytes. Neither is
    # government evidence: never deduplicate or reject a person using those
    # synthetic fields. The submitted images must be reviewed by a human.
    ocr_is_simulated = ocr.engine == "fake"

    # Real OCR also reads the BACK of the card: depending on the CNIC
    # generation the expiry may be printed on either side, and two sides that
    # disagree (different numbers / expiries) are a strong signal a human must
    # look. Fake mode keeps its previous single-side behaviour exactly.
    back_ocr = None
    if not ocr_is_simulated and back_file is not None:
        try:
            back_bytes = await ctx["storage"].get(
                bucket=back_file.bucket, object_key=back_file.object_key
            )
            back_ocr = await ctx["ocr"].extract(back_bytes, document_type="CNIC_BACK")
        except Exception as exc:
            # An unreadable back side is not fraud; the front still counts and
            # any missing expiry is routed to manual review below.
            log.warning("cnic_back_ocr_unavailable", error=type(exc).__name__)
    reading = combine_cnic_sides(ocr, back_ocr)

    face = await ctx["face"].compare(
        front_bytes, selfie_bytes, threshold=settings.ai.face_match_threshold
    )
    # The real model returns similarity=0 when either photograph has no usable
    # face. In the new opt-in pilot that is an image-quality/retry problem, not
    # proof of impersonation; the domain treats None as manual review.
    pilot_face_unreadable = (
        settings.ai.face_match_real_in_demo
        and (not face.face_detected_in_document or not face.face_detected_in_selfie)
    )
    # Structural cross-checks (P1-04): number format, province code, and the
    # gender digit against the printed gender field. None of this proves the
    # card is genuine - NADRA has no public verification API - but a card that
    # contradicts itself is worth a human's attention.
    #
    # Only a RELIABLE expiry (clear photo, confident OCR, consistent sides,
    # birth/issue/expiry all present) is passed in, because an EXPIRED result
    # rejects the seller automatically. An uncertain date becomes "UNKNOWN".
    checks = validate_cnic(
        cnic_number=reading.cnic_number,
        text=reading.combined_text or ocr.text,
        expiry=reading.expiry_date if reading.expiry_reliable else None,
        today=ctx["clock"].now().date(),
    )
    # Review codes added by the real-OCR pilot. Unknown expiry is NOT a
    # rejection - it is a human check ("we could not read the expiry").
    ocr_issues: list[str] = [] if ocr_is_simulated else list(reading.issues)
    if (
        not ocr_is_simulated
        and checks.expiry_status is ExpiryStatus.UNKNOWN
        and not reading.issues
    ):
        ocr_issues.append(ISSUE_EXPIRY_UNREADABLE)
    review_failures = () if ocr_is_simulated else (*checks.failures, *ocr_issues)

    log.info(
        "identity_ai_complete",
        seller_id=seller_id,
        ocr_engine=ocr.engine,
        ocr_confidence=ocr.confidence,
        back_side_read=back_ocr is not None,
        similarity=face.similarity,
        cnic_format_valid=checks.format_valid,
        cnic_gender_consistent=checks.gender_consistent,
        # Status only - the date itself and the CNIC number are never logged.
        cnic_expiry_status=checks.expiry_status.value,
        cnic_failures=list(checks.failures),
        cnic_issues=ocr_issues,
    )

    # Only a structurally valid number read consistently from the card is
    # indexed; an OCR mis-read must never create a false "duplicate account".
    cnic_number = reading.cnic_number if checks.format_valid else None
    cnic_hash = None
    if cnic_number and not ocr_is_simulated:
        # Blind index for duplicate detection; the number itself is stored
        # envelope-encrypted and never enters a domain entity.
        cnic_hash = ctx["encryptor"].blind_index(
            cnic_number, settings.security.token_pepper.get_secret_value().encode()
        )

    async with uow:
        import dataclasses

        from trustlens.core.domain.entities import OcrFields

        await uow.identities.update_document(
            dataclasses.replace(
                front_doc,
                status=(
                    VerificationStatus.VERIFIED
                    if ocr.has_required_fields
                    else VerificationStatus.FAILED
                ),
                ocr_engine=ocr.engine,
                ocr_engine_version=ocr.engine_version,
                ocr_confidence=ocr.confidence,
                ocr_raw=ocr.raw,
                fields=OcrFields(
                    full_name=ocr.full_name,
                    date_of_birth=ocr.date_of_birth,
                    # Fake mode keeps its old behaviour. Real mode stores only
                    # an expiry it trusts: the trust-score signal treats a
                    # stored past expiry as "ID expired".
                    expiry_date=(
                        ocr.expiry_date
                        if ocr_is_simulated
                        else (reading.expiry_date if reading.expiry_reliable else None)
                    ),
                    father_name=ocr.father_name,
                ),
                extracted_cnic_hash=cnic_hash,
                quality_score=ocr.quality_score,
                processed_at=ctx["clock"].now(),
            )
        )
        if back_doc is not None and back_ocr is not None:
            # Evidence for the reviewer; the back side never carries the
            # CNIC hash (the front is the single source for duplicates).
            await uow.identities.update_document(
                dataclasses.replace(
                    back_doc,
                    status=(
                        VerificationStatus.VERIFIED
                        if back_ocr.text and back_ocr.confidence >= settings.ai.ocr_min_confidence
                        else VerificationStatus.FAILED
                    ),
                    ocr_engine=back_ocr.engine,
                    ocr_engine_version=back_ocr.engine_version,
                    ocr_confidence=back_ocr.confidence,
                    ocr_raw=back_ocr.raw,
                    fields=OcrFields(
                        expiry_date=(
                            back_ocr.expiry_date
                            if reading.expiry_reliable and reading.expiry_source == "CNIC_BACK"
                            else None
                        ),
                    ),
                    quality_score=back_ocr.quality_score,
                    processed_at=ctx["clock"].now(),
                )
            )
        if cnic_number and not ocr_is_simulated:
            await uow.identities.store_encrypted_fields(
                front_doc.id,
                cnic_encrypted=ctx["encryptor"].encrypt(cnic_number).encode(),
                dob_encrypted=(
                    ctx["encryptor"].encrypt(str(ocr.date_of_birth)).encode()
                    if ocr.date_of_birth
                    else None
                ),
            )
        await uow.commit()

    result = await FinalizeIdentityVerification(
        uow=uow, queue=ctx["queue"], clock=ctx["clock"], ids=ctx["ids"]
    ).execute(
        FinalizeIdentityCommand(
            verification_id=vid,
            ocr_confidence=ocr.confidence if ocr.has_required_fields else None,
            face_similarity=None if pilot_face_unreadable else face.similarity,
            face_distance=face.distance,
            threshold=face.threshold,
            review_lower_bound=settings.ai.face_match_review_lower,
            liveness_passed=face.liveness_passed,
            cnic_hash=cnic_hash,
            document_expired=(
                checks.expiry_status is ExpiryStatus.EXPIRED and not ocr_is_simulated
            ),
            engine=face.engine,
            engine_version=face.engine_version,
            raw={
                "ocr_confidence": ocr.confidence,
                "ocr_engine": ocr.engine,
                "similarity": face.similarity,
                "hold_card": {
                    "card_found": hold_result.card_found if hold_result else False,
                    "good_matches": hold_result.good_matches if hold_result else 0,
                    "inliers": hold_result.inliers if hold_result else 0,
                    "holder_face_detected": holder_face_detected,
                    "holder_face_similarity": holder_face_similarity,
                    # No server-validated live video or sensor attestation.
                    "presentation_attack_detection": "NOT_ASSESSED",
                } if hold_file_id else None,
                "cnic_checks": {
                    "simulated": ocr_is_simulated,
                    "engine": ocr.engine,
                    "back_side_read": back_ocr is not None,
                    "format_valid": None if ocr_is_simulated else checks.format_valid,
                    "province": None if ocr_is_simulated else checks.province,
                    "gender_consistent": None if ocr_is_simulated else checks.gender_consistent,
                    "expiry_status": (
                        "NOT_ASSESSED" if ocr_is_simulated else checks.expiry_status
                    ),
                    # ISO date shown to the reviewer only when it was enforced.
                    "expiry_date": (
                        reading.expiry_date.isoformat()
                        if not ocr_is_simulated and reading.expiry_reliable and reading.expiry_date
                        else None
                    ),
                    "expiry_source": None if ocr_is_simulated else reading.expiry_source,
                    "issues": ocr_issues,
                    "failures": [] if ocr_is_simulated else list(checks.failures),
                },
            },
            cnic_needs_review=checks.needs_manual_review or ocr_is_simulated or bool(ocr_issues),
            cnic_check_failures=review_failures,
            hold_review_required=bool(hold_file_id),
            hold_card_found=hold_result.card_found if hold_result else False,
            holder_face_similarity=holder_face_similarity,
        )
    )

    return {
        "decision": result.decision.value,
        "requires_manual_review": result.requires_manual_review,
        "duplicate_accounts": result.duplicate_accounts,
    }


__all__ = ["verify_identity"]
