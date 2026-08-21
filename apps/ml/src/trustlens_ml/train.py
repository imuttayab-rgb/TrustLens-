"""The baseline: TF-IDF + Logistic Regression (P7-03).

**Trained first, on purpose.** A deep model's numbers mean nothing without
something to compare them against, and a linear model over TF-IDF is the right
comparison: it is fast, it is reproducible on a laptop, and - the part that
matters most for this particular product - its coefficients can be read. When
a seller appeals a listing flag, "these words pushed the score up" is an
answer. A transformer's attention weights are not.

That gives the baseline a second job beyond benchmarking. If DistilBERT wins by
a small margin (P7-04), this model may still be the one to deploy, because the
scoring engine feeds an appealable decision and the whole architecture is built
on the claim that decisions can be explained (ADR-0002).

Two failure modes this module is written to avoid:

* **Leakage through duplicates.** Public corpora contain near-identical rows.
  Splitting at random puts copies of the same advert on both sides and inflates
  every metric. Exact-duplicate text is dropped before splitting.
* **A threshold picked after seeing the test set.** The operating point is
  chosen on a validation split; the test split is scored once, at the end, with
  that threshold already fixed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from trustlens.ai.classifier.bundle import (
    ListingRecord,
    ModelBundle,
    design_matrix,
    predict_proba,
)
from trustlens.shared.logging import get_logger
from trustlens_ml.datasets.schema import Example
from trustlens_ml.evaluate import Evaluation, choose_threshold, evaluate

log = get_logger(__name__)

#: Fixed everywhere a split or an optimiser could otherwise wander. The report
#: has to be able to say "re-run this and you get the same table".
RANDOM_SEED = 20260822


@dataclass(slots=True)
class TrainingResult:
    bundle: ModelBundle
    validation: Evaluation
    test: Evaluation
    in_domain: Evaluation | None
    top_features: list[tuple[str, float]]
    rationale: str
    #: The exact held-out split and its scores.
    #:
    #: Carried rather than recomputed. The first version of the CLI re-split
    #: the corpus to draw the figures, and because `train_baseline`
    #: deduplicates *before* splitting while the caller had not, the plots were
    #: drawn on 7,750 rows while the metrics described 7,339 - a figure and a
    #: table in the same report that quietly disagreed.
    test_labels: np.ndarray | None = None
    test_scores: np.ndarray | None = None
    cross_corpus: list[Evaluation] = field(default_factory=list)


def _record(example: Example) -> ListingRecord:
    return ListingRecord(
        title=example.title,
        description=example.description,
        price=example.price,
        category=example.category,
    )


def deduplicate(examples: list[Example]) -> list[Example]:
    """Drop exact-duplicate documents, keeping the first occurrence.

    Public fraud corpora repeat adverts. A duplicate that lands in train and
    test is the model being asked a question it has already been given the
    answer to, and it shows up as a suspiciously good score rather than as an
    error.
    """
    seen: set[str] = set()
    unique: list[Example] = []
    for example in examples:
        digest = hashlib.sha256(
            f"{example.title}\n{example.description}".strip().lower().encode()
        ).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(example)

    dropped = len(examples) - len(unique)
    if dropped:
        log.info("duplicates_dropped", dropped=dropped, kept=len(unique))
    return unique


def split(
    examples: list[Example], *, test_size: float = 0.2, validation_size: float = 0.2
) -> tuple[list[Example], list[Example], list[Example]]:
    """Stratified train / validation / test.

    Stratified because at 4.8% positives a random split can hand one side
    noticeably fewer scams than the other and make two runs disagree for
    reasons that have nothing to do with the model.
    """
    from sklearn.model_selection import train_test_split

    labels = [e.label for e in examples]
    train_val, test = train_test_split(
        examples, test_size=test_size, random_state=RANDOM_SEED, stratify=labels
    )
    train, validation = train_test_split(
        train_val,
        test_size=validation_size,
        random_state=RANDOM_SEED,
        stratify=[e.label for e in train_val],
    )
    log.info(
        "split",
        train=len(train),
        validation=len(validation),
        test=len(test),
        train_positives=sum(e.label for e in train),
    )
    return train, validation, test


def train_baseline(
    examples: list[Example],
    *,
    model_version: str,
    in_domain: list[Example] | None = None,
    target_precision: float | None = None,
    max_features: int = 50_000,
) -> TrainingResult:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    examples = deduplicate(examples)
    if len({e.label for e in examples}) < 2:
        raise ValueError("training data contains only one class")

    train, validation, test = split(examples)

    vectorizer = TfidfVectorizer(
        max_features=max_features,
        # Unigrams and bigrams: "advance payment" and "money transfer" carry
        # the signal, and neither survives as single words.
        ngram_range=(1, 2),
        min_df=2,
        sublinear_tf=True,
        strip_accents="unicode",
        lowercase=True,
    )
    vectorizer.fit([_record(e).text for e in train])

    scaler = StandardScaler()
    scaler.fit(np.asarray([_record(e).numeric for e in train], dtype=np.float64))

    classifier = LogisticRegression(
        max_iter=2000,
        # The corpus is ~20:1 genuine. Without this the optimiser buys accuracy
        # by predicting "genuine" and the model never learns the minority class
        # it exists to find.
        class_weight="balanced",
        C=4.0,
        random_state=RANDOM_SEED,
        solver="liblinear",
    )

    # Built through the shared bundle so training uses the same assembly path
    # inference will. A partially-populated bundle is fine here: `design_matrix`
    # needs the vectorizer and scaler, not the classifier.
    bundle = ModelBundle(
        model_version=model_version,
        vectorizer=vectorizer,
        scaler=scaler,
        classifier=classifier,
        threshold=0.5,
    )

    classifier.fit(
        design_matrix(bundle, [_record(e) for e in train]),
        np.asarray([e.label for e in train]),
    )

    validation_scores = predict_proba(bundle, [_record(e) for e in validation])
    validation_labels = np.asarray([e.label for e in validation])
    threshold, rationale = choose_threshold(
        validation_labels, validation_scores, target_precision=target_precision
    )
    bundle.threshold = threshold
    log.info("threshold_chosen", threshold=threshold, rationale=rationale)

    validation_eval = evaluate(
        validation_labels,
        validation_scores,
        threshold=threshold,
        model="tfidf+logreg",
        corpus="proxy:validation",
        notes=rationale,
    )

    # Scored once, with the threshold already fixed.
    test_labels = np.asarray([e.label for e in test])
    test_scores = predict_proba(bundle, [_record(e) for e in test])
    test_eval = evaluate(
        test_labels,
        test_scores,
        threshold=threshold,
        model="tfidf+logreg",
        corpus="proxy:test",
        notes="held out; threshold fixed on validation before this split was scored",
    )

    in_domain_eval = None
    if in_domain:
        in_domain_eval = evaluate(
            np.asarray([e.label for e in in_domain]),
            predict_proba(bundle, [_record(e) for e in in_domain]),
            threshold=threshold,
            model="tfidf+logreg",
            corpus="in_domain:local_ads",
            notes=(
                "Pakistani marketplace ads. THIS is the number that describes "
                "the deployed task; the proxy figures above do not."
            ),
        )

    bundle.metadata = {
        "trained_at": datetime.now(UTC).isoformat(),
        "random_seed": RANDOM_SEED,
        "rows_total": len(examples),
        "rows_train": len(train),
        "rows_validation": len(validation),
        "rows_test": len(test),
        "positives_total": sum(e.label for e in examples),
        "corpora": sorted({e.corpus for e in examples}),
        "vocabulary_size": len(vectorizer.vocabulary_),
        "threshold_rationale": rationale,
        "validation": validation_eval.to_dict(),
        "test": test_eval.to_dict(),
        "in_domain": in_domain_eval.to_dict() if in_domain_eval else None,
        "in_domain_available": bool(in_domain),
    }

    return TrainingResult(
        bundle=bundle,
        validation=validation_eval,
        test=test_eval,
        in_domain=in_domain_eval,
        top_features=top_features(bundle),
        rationale=rationale,
        test_labels=test_labels,
        test_scores=test_scores,
    )


def cross_corpus_evaluate(
    examples: list[Example], *, model_version: str, target_precision: float | None = None
) -> list[Evaluation]:
    """Train on one corpus, test on another. The generalisation question.

    A single random split cannot distinguish "learned what fraud sounds like"
    from "learned what THIS dataset's fraud sounds like", because both halves
    of the split share the same quirks. Training on EMSCAD and testing on
    DIFrauD - and the reverse - separates the two.

    This exists because the first trained model's strongest scam indicators
    came back as `link`, `apply using`, `below link`, `txt` and `clerk`: the
    boilerplate of a fraudulent *job advert*, not language that would appear in
    a fraudulent listing for a used phone in Lahore. In-corpus F1 of 0.91 said
    the model was excellent. It was excellent at EMSCAD.

    The gap between the in-corpus and cross-corpus numbers is the honest
    estimate of how much of the headline figure survives contact with a
    different distribution - and TrustLens's real distribution is different
    again, and still unmeasured (P7-02).
    """
    groups: dict[str, list[Example]] = {}
    for example in examples:
        # difraud:job_scams and difraud:sms are one source for this purpose.
        groups.setdefault(example.corpus.split(":")[0], []).append(example)

    usable = {k: v for k, v in groups.items() if len({e.label for e in v}) == 2}
    if len(usable) < 2:
        log.info("cross_corpus_skipped", corpora=sorted(groups))
        return []

    results: list[Evaluation] = []
    for held_out in sorted(usable):
        train_examples = [e for key, rows in usable.items() if key != held_out for e in rows]
        test_examples = usable[held_out]

        trained = train_baseline(
            train_examples,
            model_version=f"{model_version}-xc-{held_out}",
            target_precision=target_precision,
        )
        results.append(
            evaluate(
                np.asarray([e.label for e in test_examples]),
                predict_proba(trained.bundle, [_record(e) for e in test_examples]),
                threshold=trained.bundle.threshold,
                model="tfidf+logreg",
                corpus=f"cross:trained-without-{held_out}",
                notes=(
                    f"trained on {sorted(set(usable) - {held_out})}, tested on "
                    f"{held_out!r} which it has never seen. Compare against the "
                    f"in-corpus figure: the drop is how much of the headline "
                    f"number is corpus-specific."
                ),
            )
        )
        log.info("cross_corpus_done", held_out=held_out, f1=results[-1].f1)
    return results


def top_features(bundle: ModelBundle, *, limit: int = 25) -> list[tuple[str, float]]:
    """The terms pushing hardest towards 'scam'.

    This is the explainability dividend of a linear model, and it is worth a
    figure in the report: it shows the model learned recognisable fraud
    language rather than an artefact of the corpus. It is also the first place
    to look when it has learned an artefact - a company name or a formatting
    quirk in the top 25 means the corpus leaked, not that fraud was detected.
    """
    names = list(bundle.vectorizer.get_feature_names_out())
    names.extend(f"[numeric] {f}" for f in bundle.feature_order)
    coefficients = bundle.classifier.coef_[0]
    ranked = sorted(zip(names, coefficients, strict=True), key=lambda p: p[1], reverse=True)
    return [(name, round(float(weight), 4)) for name, weight in ranked[:limit]]


def save_bundle(result: TrainingResult, model_dir: Path) -> Path:
    from trustlens.ai.classifier.bundle import save

    return save(result.bundle, model_dir / f"{result.bundle.model_version}.joblib")


__all__ = [
    "RANDOM_SEED",
    "TrainingResult",
    "cross_corpus_evaluate",
    "deduplicate",
    "save_bundle",
    "split",
    "top_features",
    "train_baseline",
]
