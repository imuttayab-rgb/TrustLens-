"""Pending holding-card evidence must not earn verified identity points."""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

from trustlens.core.application.services.signal_collector import SellerEvidence, SignalCollector
from trustlens.core.domain.entities import IdentityDocument, IdentityVerification
from trustlens.core.domain.enums import DocumentType, SignalStatus, VerificationStatus


def test_pending_hold_card_keeps_both_identity_signals_unavailable() -> None:
    now = datetime.now(UTC)
    seller = UUID(int=1)
    document = IdentityDocument(
        id=UUID(int=2), seller_id=seller,
        document_type=DocumentType.CNIC_FRONT, file_id=UUID(int=3),
        status=VerificationStatus.VERIFIED, created_at=now,
        ocr_confidence=0.99,
    )
    verification = IdentityVerification(
        id=UUID(int=4), seller_id=seller, decision=VerificationStatus.PENDING,
        created_at=now, face_similarity=0.99, threshold_used=0.7,
        raw_result={"hold_id_file_id": str(UUID(int=5))},
    )
    evidence = cast(SellerEvidence, SimpleNamespace(
        identity_documents=(document,), identity_verification=verification,
        now=now, duplicate_cnic_accounts=0,
    ))
    collector = SignalCollector()
    assert collector._identity_document(evidence).status is SignalStatus.UNAVAILABLE
    assert collector._identity_face_match(evidence).status is SignalStatus.UNAVAILABLE
