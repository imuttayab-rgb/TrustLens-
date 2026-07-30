"""Identity verification job: OpenCV + EasyOCR + DeepFace (feature F1).

This is the heaviest job in the system (~15-30 s) and the reason the worker
exists at all. It produces EVIDENCE - an OCR confidence, a face similarity, a
CNIC hash - and hands the decision to a use case. It never computes a score.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from trustlens.core.application.use_cases.verification.identity import (
    FinalizeIdentityCommand,
    FinalizeIdentityVerification,
)
from trustlens.core.domain.enums import DocumentType, VerificationStatus
from trustlens.shared.logging import get_logger

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

    front_doc = documents.get(DocumentType.CNIC_FRONT)
    front_file = files.get(DocumentType.CNIC_FRONT)
    selfie_file = files.get(DocumentType.SELFIE)
    if front_doc is None or front_file is None or selfie_file is None:
        return {"skipped": "documents missing"}

    front_bytes = await ctx["storage"].get(
        bucket=front_file.bucket, object_key=front_file.object_key
    )
    selfie_bytes = await ctx["storage"].get(
        bucket=selfie_file.bucket, object_key=selfie_file.object_key
    )

    ocr = await ctx["ocr"].extract(front_bytes, document_type="CNIC_FRONT")
    face = await ctx["face"].compare(
        front_bytes, selfie_bytes, threshold=settings.ai.face_match_threshold
    )
    log.info(
        "identity_ai_complete",
        seller_id=seller_id,
        ocr_confidence=ocr.confidence,
        similarity=face.similarity,
    )

    cnic_hash = None
    if ocr.cnic_number:
        # Blind index for duplicate detection; the number itself is stored
        # envelope-encrypted and never enters a domain entity.
        cnic_hash = ctx["encryptor"].blind_index(
            ocr.cnic_number, settings.security.token_pepper.get_secret_value().encode()
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
                    expiry_date=ocr.expiry_date,
                    father_name=ocr.father_name,
                ),
                extracted_cnic_hash=cnic_hash,
                quality_score=ocr.quality_score,
                processed_at=ctx["clock"].now(),
            )
        )
        if ocr.cnic_number:
            await uow.identities.store_encrypted_fields(
                front_doc.id,
                cnic_encrypted=ctx["encryptor"].encrypt(ocr.cnic_number).encode(),
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
            face_similarity=face.similarity,
            face_distance=face.distance,
            threshold=face.threshold,
            review_lower_bound=settings.ai.face_match_review_lower,
            liveness_passed=face.liveness_passed,
            cnic_hash=cnic_hash,
            document_expired=(
                front_doc.fields.expiry_date is not None
                and ocr.expiry_date is not None
                and ocr.expiry_date < ctx["clock"].now().date()
            )
            or (ocr.expiry_date is not None and ocr.expiry_date < ctx["clock"].now().date()),
            engine=face.engine,
            engine_version=face.engine_version,
            raw={"ocr_confidence": ocr.confidence, "similarity": face.similarity},
        )
    )

    return {
        "decision": result.decision.value,
        "requires_manual_review": result.requires_manual_review,
        "duplicate_accounts": result.duplicate_accounts,
    }


__all__ = ["verify_identity"]
