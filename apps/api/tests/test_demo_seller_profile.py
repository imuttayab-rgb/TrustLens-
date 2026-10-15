"""Persisted demo scores must be readable through the actual profile endpoint."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from trustlens.core.domain.entities import SellerProfile
from trustlens.core.domain.enums import (
    ReasonCode, RiskLevel, ScoreTrigger, SignalCategory, SignalCode,
    SignalStatus, VerificationStatus,
)
from trustlens.db import mappers, models
from trustlens_api.api.deps import get_current_actor, get_request_meta, get_uow
from trustlens_api.api.v1.routers.me import router


def persisted_score(reason: str):
    now = datetime.now(UTC)
    signal = models.TrustScoreSignalModel(
        id=UUID(int=11), trust_score_id=UUID(int=10),
        signal_definition_id=UUID(int=12),
        signal_code=SignalCode.IDENTITY_DOCUMENT_VALID.value,
        category=SignalCategory.IDENTITY, status=SignalStatus.PASS,
        weight=15, points_awarded=15, points_possible=15, confidence=1,
        reason_code=reason, reason_text="Simulated PASS for local testing.",
        evidence={"test_fixture": True}, created_at=now,
    )
    return models.TrustScoreModel(
        id=UUID(int=10), seller_id=UUID(int=2), scoring_model_id=UUID(int=13),
        score=100, risk_level=RiskLevel.LOW, raw_score=100,
        available_weight=15, confidence=1, trigger=ScoreTrigger.MANUAL,
        computed_at=now, valid_until=now+timedelta(days=30),
        is_current=True, is_manual_override=False, signals=[signal],
    )


@pytest.mark.parametrize("reason", [None, "IDENTITY_VERIFIED", "DEMO_FIXTURE_PASS"])
def test_current_seller_profile_reads_persisted_reason_codes(reason):
    now = datetime.now(UTC)
    seller = SellerProfile(
        id=UUID(int=2), user_id=UUID(int=1), handle="test-seller-01",
        display_name="Test Seller 01", account_opened_at=now, created_at=now,
        city="Lahore", identity_status=VerificationStatus.VERIFIED,
        phone_status=VerificationStatus.VERIFIED, email_status=VerificationStatus.VERIFIED,
    )

    async def get_by_user(user_id):
        assert user_id == seller.user_id
        return seller

    async def get_current(seller_id):
        assert seller_id == seller.id
        return None if reason is None else mappers.to_trust_score(
            persisted_score(reason), model_version="1.0.0"
        )

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_actor] = lambda: SimpleNamespace(user_id=seller.user_id)
    app.dependency_overrides[get_request_meta] = lambda: SimpleNamespace(request_id="fixture-regression")
    app.dependency_overrides[get_uow] = lambda: SimpleNamespace(
        sellers=SimpleNamespace(get_by_user=get_by_user),
        trust_scores=SimpleNamespace(get_current=get_current),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/sellers/me")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["handle"] == seller.handle
    assert data["identityStatus"] == "VERIFIED"
    assert data["score"] == (None if reason is None else 100)


def test_demo_reason_preserves_explicit_fixture_evidence():
    mapped = mappers.to_trust_score(persisted_score("DEMO_FIXTURE_PASS"), model_version="1.0.0")
    assert mapped.signals[0].reason_code.value == "DEMO_FIXTURE_PASS"
    assert mapped.signals[0].evidence == {"test_fixture": True}
    assert mapped.signals[0].reason_text.startswith("Simulated PASS")


def test_unknown_reason_codes_are_still_rejected():
    with pytest.raises(ValueError):
        ReasonCode("UNRECOGNISED_VALUE")
