"""Trained scam-listing classifier (the proposal's custom model)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from trustlens.ai.classifier.features import FEATURE_ORDER, extract_features, to_vector
from trustlens.core.domain.ports.ai import ClassifierResult
from trustlens.shared.logging import get_logger

log = get_logger(__name__)

DEFAULT_MODEL_DIR = Path("apps/ml/models")


class TrainedScamClassifier:
    """Loads a versioned artifact produced by apps/ml.

    If the artifact is missing, this raises rather than silently falling back
    to a heuristic: a model version recorded on a `listing_analyses` row must
    correspond to the model that actually made the prediction.
    """

    def __init__(
        self,
        *,
        model_version: str,
        threshold: float = 0.65,
        model_dir: Path | None = None,
    ) -> None:
        self._model_version = model_version
        self._threshold = threshold
        self._model_dir = model_dir or DEFAULT_MODEL_DIR
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            import joblib

            path = self._model_dir / f"{self._model_version}.joblib"
            if not path.exists():
                raise FileNotFoundError(
                    f"classifier artifact {path} not found. "
                    "Train it with `make -C apps/ml train`, or set USE_FAKE_AI=true."
                )
            self._model = joblib.load(path)
        return self._model

    async def predict(
        self,
        *,
        title: str,
        description: str,
        price: float | None,
        category: str | None,
    ) -> ClassifierResult:
        features = extract_features(
            title=title, description=description, price=price, category=category
        )
        probability = await asyncio.to_thread(self._predict_sync, features)

        return ClassifierResult(
            scam_probability=round(probability, 4),
            label="scam" if probability >= self._threshold else "genuine",
            model_version=self._model_version,
            threshold=self._threshold,
            features_used=FEATURE_ORDER,
            raw={"features": features},
        )

    def _predict_sync(self, features: dict[str, float]) -> float:
        model = self._load()
        return float(model.predict_proba([to_vector(features)])[0][1])


__all__ = ["TrainedScamClassifier"]
