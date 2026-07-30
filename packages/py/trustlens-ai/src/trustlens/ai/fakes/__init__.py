"""Deterministic fake AI adapters.

`USE_FAKE_AI=true` swaps every AI port for one of these. That single switch is
what makes the whole system runnable on a lab machine with no internet and no
paid API key (NFR-8) - which is the difference between a demonstrable FYP and
one that depends on someone's billing account working on presentation day.

These are not stubs that return constants: they derive plausible, *stable*
results from the input, so the same listing always produces the same analysis
and E2E tests can assert on real numbers.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta
from typing import Any

from trustlens.core.domain.ports.ai import (
    ClassifierResult,
    FaceMatchResult,
    ListingAnalysisResult,
    OcrResult,
)


def _stable_unit(*parts: str) -> float:
    """A stable pseudo-random float in [0, 1) derived from the inputs.

    Not `random`: a fake that returns different values on each run makes tests
    flaky and demos unrepeatable.
    """
    digest = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF


class FakeOcrEngine:
    """Returns plausible CNIC fields derived from the image bytes."""

    def __init__(self, *, base_confidence: float = 0.93) -> None:
        self._base_confidence = base_confidence

    async def extract(self, image: bytes, *, document_type: str) -> OcrResult:
        seed = hashlib.sha256(image).hexdigest()
        # Tiny payloads mean a test passed a placeholder, not a document -
        # surface that as low confidence rather than silently "succeeding".
        confidence = self._base_confidence if len(image) > 64 else 0.35
        digits = "".join(c for c in seed if c.isdigit())[:13].ljust(13, "7")

        if document_type == "SELFIE":
            return OcrResult(text="", confidence=confidence, engine="fake", engine_version="1.0")

        return OcrResult(
            text=f"PAKISTAN NATIONAL IDENTITY CARD\n{digits}",
            confidence=confidence,
            engine="fake",
            engine_version="1.0",
            full_name="Demo Seller",
            cnic_number=digits,
            date_of_birth=date(1995, 6, 15),
            # Deterministically expired for ~1 image in 10, so the
            # DOCUMENT_EXPIRED branch is actually exercised by tests.
            expiry_date=(
                date.today() - timedelta(days=30)
                if _stable_unit(seed, "expiry") < 0.1
                else date.today() + timedelta(days=900)
            ),
            quality_score=confidence,
            raw={"engine": "fake", "seed": seed[:16]},
        )


class FakeFaceMatcher:
    """Returns a stable similarity derived from both images.

    Identical images always match; different images land across the pass,
    review and fail bands so all three code paths get exercised.
    """

    async def compare(
        self, document_image: bytes, selfie_image: bytes, *, threshold: float
    ) -> FaceMatchResult:
        if document_image == selfie_image:
            similarity = 0.97
        else:
            a = hashlib.sha256(document_image).hexdigest()
            b = hashlib.sha256(selfie_image).hexdigest()
            similarity = round(0.35 + _stable_unit(a, b) * 0.6, 4)

        return FaceMatchResult(
            similarity=similarity,
            distance=round(1.0 - similarity, 4),
            threshold=threshold,
            engine="fake",
            engine_version="1.0",
            liveness_passed=True,
            quality_score=0.9,
            raw={"engine": "fake"},
        )


#: Patterns the fake LLM looks for. These are the real scam markers the
#: proposal names, so the fake produces the same *kind* of evidence the live
#: model would - which keeps the scoring logic honestly exercised.
SCAM_PATTERNS: tuple[tuple[str, str, float], ...] = (
    (r"\b(urgent|today only|hurry|last chance|first come)\b", "urgency_pressure", 0.85),
    (
        r"\b(whatsapp|telegram|contact me on|dm me|do not message here)\b",
        "off_platform_contact",
        0.8,
    ),
    (r"\b(advance|deposit|reserve|token money|send.*payment)\b", "advance_fee", 0.75),
    (r"\b(leaving country|moving abroad|relocating)\b", "urgency_pressure", 0.6),
    (r"\b(sealed|brand new|unopened)\b.*\b(cheap|below market|half price)\b", "price_anomaly", 0.7),
    (r"\b(no inspection|no questions|as is, no returns)\b", "impersonation", 0.5),
)


class StubLlmAnalyzer:
    """Pattern-driven listing analysis.

    Deliberately conservative and explainable - it is a stand-in for evidence,
    not a scorer. The rule engine still decides the points (ADR-0002).
    """

    def __init__(self, *, provider: str = "fake", model_name: str = "fake-llm-v1") -> None:
        self._provider = provider
        self._model_name = model_name

    async def analyze_listing(
        self,
        *,
        title: str,
        description: str,
        price: float | None,
        currency: str | None,
        category: str | None,
    ) -> ListingAnalysisResult:
        text = f"{title}\n{description}".lower()
        labels: list[str] = []
        findings: dict[str, Any] = {}
        risk = 5.0

        for pattern, label, weight in SCAM_PATTERNS:
            match = re.search(pattern, text)
            if match is None:
                continue
            if label not in labels:
                labels.append(label)
            risk += weight * 22
            findings.setdefault(label, []).append(match.group(0))

        if len(description) < 40:
            labels.append("low_detail")
            risk += 8
            findings["low_detail"] = ["description is very short"]

        risk = min(100.0, round(risk, 2))
        summary = (
            "No scam patterns detected."
            if not labels
            else "Detected: " + ", ".join(label.replace("_", " ") for label in labels)
        )

        return ListingAnalysisResult(
            risk_score=risk,
            confidence=0.8,
            labels=tuple(labels),
            findings=findings,
            provider=self._provider,
            model_name=self._model_name,
            model_version="fake-1.0",
            prompt_version="v1",
            summary=summary,
            input_tokens=len(text) // 4,
            output_tokens=64,
            latency_ms=12,
            cost_usd=0.0,
            raw={"engine": "fake"},
        )


class FakeScamClassifier:
    """Lightweight keyword classifier standing in for the trained model.

    Shares its notion of features with the real classifier so that swapping in
    the trained artifact does not change the shape of the evidence.
    """

    def __init__(self, *, threshold: float = 0.65, model_version: str = "fake-clf-v1") -> None:
        self._threshold = threshold
        self._model_version = model_version

    async def predict(
        self,
        *,
        title: str,
        description: str,
        price: float | None,
        category: str | None,
    ) -> ClassifierResult:
        text = f"{title} {description}".lower()
        hits = sum(1 for pattern, _label, _w in SCAM_PATTERNS if re.search(pattern, text))
        probability = min(0.98, round(0.08 + hits * 0.22, 4))

        return ClassifierResult(
            scam_probability=probability,
            label="scam" if probability >= self._threshold else "genuine",
            model_version=self._model_version,
            threshold=self._threshold,
            features_used=("keyword_hits", "text_length", "has_price"),
            raw={"hits": hits},
        )


class FakeIpIntelligence:
    """Marks a stable ~15% of addresses as VPN so the NETWORK signal varies."""

    async def lookup(self, ip: str):
        from datetime import UTC, datetime

        from trustlens.core.domain.entities import IpReputation

        roll = _stable_unit(ip, "vpn")
        return IpReputation(
            ip=ip,
            country_code="PK",
            city="Lahore",
            asn=17557,
            asn_org="Fake Telecom",
            is_vpn=roll < 0.15,
            is_datacenter=roll < 0.05,
            provider="fake",
            looked_up_at=datetime.now(UTC),
        )


__all__ = [
    "SCAM_PATTERNS",
    "FakeFaceMatcher",
    "FakeIpIntelligence",
    "FakeOcrEngine",
    "FakeScamClassifier",
    "StubLlmAnalyzer",
]
