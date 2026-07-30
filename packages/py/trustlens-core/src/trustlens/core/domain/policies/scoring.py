"""The Trust Score engine.

Pure functions of their inputs: no I/O, no clock, no randomness. That is what
makes the score reproducible, exhaustively testable, and defensible in an
appeal (ADR-0002).

Algorithm (docs/08 section 4):

    1. Collect signal evaluations.
    2. available_weight = sum of points_possible for signals that actually ran.
    3. earned           = sum of points_awarded.
    4. If available_weight < MIN_EVIDENCE_WEIGHT -> UNKNOWN, stop.
    5. raw = (earned / available_weight) * 100          <- normalisation
    6. Apply hard caps for failed critical signals.     <- non-negotiables
    7. score = round(clamp(raw, 0, 100))
    8. risk_level = band(score)
    9. confidence = coverage-weighted mean of evidence confidence
   10. Emit the per-signal breakdown.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from trustlens.core.domain.entities.trust_score import (
    ScoringModel,
    SignalDefinition,
    SignalEvaluation,
    TrustScoreSignal,
)
from trustlens.core.domain.enums import RiskLevel, SignalCode, SignalStatus
from trustlens.core.domain.value_objects import Confidence, Score

#: Below this much evaluated weight we decline to judge. A brand-new honest
#: seller must not be rendered identically to a proven scammer, so the verdict
#: is UNKNOWN rather than HIGH.
DEFAULT_MIN_EVIDENCE_WEIGHT = 40.0


@dataclass(frozen=True, slots=True)
class ScoreComputation:
    """The full result of one scoring run, ready to persist."""

    score: Score
    risk_level: RiskLevel
    raw_score: float
    available_weight: float
    earned_points: float
    confidence: Confidence
    signals: tuple[TrustScoreSignal, ...]
    cap_applied: int | None = None
    insufficient_evidence: bool = False

    @property
    def unavailable_codes(self) -> tuple[SignalCode, ...]:
        return tuple(s.signal_code for s in self.signals if s.status == SignalStatus.UNAVAILABLE)


class ScoringPolicy:
    """Evaluates signals against one versioned scoring model."""

    def __init__(
        self,
        model: ScoringModel,
        definitions: dict[SignalCode, SignalDefinition],
        *,
        min_evidence_weight: float = DEFAULT_MIN_EVIDENCE_WEIGHT,
    ) -> None:
        model.validate()
        self._model = model
        self._definitions = definitions
        self._min_evidence_weight = min_evidence_weight

    @property
    def model(self) -> ScoringModel:
        return self._model

    def evaluate(self, evaluations: Sequence[SignalEvaluation]) -> ScoreComputation:
        breakdown = self._build_breakdown(evaluations)

        available_weight = sum(
            s.points_possible for s in breakdown if s.status.counts_toward_evidence
        )
        earned = sum(s.points_awarded for s in breakdown if s.status.counts_toward_evidence)

        if available_weight < self._min_evidence_weight:
            return ScoreComputation(
                score=Score(0),
                risk_level=RiskLevel.UNKNOWN,
                raw_score=0.0,
                available_weight=round(available_weight, 3),
                earned_points=round(earned, 3),
                confidence=Confidence.unknown(),
                signals=breakdown,
                insufficient_evidence=True,
            )

        # Normalisation: score over what was actually evaluated. Treating an
        # UNAVAILABLE signal as 0 would penalise a seller for *our* provider
        # outage - unfair, and unappealable since they cannot fix it.
        raw_score = (earned / available_weight) * 100.0

        capped, cap_applied = self._apply_hard_caps(raw_score, breakdown)
        score = Score.clamped(capped)

        return ScoreComputation(
            score=score,
            risk_level=score.risk_level,
            raw_score=round(raw_score, 3),
            available_weight=round(available_weight, 3),
            earned_points=round(earned, 3),
            confidence=self._aggregate_confidence(breakdown, available_weight),
            signals=breakdown,
            cap_applied=cap_applied,
        )

    # ── internals ────────────────────────────────────────────────────

    def _build_breakdown(
        self, evaluations: Sequence[SignalEvaluation]
    ) -> tuple[TrustScoreSignal, ...]:
        by_code = {e.code: e for e in evaluations}
        rows: list[TrustScoreSignal] = []

        for weight in self._model.enabled_weights:
            definition = self._definitions.get(weight.signal_code)
            if definition is None or not definition.is_active:
                continue

            evaluation = by_code.get(weight.signal_code)
            if evaluation is None:
                # A configured signal that no collector produced is UNAVAILABLE,
                # not a silent zero: an omission must never look like a failure.
                evaluation = SignalEvaluation.unavailable(
                    code=weight.signal_code,
                    category=definition.category,
                    reason_text="This check has not been completed yet.",
                )

            counts = evaluation.status.counts_toward_evidence
            rows.append(
                TrustScoreSignal(
                    signal_definition_id=definition.id,
                    signal_code=evaluation.code,
                    category=evaluation.category,
                    status=evaluation.status,
                    weight=weight.weight,
                    points_awarded=round(weight.weight * evaluation.ratio, 3) if counts else 0.0,
                    points_possible=weight.weight if counts else 0.0,
                    confidence=float(evaluation.confidence),
                    reason_code=evaluation.reason_code,
                    reason_text=evaluation.reason_text,
                    evidence=evaluation.evidence,
                    source_table=evaluation.source_table,
                    source_id=evaluation.source_id,
                )
            )

        return tuple(rows)

    def _apply_hard_caps(
        self, raw_score: float, breakdown: tuple[TrustScoreSignal, ...]
    ) -> tuple[float, int | None]:
        """Clamp the score when a critical signal fails.

        A weighted sum alone is gameable: a seller who fails face match but
        passes everything else scores ~85 - "LOW risk" - which is exactly
        backwards. Caps encode the non-negotiables.
        """
        capped = raw_score
        applied: int | None = None

        for signal in breakdown:
            if signal.status != SignalStatus.FAIL:
                continue
            weight = self._model.weight_for(signal.signal_code)
            if weight is None or weight.hard_cap_on_fail is None:
                continue
            cap = float(weight.hard_cap_on_fail)
            if cap < capped:
                capped = cap
                applied = weight.hard_cap_on_fail

        return capped, applied

    @staticmethod
    def _aggregate_confidence(
        breakdown: tuple[TrustScoreSignal, ...], available_weight: float
    ) -> Confidence:
        """Weighted mean confidence, scaled by evidence coverage.

        Two scores of 74 are not equally trustworthy if one was computed from
        every signal and the other from half of them - so coverage is folded
        into the number the API publishes.
        """
        evaluated = [s for s in breakdown if s.status.counts_toward_evidence]
        if not evaluated or available_weight <= 0:
            return Confidence.unknown()

        weighted = sum(s.confidence * s.points_possible for s in evaluated)
        mean_confidence = weighted / available_weight

        total_configured = sum(s.weight for s in breakdown) or 1.0
        coverage = available_weight / total_configured

        return Confidence(round(min(1.0, mean_confidence * coverage), 3))


def rank_improvements(
    breakdown: Sequence[TrustScoreSignal],
    definitions: dict[SignalCode, SignalDefinition],
    *,
    limit: int = 5,
) -> tuple[tuple[SignalCode, float, str], ...]:
    """The "what should I fix" list, ranked by points recoverable.

    Turns the score from a verdict into a path. That distinction decides
    whether sellers cooperate with the system or resent it.
    """
    candidates = [
        (
            s.signal_code,
            s.points_lost,
            _improvement_text(s.signal_code, definitions),
        )
        for s in breakdown
        if s.points_lost > 0 and s.status != SignalStatus.NOT_APPLICABLE
    ]
    candidates.sort(key=lambda row: row[1], reverse=True)
    return tuple(candidates[:limit])


_IMPROVEMENT_ACTIONS: dict[SignalCode, str] = {
    SignalCode.IDENTITY_DOCUMENT_VALID: "Upload a clear photo of a valid, unexpired CNIC.",
    SignalCode.IDENTITY_FACE_MATCH: "Retake your selfie in good light, facing the camera directly.",
    SignalCode.PHONE_VERIFIED: "Verify your phone number with the code we send by SMS.",
    SignalCode.PHONE_NOT_DISPOSABLE: (
        "Use a mobile SIM number rather than an internet (VOIP) number."
    ),
    SignalCode.EMAIL_VERIFIED: "Confirm your email address using the link we sent you.",
    SignalCode.EMAIL_NOT_DISPOSABLE: "Use a permanent email address, not a temporary one.",
    SignalCode.DEVICE_NOT_SHARED: (
        "Sign in from your own device; this one is linked to several accounts."
    ),
    SignalCode.DEVICE_CONSISTENT: "Use a standard browser on a real device.",
    SignalCode.NETWORK_NOT_VPN: "Connect without a VPN or proxy so your location can be confirmed.",
    SignalCode.NETWORK_GEO_CONSISTENT: (
        "Make sure your profile location matches where you actually are."
    ),
    SignalCode.ACCOUNT_AGE: "This improves on its own as your account gets older.",
    SignalCode.ACTIVITY_CONSISTENT: "Keep using your account regularly.",
    SignalCode.LISTING_CONTENT_SAFE: (
        "Avoid urgency pressure and requests to move off-platform in listings."
    ),
    SignalCode.LISTING_PRICE_REALISTIC: "Price items within the normal range for their category.",
}


def _improvement_text(code: SignalCode, definitions: dict[SignalCode, SignalDefinition]) -> str:
    if action := _IMPROVEMENT_ACTIONS.get(code):
        return action
    definition = definitions.get(code)
    return definition.buyer_facing_description if definition else "Complete this check."


__all__ = [
    "DEFAULT_MIN_EVIDENCE_WEIGHT",
    "ScoreComputation",
    "ScoringPolicy",
    "rank_improvements",
]
