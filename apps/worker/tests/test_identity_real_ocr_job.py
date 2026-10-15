"""End-to-end identity job with REAL OCR on SYNTHETIC cards (no personal data).

Storage, database and queue are in-memory stand-ins; the OCR engine is the
real RapidOCR adapter. The face matcher is a deterministic stub because the
point here is the expiry/OCR decision path, not biometrics.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from trustlens.core.domain.entities import IdentityDocument, IdentityVerification, SellerProfile
from trustlens.core.domain.enums import DocumentType, VerificationStatus
from trustlens.core.domain.ports.ai import FaceMatchResult

NOW = datetime(2026, 10, 2, tzinfo=UTC)
SELLER, USER, VERIFICATION = UUID(int=11), UUID(int=12), UUID(int=13)
FILES = {
    DocumentType.CNIC_FRONT: UUID(int=21),
    DocumentType.CNIC_BACK: UUID(int=22),
    DocumentType.SELFIE: UUID(int=23),
}


def _card(lines: list[str], *, blur: int = 0) -> bytes:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    image = np.full((540, 860, 3), 235, dtype=np.uint8)
    for index, text in enumerate(lines):
        x = 40 + (index % 3) * 280 if "." in text and text[0].isdigit() else 40
        cv2.putText(image, text, (x, 60 + 50 * (index if x == 40 else 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2, cv2.LINE_AA)
    if blur:
        image = cv2.GaussianBlur(image, (blur, blur), 0)
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    assert ok
    return bytes(buffer.tobytes())


def front(expiry: str | None, *, blur: int = 0) -> bytes:
    dates = ["01.01.1990", "15.03.2021"] + ([expiry] if expiry else [])
    return _card(
        ["PAKISTAN National Identity Card", "Name", "Test Sample Person", "Gender M",
         "Identity Number", "35202-1234567-1", *dates],
        blur=blur,
    )


BACK = _card(["Synthetic back side", "35202-1234567-1"])


class Store:
    def __init__(self, blobs: dict[str, bytes]) -> None:
        self.blobs = blobs

    async def get(self, *, bucket: str, object_key: str) -> bytes:
        return self.blobs[object_key]


class Face:
    async def compare(self, *_: Any, threshold: float) -> FaceMatchResult:
        return FaceMatchResult(similarity=0.9, distance=0.1, threshold=threshold,
                               engine="stub", engine_version="1")


def _context(front_bytes: bytes, engine: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    seen: dict[str, Any] = {"documents": {}, "seller": None, "verification": None}
    seller = SellerProfile(
        id=SELLER, user_id=USER, handle="synthetic", display_name="Synthetic",
        account_opened_at=NOW, created_at=NOW, identity_status=VerificationStatus.PROCESSING,
    )
    verification = IdentityVerification(
        id=VERIFICATION, seller_id=SELLER, decision=VerificationStatus.PROCESSING,
        created_at=NOW, front_document_id=UUID(int=31),
    )
    docs = [
        IdentityDocument(id=UUID(int=31 + i), seller_id=SELLER, document_type=t,
                         file_id=FILES[t], status=VerificationStatus.PROCESSING, created_at=NOW)
        for i, t in enumerate(FILES)
    ]

    class Identities:
        async def get_latest_verification_by_id(self, _id: UUID) -> IdentityVerification:
            return verification

        async def list_documents(self, _seller: UUID) -> list[IdentityDocument]:
            return docs

        async def update_document(self, doc: IdentityDocument) -> IdentityDocument:
            seen["documents"][doc.document_type] = doc
            return doc

        async def store_encrypted_fields(self, *_: Any, **__: Any) -> None:
            seen["encrypted"] = True

        async def count_sellers_with_cnic_hash(self, *_: Any, **__: Any) -> int:
            return 0

        async def update_verification(self, value: IdentityVerification) -> IdentityVerification:
            seen["verification"] = value
            return value

    class Files:
        async def get(self, file_id: UUID) -> Any:
            return SimpleNamespace(bucket="b", object_key=str(file_id), owner_user_id=USER,
                                   purpose=None)

    class Sellers:
        async def get(self, _id: UUID) -> SellerProfile:
            return seen["seller"] or seller

        async def update(self, value: SellerProfile) -> SellerProfile:
            seen["seller"] = value
            return value

    class Listings:
        async def list_for_seller(self, *_: Any, **__: Any) -> list[Any]:
            return []

    class ReviewCases:
        async def add(self, case: Any) -> Any:
            seen["review_reason"] = case.trigger_reason
            return case

    class Uow:
        identities, files, sellers = Identities(), Files(), Sellers()
        listings, review_cases = Listings(), ReviewCases()

        async def __aenter__(self) -> Uow:
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def commit(self) -> None:
            return None

        async def publish(self, _event: Any) -> None:
            return None

    class Queue:
        async def enqueue(self, *_: Any, **__: Any) -> None:
            return None

    class Encryptor:
        def blind_index(self, value: str, _pepper: bytes) -> bytes:
            return b"hash-of-" + value.encode()

        def encrypt(self, value: str) -> str:
            return "enc"

    blobs = {str(FILES[DocumentType.CNIC_FRONT]): front_bytes,
             str(FILES[DocumentType.CNIC_BACK]): BACK,
             str(FILES[DocumentType.SELFIE]): b"selfie-not-used-by-stub"}
    settings = SimpleNamespace(
        ai=SimpleNamespace(face_match_threshold=0.7, face_match_review_lower=0.55,
                           face_match_real_in_demo=False, ocr_min_confidence=0.6),
        security=SimpleNamespace(token_pepper=SimpleNamespace(get_secret_value=lambda: "p")),
    )
    ctx = {"settings": settings, "uow": Uow, "storage": Store(blobs), "ocr": engine,
           "face": Face(), "queue": Queue(), "encryptor": Encryptor(),
           "clock": SimpleNamespace(now=lambda: NOW),
           "ids": SimpleNamespace(new=lambda: UUID(int=99))}
    return ctx, seen


@pytest.fixture(scope="module")
def engine():  # type: ignore[no-untyped-def]
    pytest.importorskip("rapidocr_onnxruntime")
    from trustlens.ai.ocr.rapidocr_engine import RapidOcrEngine

    return RapidOcrEngine(min_confidence=0.60)


async def _run(front_bytes: bytes, engine: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    from trustlens_worker.jobs.identity import verify_identity

    ctx, seen = _context(front_bytes, engine)
    out = await verify_identity(ctx, verification_id=str(VERIFICATION), seller_id=str(SELLER))
    return out, seen


async def test_valid_synthetic_card_is_verified_with_real_ocr(engine) -> None:  # type: ignore[no-untyped-def]
    out, seen = await _run(front("15.03.2031"), engine)
    checks = seen["verification"].raw_result["cnic_checks"]
    assert checks["engine"] == "rapidocr" and checks["simulated"] is False
    assert checks["expiry_status"] == "VALID" and checks["expiry_date"] == "2031-03-15"
    assert checks["back_side_read"] is True
    assert out["decision"] == VerificationStatus.VERIFIED.value
    assert seen["documents"][DocumentType.CNIC_FRONT].extracted_cnic_hash is not None


async def test_expired_synthetic_card_is_rejected(engine) -> None:  # type: ignore[no-untyped-def]
    out, seen = await _run(front("15.03.2025"), engine)
    assert out["decision"] == VerificationStatus.REJECTED.value
    assert "expired" in seen["verification"].decision_reason.lower()


async def test_card_without_expiry_goes_to_human_not_rejection(engine) -> None:  # type: ignore[no-untyped-def]
    out, seen = await _run(front(None), engine)
    assert out["decision"] == VerificationStatus.PENDING.value
    assert out["requires_manual_review"] is True
    assert "CNIC_EXPIRY_UNREADABLE" in seen["review_reason"]
    # The issue date must never be stored as an (expired) expiry.
    assert seen["documents"][DocumentType.CNIC_FRONT].fields.expiry_date is None


async def test_blurred_expired_card_is_reviewed_not_auto_rejected(engine) -> None:  # type: ignore[no-untyped-def]
    out, _seen = await _run(front("15.03.2025", blur=21), engine)
    assert out["decision"] == VerificationStatus.PENDING.value
    assert out["requires_manual_review"] is True


async def test_fake_ocr_never_rejects_for_expiry() -> None:
    from trustlens.ai.fakes import FakeOcrEngine

    out, seen = await _run(front("15.03.2025"), FakeOcrEngine())
    assert out["decision"] == VerificationStatus.PENDING.value
    assert seen["verification"].raw_result["cnic_checks"]["expiry_status"] == "NOT_ASSESSED"
    assert DocumentType.CNIC_BACK not in seen["documents"]  # fake path unchanged
