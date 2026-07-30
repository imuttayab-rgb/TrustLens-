"""Tests for the scoring engine.

This is the highest-value test file in the repository: these rules decide
whether a real person is labelled a fraud risk, so every branch is covered
explicitly - especially the ones that are easy to get subtly wrong
(normalisation, hard caps, band boundaries).
"""

from __future__ import annotations

import uuid

import pytest

from trustlens.core.domain.entities import (
    ScoringModel,
    ScoringWeight,
    SignalDefinition,
    SignalEvaluation,
)
from trustlens.core.domain.enums import (
    ReasonCode,
    RiskLevel,
    SignalCategory,
    SignalCode,
    SignalStatus,
)
from trustlens.core.domain.errors import InvalidScoringModel
from trustlens.core.domain.policies import band_for
from trustlens.core.domain.policies.scoring import ScoringPolicy, rank_improvements

# ── Fixtures ─────────────────────────────────────────────────────────

#: A deliberately small three-signal model so the arithmetic in each test is
#: checkable by hand. Weight distribution mirrors the real v1 shape:
#: one critical identity signal, one contact signal, one listing signal.
_LAYOUT: tuple[tuple[SignalCode, SignalCategory, float, int | None], ...] = (
    (SignalCode.IDENTITY_FACE_MATCH, SignalCategory.IDENTITY, 50.0, 25),
    (SignalCode.PHONE_VERIFIED, SignalCategory.PHONE, 30.0, None),
    (SignalCode.LISTING_CONTENT_SAFE, SignalCategory.LISTING, 20.0, None),
)


@pytest.fixture
def definitions() -> dict[SignalCode, SignalDefinition]:
    return {
        code: SignalDefinition(
            id=uuid.uuid5(uuid.NAMESPACE_OID, code.value),
            code=code,
            category=category,
            name=code.value,
            description="",
            buyer_facing_description="",
            max_points=int(weight),
            is_critical=cap is not None,
        )
        for code, category, weight, cap in _LAYOUT
    }


@pytest.fixture
def model(definitions: dict[SignalCode, SignalDefinition]) -> ScoringModel:
    model_id = uuid.uuid4()
    return ScoringModel(
        id=model_id,
        version="test-v1",
        name="Test model",
        description="",
        is_active=True,
        weights=tuple(
            ScoringWeight(
                id=uuid.uuid4(),
                scoring_model_id=model_id,
                signal_definition_id=definitions[code].id,
                signal_code=code,
                weight=weight,
                hard_cap_on_fail=cap,
            )
            for code, _category, weight, cap in _LAYOUT
        ),
    )


@pytest.fixture
def policy(model: ScoringModel, definitions: dict[SignalCode, SignalDefinition]) -> ScoringPolicy:
    return ScoringPolicy(model, definitions, min_evidence_weight=40.0)


def _passed(code: SignalCode, category: SignalCategory) -> SignalEvaluation:
    return SignalEvaluation.passed(code, category, ReasonCode.IDENTITY_VERIFIED, "ok")


def _failed(code: SignalCode, category: SignalCategory) -> SignalEvaluation:
    return SignalEvaluation.failed(code, category, ReasonCode.FACE_MATCH_LOW, "not ok")


def _unavailable(code: SignalCode, category: SignalCategory) -> SignalEvaluation:
    return SignalEvaluation.unavailable(code, category)


ALL_CODES = [(code, category) for code, category, _w, _c in _LAYOUT]


# ── Happy paths ──────────────────────────────────────────────────────


def test_all_signals_pass_scores_100(policy: ScoringPolicy) -> None:
    result = policy.evaluate([_passed(c, cat) for c, cat in ALL_CODES])

    assert int(result.score) == 100
    assert result.risk_level is RiskLevel.LOW
    assert result.available_weight == 100.0
    assert result.cap_applied is None


def test_all_signals_fail_scores_zero(policy: ScoringPolicy) -> None:
    result = policy.evaluate([_failed(c, cat) for c, cat in ALL_CODES])

    assert int(result.score) == 0
    assert result.risk_level is RiskLevel.HIGH


def test_partial_signal_awards_fractional_points(policy: ScoringPolicy) -> None:
    result = policy.evaluate(
        [
            _passed(SignalCode.IDENTITY_FACE_MATCH, SignalCategory.IDENTITY),
            _passed(SignalCode.PHONE_VERIFIED, SignalCategory.PHONE),
            SignalEvaluation.partial(
                SignalCode.LISTING_CONTENT_SAFE,
                SignalCategory.LISTING,
                0.5,
                ReasonCode.LISTING_SCAM_PATTERN,
                "some risk",
            ),
        ]
    )

    # 50 + 30 + (20 * 0.5) = 90
    assert int(result.score) == 90
    assert result.risk_level is RiskLevel.LOW


# ── Normalisation: our outage must not cost the seller points ────────


def test_unavailable_signal_is_excluded_from_the_denominator(policy: ScoringPolicy) -> None:
    """The single most important behaviour in the engine.

    If the LLM provider is down, LISTING_CONTENT_SAFE is UNAVAILABLE. Scoring
    it as 0 would drop a fully verified seller from 100 to 80 because of *our*
    outage - unfair, and unappealable since they cannot fix it.
    """
    result = policy.evaluate(
        [
            _passed(SignalCode.IDENTITY_FACE_MATCH, SignalCategory.IDENTITY),
            _passed(SignalCode.PHONE_VERIFIED, SignalCategory.PHONE),
            _unavailable(SignalCode.LISTING_CONTENT_SAFE, SignalCategory.LISTING),
        ]
    )

    assert result.available_weight == 80.0
    assert int(result.score) == 100
    assert SignalCode.LISTING_CONTENT_SAFE in result.unavailable_codes


def test_not_applicable_signal_is_also_excluded(policy: ScoringPolicy) -> None:
    result = policy.evaluate(
        [
            _passed(SignalCode.IDENTITY_FACE_MATCH, SignalCategory.IDENTITY),
            _passed(SignalCode.PHONE_VERIFIED, SignalCategory.PHONE),
            SignalEvaluation.not_applicable(
                SignalCode.LISTING_CONTENT_SAFE,
                SignalCategory.LISTING,
                ReasonCode.NO_LISTINGS,
                "no listings",
            ),
        ]
    )

    assert result.available_weight == 80.0
    assert int(result.score) == 100


def test_missing_evaluation_is_unavailable_not_a_silent_zero(policy: ScoringPolicy) -> None:
    """A signal no collector produced must not look like a failure."""
    result = policy.evaluate([_passed(SignalCode.IDENTITY_FACE_MATCH, SignalCategory.IDENTITY)])

    listing = next(s for s in result.signals if s.signal_code == SignalCode.LISTING_CONTENT_SAFE)
    assert listing.status is SignalStatus.UNAVAILABLE
    assert listing.points_possible == 0.0


# ── Insufficient evidence ────────────────────────────────────────────


def test_insufficient_evidence_yields_unknown_not_high_risk(policy: ScoringPolicy) -> None:
    """A brand-new honest seller must not render identically to a scammer."""
    result = policy.evaluate(
        [
            _passed(SignalCode.PHONE_VERIFIED, SignalCategory.PHONE),  # 30 < min 40
            _unavailable(SignalCode.IDENTITY_FACE_MATCH, SignalCategory.IDENTITY),
            _unavailable(SignalCode.LISTING_CONTENT_SAFE, SignalCategory.LISTING),
        ]
    )

    assert result.risk_level is RiskLevel.UNKNOWN
    assert result.insufficient_evidence is True
    assert int(result.score) == 0
    assert float(result.confidence) == 0.0


def test_evidence_exactly_at_the_threshold_is_scored(
    model: ScoringModel, definitions: dict[SignalCode, SignalDefinition]
) -> None:
    policy = ScoringPolicy(model, definitions, min_evidence_weight=30.0)
    result = policy.evaluate(
        [
            _passed(SignalCode.PHONE_VERIFIED, SignalCategory.PHONE),
            _unavailable(SignalCode.IDENTITY_FACE_MATCH, SignalCategory.IDENTITY),
            _unavailable(SignalCode.LISTING_CONTENT_SAFE, SignalCategory.LISTING),
        ]
    )

    assert result.insufficient_evidence is False
    assert int(result.score) == 100


# ── Hard caps ────────────────────────────────────────────────────────


def test_failed_critical_signal_caps_the_score(policy: ScoringPolicy) -> None:
    """Without caps, failing face match but passing everything else scores 50
    - "MEDIUM risk" for someone whose identity is actively unproven."""
    result = policy.evaluate(
        [
            _failed(SignalCode.IDENTITY_FACE_MATCH, SignalCategory.IDENTITY),
            _passed(SignalCode.PHONE_VERIFIED, SignalCategory.PHONE),
            _passed(SignalCode.LISTING_CONTENT_SAFE, SignalCategory.LISTING),
        ]
    )

    assert result.raw_score == 50.0
    assert int(result.score) == 25
    assert result.cap_applied == 25
    assert result.risk_level is RiskLevel.HIGH


def test_cap_does_not_raise_an_already_lower_score(policy: ScoringPolicy) -> None:
    result = policy.evaluate(
        [
            _failed(SignalCode.IDENTITY_FACE_MATCH, SignalCategory.IDENTITY),
            _failed(SignalCode.PHONE_VERIFIED, SignalCategory.PHONE),
            _failed(SignalCode.LISTING_CONTENT_SAFE, SignalCategory.LISTING),
        ]
    )

    assert int(result.score) == 0
    assert result.cap_applied is None


def test_cap_is_not_applied_for_a_partial_result(policy: ScoringPolicy) -> None:
    """Borderline face match routes to manual review; it must not trip the cap
    that a definitive failure would."""
    result = policy.evaluate(
        [
            SignalEvaluation.partial(
                SignalCode.IDENTITY_FACE_MATCH,
                SignalCategory.IDENTITY,
                0.5,
                ReasonCode.FACE_MATCH_BORDERLINE,
                "borderline",
            ),
            _passed(SignalCode.PHONE_VERIFIED, SignalCategory.PHONE),
            _passed(SignalCode.LISTING_CONTENT_SAFE, SignalCategory.LISTING),
        ]
    )

    assert result.cap_applied is None
    assert int(result.score) == 75


# ── Band boundaries ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, RiskLevel.HIGH),
        (39, RiskLevel.HIGH),
        (40, RiskLevel.MEDIUM),
        (69, RiskLevel.MEDIUM),
        (70, RiskLevel.LOW),
        (100, RiskLevel.LOW),
    ],
)
def test_risk_band_boundaries(score: int, expected: RiskLevel) -> None:
    """Off-by-one here silently reclassifies sellers, so the edges are pinned."""
    assert band_for(score) is expected


# ── Confidence ───────────────────────────────────────────────────────


def test_confidence_drops_when_coverage_is_partial(policy: ScoringPolicy) -> None:
    """Two scores of 100 are not equally trustworthy if one used every signal
    and the other used half."""
    full = policy.evaluate([_passed(c, cat) for c, cat in ALL_CODES])
    partial = policy.evaluate(
        [
            _passed(SignalCode.IDENTITY_FACE_MATCH, SignalCategory.IDENTITY),
            _passed(SignalCode.PHONE_VERIFIED, SignalCategory.PHONE),
            _unavailable(SignalCode.LISTING_CONTENT_SAFE, SignalCategory.LISTING),
        ]
    )

    assert int(full.score) == int(partial.score) == 100
    assert float(full.confidence) > float(partial.confidence)


# ── Model validation ─────────────────────────────────────────────────


def test_model_whose_weights_do_not_sum_to_100_is_rejected(
    model: ScoringModel, definitions: dict[SignalCode, SignalDefinition]
) -> None:
    """Weights are runtime data (ADR-0007), so an invalid configuration is
    possible and must be rejected before it produces a meaningless score."""
    broken = ScoringModel(
        **{**{f: getattr(model, f) for f in model.__slots__}, "weights": model.weights[:2]}
    )

    with pytest.raises(InvalidScoringModel, match="must sum to 100"):
        ScoringPolicy(broken, definitions)


# ── Explainability ───────────────────────────────────────────────────


def test_every_evaluated_signal_appears_in_the_breakdown(policy: ScoringPolicy) -> None:
    result = policy.evaluate([_passed(c, cat) for c, cat in ALL_CODES])

    assert len(result.signals) == len(ALL_CODES)
    for signal in result.signals:
        assert signal.reason_code is not None
        assert signal.reason_text


def test_improvements_are_ranked_by_points_recoverable(
    policy: ScoringPolicy, definitions: dict[SignalCode, SignalDefinition]
) -> None:
    result = policy.evaluate(
        [
            _failed(SignalCode.IDENTITY_FACE_MATCH, SignalCategory.IDENTITY),  # -50
            _passed(SignalCode.PHONE_VERIFIED, SignalCategory.PHONE),
            _failed(SignalCode.LISTING_CONTENT_SAFE, SignalCategory.LISTING),  # -20
        ]
    )

    ranked = rank_improvements(result.signals, definitions)

    assert [code for code, _points, _action in ranked] == [
        SignalCode.IDENTITY_FACE_MATCH,
        SignalCode.LISTING_CONTENT_SAFE,
    ]
    assert ranked[0][1] == 50.0
    assert ranked[0][2]  # a concrete action, not an empty string


def test_category_rollup_sums_per_category(policy: ScoringPolicy) -> None:
    from trustlens.core.domain.entities import TrustScore
    from trustlens.core.domain.enums import ScoreTrigger
    from trustlens.core.domain.value_objects import Confidence

    computation = policy.evaluate([_passed(c, cat) for c, cat in ALL_CODES])
    now = __import__("datetime").datetime(2026, 7, 30, tzinfo=__import__("datetime").UTC)

    score = TrustScore(
        id=uuid.uuid4(),
        seller_id=uuid.uuid4(),
        scoring_model_id=uuid.uuid4(),
        scoring_model_version="test-v1",
        score=computation.score,
        risk_level=computation.risk_level,
        raw_score=computation.raw_score,
        available_weight=computation.available_weight,
        confidence=Confidence(1.0),
        trigger=ScoreTrigger.MANUAL,
        computed_at=now,
        valid_until=now,
        signals=computation.signals,
    )

    rollup = score.category_breakdown
    assert rollup[SignalCategory.IDENTITY]["points_awarded"] == 50.0
    assert rollup[SignalCategory.IDENTITY]["status"] == "PASS"
