"""Trained scam-listing classifier (the proposal's custom model).

Loads an artifact produced by `apps/ml` and scores listings through the shared
path in `bundle.py`, so training and inference cannot drift apart.

---

**Read this before enabling it in production.**

The shipped `scam-clf-v1` scores F1 0.906 on a held-out split of the corpora it
was trained on. That number does not describe this product's task. Trained on
one fraud corpus and tested on another it has never seen, F1 falls to **0.68
and 0.44**, with precision as low as **0.32** - two out of every three flags
wrong. The training corpora are English job adverts and scam SMS; TrustLens
scores Urdu-and-English marketplace ads for physical goods in Pakistan.

That matters here specifically because `jobs/listings.py` combines this with
the LLM verdict as `max(llm_risk, classifier_probability * 100)`. A false
positive is not averaged away - it becomes the listing's risk score, and flows
into a seller's trust score.

So the artifact is real, the pipeline is real, and the number in the report
must be the cross-corpus one. Enabling this as a live scoring input is gated on
the in-domain corpus (P7-02): a few hundred hand-labelled Pakistani ads, which
is the only evidence that would justify it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from trustlens.ai.classifier.bundle import ListingRecord, ModelBundle, predict_proba
from trustlens.ai.classifier.bundle import load as load_bundle
from trustlens.ai.classifier.features import FEATURE_ORDER
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
        threshold: float | None = None,
        model_dir: Path | None = None,
    ) -> None:
        self._model_version = model_version
        #: `None` means "use the threshold the artifact was calibrated with".
        #: A configured value overrides it, which is how an operator moves the
        #: operating point without retraining - but the default deliberately
        #: comes from the model, because the threshold was chosen against a
        #: validation curve and a number typed into an env var was not.
        self._threshold_override = threshold
        self._model_dir = model_dir or DEFAULT_MODEL_DIR
        self._bundle: ModelBundle | None = None

    def _load(self) -> ModelBundle:
        if self._bundle is None:
            path = self._model_dir / f"{self._model_version}.joblib"
            if not path.exists():
                raise FileNotFoundError(
                    f"classifier artifact {path} not found. "
                    "Train it with `make -C apps/ml train`, or set USE_FAKE_AI=true."
                )
            self._bundle = load_bundle(path)
            log.info(
                "classifier_loaded",
                model_version=self._bundle.model_version,
                threshold=self._bundle.threshold,
                trained_at=self._bundle.metadata.get("trained_at"),
            )
        return self._bundle

    @property
    def _threshold(self) -> float:
        if self._threshold_override is not None:
            return self._threshold_override
        return self._load().threshold

    async def predict(
        self,
        *,
        title: str,
        description: str,
        price: float | None,
        category: str | None,
    ) -> ClassifierResult:
        record = ListingRecord(title=title, description=description, price=price, category=category)
        probability = await asyncio.to_thread(self._predict_sync, record)
        threshold = self._threshold

        return ClassifierResult(
            scam_probability=round(probability, 4),
            label="scam" if probability >= threshold else "genuine",
            model_version=self._model_version,
            threshold=threshold,
            features_used=FEATURE_ORDER,
            raw={
                "numeric_features": dict(zip(FEATURE_ORDER, record.numeric, strict=True)),
                # Carried onto the analysis row so a later appeal can see which
                # model version and operating point produced the call, without
                # having to reconstruct them from a deployment log.
                "threshold_source": (
                    "config" if self._threshold_override is not None else "artifact"
                ),
            },
        )

    def _predict_sync(self, record: ListingRecord) -> float:
        return float(predict_proba(self._load(), [record])[0])


__all__ = ["TrainedScamClassifier"]
