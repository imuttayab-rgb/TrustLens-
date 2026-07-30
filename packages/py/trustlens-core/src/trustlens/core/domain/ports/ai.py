"""AI capability ports.

Each returns *evidence with a confidence value*, never a score. The
deterministic scoring policy is what turns evidence into points (ADR-0002),
which is what makes a score reproducible, auditable and appealable - and what
contains prompt injection, since a compromised LLM response can at worst
mislabel one signal worth <= 10 points.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class OcrResult:
    """Raw OCR output plus the fields a CNIC parser could recover."""

    text: str
    confidence: float
    engine: str
    engine_version: str
    tokens: tuple[dict[str, Any], ...] = ()
    full_name: str | None = None
    cnic_number: str | None = None
    date_of_birth: date | None = None
    expiry_date: date | None = None
    father_name: str | None = None
    address: str | None = None
    quality_score: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_required_fields(self) -> bool:
        return bool(self.full_name and self.cnic_number)


@runtime_checkable
class OcrEngine(Protocol):
    """Optical character recognition over an identity document image."""

    async def extract(self, image: bytes, *, document_type: str) -> OcrResult: ...


@dataclass(frozen=True, slots=True)
class FaceMatchResult:
    similarity: float
    distance: float
    threshold: float
    engine: str
    engine_version: str
    #: None when quality gates could not establish liveness either way.
    liveness_passed: bool | None = None
    face_detected_in_document: bool = True
    face_detected_in_selfie: bool = True
    quality_score: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_match(self) -> bool:
        return self.similarity >= self.threshold


@runtime_checkable
class FaceMatcher(Protocol):
    """Compare a selfie against the photo on an identity document."""

    async def compare(
        self, document_image: bytes, selfie_image: bytes, *, threshold: float
    ) -> FaceMatchResult: ...


@dataclass(frozen=True, slots=True)
class ListingAnalysisResult:
    """Structured LLM output for one listing.

    The schema is strict and every field is range- or enum-validated by the
    adapter before it reaches the domain. Untrusted seller text goes in;
    only typed, bounded evidence comes out.
    """

    risk_score: float
    confidence: float
    labels: tuple[str, ...]
    findings: dict[str, Any]
    provider: str
    model_name: str
    summary: str = ""
    model_version: str | None = None
    prompt_version: str | None = None
    price_deviation_pct: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LlmAnalyzer(Protocol):
    """LLM-based listing analysis.

    Two adapters implement this (OpenAI and Claude, as the proposal specifies
    "OpenAI / Claude API"); both pass the same contract test suite, so a use
    case cannot tell which one it received.
    """

    async def analyze_listing(
        self,
        *,
        title: str,
        description: str,
        price: float | None,
        currency: str | None,
        category: str | None,
    ) -> ListingAnalysisResult: ...


@dataclass(frozen=True, slots=True)
class ClassifierResult:
    """Output of the custom-trained scam-listing classifier."""

    scam_probability: float
    label: str
    model_version: str
    threshold: float
    features_used: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_scam(self) -> bool:
        return self.scam_probability >= self.threshold


@runtime_checkable
class ScamClassifier(Protocol):
    """The custom-trained classifier from apps/ml.

    Feature extraction is shared with training rather than reimplemented -
    train/serve skew is the classic reason a model scores 0.94 offline and
    behaves randomly in production.
    """

    async def predict(
        self,
        *,
        title: str,
        description: str,
        price: float | None,
        category: str | None,
    ) -> ClassifierResult: ...


__all__ = [
    "ClassifierResult",
    "FaceMatchResult",
    "FaceMatcher",
    "ListingAnalysisResult",
    "LlmAnalyzer",
    "OcrEngine",
    "OcrResult",
    "ScamClassifier",
]
