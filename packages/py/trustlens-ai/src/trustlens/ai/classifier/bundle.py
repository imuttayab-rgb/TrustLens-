"""The trained-classifier artifact: its shape, and the one path that scores it.

**This module is the train/serve contract.** `apps/ml` fits the estimators and
writes a bundle; the worker loads that bundle and scores listings. Both go
through `design_matrix` here, so there is exactly one implementation of "turn a
listing into the numbers the model expects".

Feature skew is the classic way a classifier scores 0.94 offline and behaves
randomly in production, and the existing `features.py` already guards the
numeric half of it. This extends the same guarantee to the text half, which is
where most of the signal in a marketplace ad actually lives.

**Why a dict of stock estimators rather than a `sklearn.Pipeline`.** Unpickling
restores classes by import path, so a custom transformer defined in `apps/ml`
would have to be importable inside the worker image - which would drag the
training package into production and break the layering the project enforces
everywhere else. Every object in this bundle is a stock scikit-learn estimator,
so the worker needs `scikit-learn` (which it already has, for both engine
extras) and nothing from `apps/ml`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from trustlens.ai.classifier.features import FEATURE_ORDER, extract_features, to_vector

if TYPE_CHECKING:  # pragma: no cover - typing only
    import numpy as np

#: Bumped when the bundle layout changes in a way an older loader cannot read.
#: Stored in the artifact and checked on load, so a stale model fails loudly at
#: startup rather than producing quiet nonsense.
BUNDLE_FORMAT = "trustlens-scam-classifier/1"


@dataclass(frozen=True, slots=True)
class ListingRecord:
    """One listing, as both training and inference see it."""

    title: str
    description: str
    price: float | None = None
    category: str | None = None

    @property
    def text(self) -> str:
        return f"{self.title}\n{self.description}".strip()

    @property
    def numeric(self) -> list[float]:
        return to_vector(
            extract_features(
                title=self.title,
                description=self.description,
                price=self.price,
                category=self.category,
            )
        )


@dataclass(slots=True)
class ModelBundle:
    """A fitted model plus everything needed to interpret and defend it.

    The metadata is not decoration. A `listing_analyses` row records a model
    version, and an appeal months later has to be answerable with "this is the
    model that made that call, here is what it scored, and here is the point on
    the curve we chose". That requires the metrics and the threshold to travel
    with the weights.
    """

    model_version: str
    vectorizer: Any
    scaler: Any
    classifier: Any
    threshold: float
    feature_order: tuple[str, ...] = FEATURE_ORDER
    format: str = BUNDLE_FORMAT
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.format != BUNDLE_FORMAT:
            raise ValueError(
                f"artifact format {self.format!r} cannot be read by this build "
                f"(expected {BUNDLE_FORMAT!r}). Retrain, or pin the older worker."
            )
        # A reordered feature vector does not raise - it silently scores the
        # wrong column, which is worse. Compare explicitly.
        if tuple(self.feature_order) != FEATURE_ORDER:
            raise ValueError(
                "feature order in the artifact does not match this build of "
                "trustlens.ai. The numeric features would be scored in the "
                "wrong positions. Retrain against this version."
            )


def design_matrix(bundle: ModelBundle, records: list[ListingRecord]) -> Any:
    """Text features and numeric features, side by side, in a fixed order.

    Called by training (after fitting) and by inference (after loading). If it
    is ever called from only one of them, that is the bug this module exists to
    prevent.
    """
    import numpy as np
    from scipy.sparse import csr_matrix, hstack

    text_block = bundle.vectorizer.transform([r.text for r in records])
    numeric_block = np.asarray([r.numeric for r in records], dtype=np.float64)
    if bundle.scaler is not None:
        numeric_block = bundle.scaler.transform(numeric_block)
    return hstack([text_block, csr_matrix(numeric_block)], format="csr")


def predict_proba(bundle: ModelBundle, records: list[ListingRecord]) -> np.ndarray:
    """Probability of the positive (scam) class, one per record."""
    import numpy as np

    matrix = design_matrix(bundle, records)
    return np.asarray(bundle.classifier.predict_proba(matrix)[:, 1])


def save(bundle: ModelBundle, path: Path) -> Path:
    import joblib

    bundle.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path, compress=3)
    return path


def load(path: Path) -> ModelBundle:
    import joblib

    bundle: ModelBundle = joblib.load(path)
    bundle.validate()
    return bundle


__all__ = [
    "BUNDLE_FORMAT",
    "ListingRecord",
    "ModelBundle",
    "design_matrix",
    "load",
    "predict_proba",
    "save",
]
