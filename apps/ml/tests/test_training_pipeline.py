"""The training pipeline, and the guarantees that make its numbers meaningful.

These are not accuracy tests - accuracy is measured by `trustlens-ml train` and
recorded in `reports/`. These assert the properties that decide whether that
measurement can be believed at all: no leakage across the split, a threshold
never chosen on the test set, and one shared path from listing to feature
vector for both training and serving.
"""

from __future__ import annotations

import numpy as np
import pytest

from trustlens.ai.classifier.bundle import (
    BUNDLE_FORMAT,
    ListingRecord,
    ModelBundle,
    design_matrix,
    predict_proba,
)
from trustlens_ml.datasets.schema import Example, Provenance
from trustlens_ml.evaluate import choose_threshold, evaluate, sweep_thresholds
from trustlens_ml.train import deduplicate, split, train_baseline

SCAM_PHRASES = (
    "send advance payment today only hurry",
    "token money required whatsapp me no calls",
    "deposit now bank transfer last chance only one left",
    "crypto payment accepted contact telegram stock going fast",
)
GENUINE_PHRASES = (
    "used for eight months receipt and box available meet to inspect",
    "single owner complete file non accidental inspection welcome",
    "good condition slight scratches buyer collects from model town",
    "still under warranty minor scratch can meet at the mall",
)


def _corpus(n: int = 240) -> list[Example]:
    """A separable synthetic corpus, imbalanced like the real one."""
    examples: list[Example] = []
    for i in range(n):
        scam = i % 8 == 0  # 12.5% positive
        phrases = SCAM_PHRASES if scam else GENUINE_PHRASES
        examples.append(
            Example(
                title=f"item {i}",
                description=f"{phrases[i % len(phrases)]} variant {i}",
                label=1 if scam else 0,
                corpus="synthetic",
                provenance=Provenance.PROXY,
            )
        )
    return examples


@pytest.mark.unit
def test_deduplicate_keeps_first_occurrence() -> None:
    duplicated = [
        Example("a", "same body", 0, "c", Provenance.PROXY),
        Example("a", "SAME BODY", 1, "c", Provenance.PROXY),
        Example("b", "different", 1, "c", Provenance.PROXY),
    ]
    kept = deduplicate(duplicated)
    assert len(kept) == 2
    assert kept[0].label == 0


@pytest.mark.unit
def test_split_shares_no_document_between_train_and_test() -> None:
    """Leakage inflates every metric and looks like success, not like a bug."""
    train, validation, test = split(deduplicate(_corpus()))
    keys = [{f"{e.title}|{e.description}" for e in part} for part in (train, validation, test)]
    assert not keys[0] & keys[1]
    assert not keys[0] & keys[2]
    assert not keys[1] & keys[2]


@pytest.mark.unit
def test_split_is_deterministic() -> None:
    """A report that cannot be reproduced is an anecdote."""
    first = [e.description for e in split(_corpus())[2]]
    second = [e.description for e in split(_corpus())[2]]
    assert first == second


@pytest.mark.unit
def test_threshold_is_chosen_from_the_curve_not_hardcoded() -> None:
    labels = np.array([0] * 90 + [1] * 10)
    scores = np.concatenate([np.linspace(0.0, 0.5, 90), np.linspace(0.7, 0.99, 10)])
    threshold, rationale = choose_threshold(labels, scores)
    assert 0.5 < threshold < 0.75
    assert "F1" in rationale


@pytest.mark.unit
def test_target_precision_trades_recall_for_precision() -> None:
    labels = np.array([0] * 80 + [1] * 20)
    rng = np.random.default_rng(0)
    scores = np.concatenate([rng.uniform(0.0, 0.7, 80), rng.uniform(0.3, 1.0, 20)])
    lenient, _ = choose_threshold(labels, scores)
    strict, rationale = choose_threshold(labels, scores, target_precision=0.9)
    assert strict >= lenient
    assert "precision" in rationale


@pytest.mark.unit
def test_evaluation_exposes_the_majority_class_baseline() -> None:
    """4.8% positives means 95.2% accuracy is what doing nothing scores.

    Reporting accuracy without that number beside it is the single easiest way
    to make this project look better than it is.
    """
    labels = np.array([0] * 95 + [1] * 5)
    scores = np.zeros(100)
    result = evaluate(labels, scores, threshold=0.5, model="always-genuine", corpus="test")
    assert result.accuracy == pytest.approx(0.95)
    assert result.majority_class_accuracy == pytest.approx(0.95)
    assert result.recall == 0.0  # caught nothing, despite 95% accuracy


@pytest.mark.unit
def test_sweep_is_monotonic_in_flagged_count() -> None:
    labels = np.array([0, 0, 1, 1])
    scores = np.array([0.1, 0.4, 0.6, 0.9])
    flagged = [p.flagged for p in sweep_thresholds(labels, scores)]
    assert flagged == sorted(flagged, reverse=True)


@pytest.mark.slow
def test_train_baseline_produces_a_usable_bundle() -> None:
    result = train_baseline(_corpus(400), model_version="test-clf")

    assert result.bundle.format == BUNDLE_FORMAT
    assert 0.0 < result.bundle.threshold < 1.0
    # Separable synthetic data: anything less means the pipeline is broken,
    # not that the model is weak.
    assert result.test.f1 > 0.8
    assert result.test.rows > 0
    # The evaluated split travels with the result, so figures and tables
    # cannot be drawn from different rows.
    assert result.test_labels is not None
    assert len(result.test_labels) == result.test.rows


@pytest.mark.slow
def test_bundle_round_trips_through_disk(tmp_path) -> None:
    from trustlens.ai.classifier.bundle import load, save

    result = train_baseline(_corpus(400), model_version="test-clf")
    records = [ListingRecord(title="x", description=SCAM_PHRASES[0])]
    before = predict_proba(result.bundle, records)

    reloaded = load(save(result.bundle, tmp_path / "test-clf.joblib"))
    after = predict_proba(reloaded, records)

    assert np.allclose(before, after)
    assert reloaded.threshold == result.bundle.threshold
    assert reloaded.metadata["rows_train"] == result.bundle.metadata["rows_train"]


@pytest.mark.unit
def test_bundle_rejects_a_foreign_format() -> None:
    bundle = ModelBundle(
        model_version="v",
        vectorizer=None,
        scaler=None,
        classifier=None,
        threshold=0.5,
        format="something-else/9",
    )
    with pytest.raises(ValueError, match="cannot be read"):
        bundle.validate()


@pytest.mark.unit
def test_bundle_rejects_reordered_features() -> None:
    """A reordered vector does not raise on its own - it scores wrong columns."""
    bundle = ModelBundle(
        model_version="v",
        vectorizer=None,
        scaler=None,
        classifier=None,
        threshold=0.5,
        feature_order=("word_count", "char_length"),
    )
    with pytest.raises(ValueError, match="feature order"):
        bundle.validate()


@pytest.mark.slow
def test_training_and_inference_build_identical_matrices() -> None:
    """The whole reason `bundle.py` exists.

    If these two ever diverge, the model scores well offline and behaves
    randomly in production - and nothing else in the test suite would notice.
    """
    result = train_baseline(_corpus(400), model_version="test-clf")
    record = ListingRecord(title="iPhone", description=SCAM_PHRASES[1], price=1000.0)

    from_training = design_matrix(result.bundle, [record])
    from_inference = design_matrix(result.bundle, [record])
    assert (from_training != from_inference).nnz == 0
