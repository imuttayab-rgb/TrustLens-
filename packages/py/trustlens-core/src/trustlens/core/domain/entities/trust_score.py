"""Trust score entities - the core of the system.

Design notes that matter:

* `TrustScore` is **immutable and append-only**. Recomputation inserts a new
  row and flips the previous one's `is_current`. This gives score history for
  free and means a past decision can always be defended in an appeal.
* `TrustScoreSignal` is the explainability record. It freezes the status,
  weight, contribution, machine reason code, human sentence and a pointer to
  the underlying evidence at the moment of computation. Explaining a score
  therefore never requires recomputing it or asking an LLM.
* `ScoringModel` + `ScoringWeight` make the rules **data** (ADR-0007), so
  weights are tunable without a redeploy and every score cites the version
  that produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from trustlens.core.domain.enums import (
    ReasonCode,
    RiskLevel,
    ScoreTrigger,
    SignalCategory,
    SignalCode,
    SignalStatus,
)
from trustlens.core.domain.errors import InvalidScoringModel
from trustlens.core.domain.value_objects import Confidence, Score


@dataclass(frozen=True, slots=True)
class SignalDefinition:
    """Catalogue entry for a scoreable signal.

    Signals are rows, not code: adding one is a seed + a collector + a weight,
    and the scoring policy is never modified (open/closed principle).
    """

    id: UUID
    code: SignalCode
    category: SignalCategory
    name: str
    description: str
    buyer_facing_description: str
    max_points: int
    is_active: bool = True
    #: Failing a critical signal clamps the final score to a hard cap. Without
    #: caps, a seller who fails face match but passes everything else scores
    #: ~85 ("LOW risk"), which inverts the product's purpose.
    is_critical: bool = False
    display_order: int = 0


@dataclass(frozen=True, slots=True)
class ScoringWeight:
    """A signal's weight within one scoring model version."""

    id: UUID
    scoring_model_id: UUID
    signal_definition_id: UUID
    signal_code: SignalCode
    weight: float
    #: Extra per-signal knobs (thresholds, graded bands) kept as data so that
    #: tuning a threshold is a config change, not a deploy.
    threshold_config: dict[str, Any] = field(default_factory=dict)
    hard_cap_on_fail: int | None = None
    is_enabled: bool = True


@dataclass(frozen=True, slots=True)
class ScoringModel:
    """A versioned set of weights. At most one is active at a time."""

    id: UUID
    version: str
    name: str
    description: str
    is_active: bool
    algorithm: str = "WEIGHTED_SUM"
    config: dict[str, Any] = field(default_factory=dict)
    weights: tuple[ScoringWeight, ...] = ()
    activated_at: datetime | None = None
    activated_by: UUID | None = None

    @property
    def enabled_weights(self) -> tuple[ScoringWeight, ...]:
        return tuple(w for w in self.weights if w.is_enabled)

    @property
    def total_weight(self) -> float:
        return sum(w.weight for w in self.enabled_weights)

    def weight_for(self, code: SignalCode) -> ScoringWeight | None:
        return next((w for w in self.enabled_weights if w.signal_code == code), None)

    def validate(self) -> None:
        """Enabled weights must sum to 100.

        Enforced here *and* by a database check constraint. Weights are runtime
        data (ADR-0007), so an invalid configuration is possible and must be
        rejected before it can produce a meaningless score.
        """
        if not self.enabled_weights:
            raise InvalidScoringModel("scoring model has no enabled weights")
        total = self.total_weight
        if abs(total - 100.0) > 0.001:
            raise InvalidScoringModel(
                f"enabled weights must sum to 100, got {total:g}",
                details={"version": self.version, "total": total},
            )


@dataclass(frozen=True, slots=True)
class SignalEvaluation:
    """The result of evaluating one signal for one seller.

    Produced by a signal collector from raw evidence; consumed by the scoring
    policy. This is the boundary where AI output stops being AI output and
    becomes scoreable evidence (ADR-0002).
    """

    code: SignalCode
    category: SignalCategory
    status: SignalStatus
    #: Fraction of the signal's points earned, 0.0-1.0. PARTIAL uses the
    #: values in between; PASS is 1.0 and FAIL is 0.0.
    ratio: float
    confidence: Confidence
    reason_code: ReasonCode
    reason_text: str
    evidence: dict[str, Any] = field(default_factory=dict)
    source_table: str | None = None
    source_id: UUID | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.ratio <= 1.0:
            raise InvalidScoringModel(f"signal ratio must be 0..1, got {self.ratio}")

    @classmethod
    def passed(
        cls,
        code: SignalCode,
        category: SignalCategory,
        reason_code: ReasonCode,
        reason_text: str,
        *,
        confidence: float = 1.0,
        **kw: Any,
    ) -> SignalEvaluation:
        return cls(
            code=code,
            category=category,
            status=SignalStatus.PASS,
            ratio=1.0,
            confidence=Confidence(confidence),
            reason_code=reason_code,
            reason_text=reason_text,
            **kw,
        )

    @classmethod
    def failed(
        cls,
        code: SignalCode,
        category: SignalCategory,
        reason_code: ReasonCode,
        reason_text: str,
        *,
        confidence: float = 1.0,
        **kw: Any,
    ) -> SignalEvaluation:
        return cls(
            code=code,
            category=category,
            status=SignalStatus.FAIL,
            ratio=0.0,
            confidence=Confidence(confidence),
            reason_code=reason_code,
            reason_text=reason_text,
            **kw,
        )

    @classmethod
    def partial(
        cls,
        code: SignalCode,
        category: SignalCategory,
        ratio: float,
        reason_code: ReasonCode,
        reason_text: str,
        *,
        confidence: float = 1.0,
        **kw: Any,
    ) -> SignalEvaluation:
        return cls(
            code=code,
            category=category,
            status=SignalStatus.PARTIAL,
            ratio=ratio,
            confidence=Confidence(confidence),
            reason_code=reason_code,
            reason_text=reason_text,
            **kw,
        )

    @classmethod
    def unavailable(
        cls,
        code: SignalCode,
        category: SignalCategory,
        reason_text: str = "This check could not be completed.",
        **kw: Any,
    ) -> SignalEvaluation:
        """The check could not run (provider outage, timeout).

        Excluded from the score denominator - penalising a seller for *our*
        outage would be unfair and unappealable.
        """
        return cls(
            code=code,
            category=category,
            status=SignalStatus.UNAVAILABLE,
            ratio=0.0,
            confidence=Confidence.unknown(),
            reason_code=ReasonCode.SIGNAL_UNAVAILABLE,
            reason_text=reason_text,
            **kw,
        )

    @classmethod
    def not_applicable(
        cls,
        code: SignalCode,
        category: SignalCategory,
        reason_code: ReasonCode,
        reason_text: str,
        **kw: Any,
    ) -> SignalEvaluation:
        return cls(
            code=code,
            category=category,
            status=SignalStatus.NOT_APPLICABLE,
            ratio=0.0,
            confidence=Confidence.unknown(),
            reason_code=reason_code,
            reason_text=reason_text,
            **kw,
        )


@dataclass(frozen=True, slots=True)
class TrustScoreSignal:
    """A frozen, per-signal breakdown row. This *is* the explanation."""

    signal_definition_id: UUID
    signal_code: SignalCode
    category: SignalCategory
    status: SignalStatus
    weight: float
    points_awarded: float
    points_possible: float
    confidence: float
    reason_code: ReasonCode
    reason_text: str
    evidence: dict[str, Any] = field(default_factory=dict)
    source_table: str | None = None
    source_id: UUID | None = None
    id: UUID | None = None
    trust_score_id: UUID | None = None

    @property
    def points_lost(self) -> float:
        """Used to rank reasons: sellers ask "why am I not higher", so the
        biggest losses are shown first."""
        return round(self.points_possible - self.points_awarded, 3)


@dataclass(frozen=True, slots=True)
class TrustScore:
    """An immutable score computation."""

    id: UUID
    seller_id: UUID
    scoring_model_id: UUID
    scoring_model_version: str
    score: Score
    risk_level: RiskLevel
    raw_score: float
    available_weight: float
    confidence: Confidence
    trigger: ScoreTrigger
    computed_at: datetime
    valid_until: datetime
    signals: tuple[TrustScoreSignal, ...] = ()
    cap_applied: int | None = None
    is_current: bool = True
    is_manual_override: bool = False
    override_reason: str | None = None
    overridden_by: UUID | None = None

    @property
    def unavailable_signal_codes(self) -> tuple[SignalCode, ...]:
        return tuple(s.signal_code for s in self.signals if s.status == SignalStatus.UNAVAILABLE)

    @property
    def category_breakdown(self) -> dict[SignalCategory, dict[str, float | str]]:
        """Category rollup for the UI: Identity 30/30, Phone 10/15, ..."""
        out: dict[SignalCategory, dict[str, float | str]] = {}
        for signal in self.signals:
            if not signal.status.counts_toward_evidence:
                continue
            bucket = out.setdefault(
                signal.category, {"points_awarded": 0.0, "points_possible": 0.0}
            )
            bucket["points_awarded"] = float(bucket["points_awarded"]) + signal.points_awarded
            bucket["points_possible"] = float(bucket["points_possible"]) + signal.points_possible
        for bucket in out.values():
            awarded, possible = float(bucket["points_awarded"]), float(bucket["points_possible"])
            bucket["status"] = (
                "PASS" if awarded >= possible else "FAIL" if awarded == 0 else "PARTIAL"
            )
        return out

    def top_reasons(self, limit: int = 5) -> tuple[TrustScoreSignal, ...]:
        """Reasons ordered by point impact: losses first, then confirmations."""
        losses = sorted(
            (s for s in self.signals if s.points_lost > 0),
            key=lambda s: s.points_lost,
            reverse=True,
        )
        gains = sorted(
            (s for s in self.signals if s.points_lost == 0 and s.points_awarded > 0),
            key=lambda s: s.points_awarded,
            reverse=True,
        )
        return tuple((losses + gains)[:limit])

    def is_stale_at(self, now: datetime) -> bool:
        return now >= self.valid_until


__all__ = [
    "ScoringModel",
    "ScoringWeight",
    "SignalDefinition",
    "SignalEvaluation",
    "TrustScore",
    "TrustScoreSignal",
]
