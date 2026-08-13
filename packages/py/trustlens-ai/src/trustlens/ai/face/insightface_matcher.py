"""Face matching via InsightFace (ONNX runtime).

Same job as `deepface_matcher`, without TensorFlow. DeepFace is a wrapper: the
model it reaches for by default *is* ArcFace, and ArcFace is InsightFace's. So
this runs the same family of model through `onnxruntime` and drops ~600 MB from
the worker image, which is what lets the whole system sit on a free tier
(docs/20-go-live-plan).

Two differences from the DeepFace path worth knowing:

* **No temp files.** DeepFace works on paths, so images had to be written to
  disk and deleted. This decodes in memory, so biometric data never touches a
  worker's filesystem at all - strictly better for something the purge job
  otherwise has to chase.
* **Cosine similarity, directly.** ArcFace embeddings are unit vectors, so
  their dot product *is* the cosine similarity in [-1, 1]. DeepFace returns a
  distance which the adapter then has to convert back with a fudge factor. Here
  the number the domain reasons about comes straight out of the model.

Neither engine has been measured on real CNICs yet (P1-01), which is why both
stay behind `FACE_ENGINE` for Phase 1 to benchmark.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from trustlens.core.domain.ports.ai import FaceMatchResult
from trustlens.shared.logging import get_logger

log = get_logger(__name__)

ENGINE_NAME = "insightface"

#: `buffalo_s` rather than `buffalo_l`: ~50 MB against ~300 MB, for a small
#: accuracy cost on a CPU-only free tier where the large model's cold start is
#: the difference between a demo that works and one that times out. Phase 1
#: measures whether that trade is acceptable.
DEFAULT_MODEL = "buffalo_s"

#: Below this the crop is too small or too blurred for the embedding to mean
#: anything. Reported as "no usable face" rather than a low similarity, because
#: those tell the seller opposite things: retake the photo, versus you are not
#: who you claim to be.
MIN_FACE_PIXELS = 40


class InsightFaceMatcher:
    """`FaceMatcher` backed by InsightFace's ONNX models."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_MODEL,
        det_size: int = 640,
        model_root: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._det_size = det_size
        # Read from the environment rather than hard-coded, so the same class
        # works from a checkout (default cache) and from the image (baked
        # weights) without a second code path.
        self._model_root = model_root or os.environ.get("INSIGHTFACE_HOME", "~/.insightface")
        self._app: Any | None = None

    def _get_app(self) -> Any:
        """Built once, lazily - model load is seconds, not milliseconds.

        Weights are read from `INSIGHTFACE_HOME` (`/app/models` in the image,
        baked at build time). InsightFace otherwise downloads them to
        `~/.insightface` on first use, which turns the first verification after
        a deploy into a several-hundred-megabyte fetch - on a free tier that
        cold-starts, that is a job that times out rather than a job that is
        slow, and it fails for a seller rather than for us.
        """
        if self._app is None:
            from insightface.app import FaceAnalysis

            app = FaceAnalysis(
                name=self._model_name,
                root=self._model_root,
                # Detection and recognition only. The bundled age/gender and
                # landmark models are weight we would load and never call.
                allowed_modules=["detection", "recognition"],
                providers=["CPUExecutionProvider"],
            )
            app.prepare(ctx_id=-1, det_size=(self._det_size, self._det_size))
            self._app = app
        return self._app

    async def compare(
        self, document_image: bytes, selfie_image: bytes, *, threshold: float
    ) -> FaceMatchResult:
        return await asyncio.to_thread(self._compare_sync, document_image, selfie_image, threshold)

    def _compare_sync(
        self, document_image: bytes, selfie_image: bytes, threshold: float
    ) -> FaceMatchResult:
        try:
            import numpy as np
        except ImportError:  # pragma: no cover - the onnx extra guarantees it
            raise

        doc_face = self._largest_face(document_image, "document")
        selfie_face = self._largest_face(selfie_image, "selfie")

        if doc_face is None or selfie_face is None:
            # A user-fixable input problem, reported as evidence rather than
            # raised: a seller cannot appeal against a 500, and a FAILED
            # identity signal caps their score (P1-05).
            return FaceMatchResult(
                similarity=0.0,
                distance=1.0,
                threshold=threshold,
                engine=ENGINE_NAME,
                engine_version=self._model_name,
                face_detected_in_document=doc_face is not None,
                face_detected_in_selfie=selfie_face is not None,
                quality_score=0.0,
                raw={"engine": ENGINE_NAME, "reason": "no_face_detected"},
            )

        # ArcFace embeddings are already L2-normalised, so the dot product is
        # the cosine similarity. Normalising again defensively costs nothing
        # and stops a model variant that does not normalise from silently
        # producing similarities above 1.
        a = doc_face.embedding / (np.linalg.norm(doc_face.embedding) + 1e-10)
        b = selfie_face.embedding / (np.linalg.norm(selfie_face.embedding) + 1e-10)
        cosine = float(np.dot(a, b))

        # Cosine lives in [-1, 1]; the domain reasons in [0, 1] where higher is
        # better. Mapped rather than clamped, so an actively dissimilar pair
        # (negative cosine) lands near 0 instead of piling up exactly at it.
        similarity = max(0.0, min(1.0, (cosine + 1.0) / 2.0))

        return FaceMatchResult(
            similarity=round(similarity, 4),
            distance=round(1.0 - similarity, 4),
            threshold=threshold,
            engine=ENGINE_NAME,
            engine_version=self._model_name,
            # A real liveness challenge is future scope, and claiming one that
            # does not exist would be worse than admitting it (P1-08).
            liveness_passed=None,
            quality_score=round(min(float(doc_face.det_score), float(selfie_face.det_score)), 4),
            raw={
                "engine": ENGINE_NAME,
                "cosine": round(cosine, 4),
                "doc_det_score": round(float(doc_face.det_score), 4),
                "selfie_det_score": round(float(selfie_face.det_score), 4),
            },
        )

    def _largest_face(self, image: bytes, label: str) -> Any | None:
        """The biggest detected face, or None.

        Biggest rather than first: a CNIC photographed on a desk may catch a
        bystander in frame, and the document holder is the one filling it.
        """
        try:
            import cv2
            import numpy as np

            buffer = np.frombuffer(image, dtype=np.uint8)
            decoded = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        except Exception as exc:
            log.info("face_undecodable_input", side=label, error=type(exc).__name__)
            return None

        if decoded is None:
            # Not an image. cv2 signals this by returning None rather than
            # raising, which is easy to miss and would crash on the next line.
            return None

        try:
            faces = self._get_app().get(decoded)
        except Exception as exc:
            log.warning("face_engine_failed", side=label, error=type(exc).__name__)
            return None

        usable = [f for f in faces if _face_width(f) >= MIN_FACE_PIXELS]
        if not usable:
            return None
        return max(usable, key=_face_width)


def _face_width(face: Any) -> float:
    left, _top, right, _bottom = face.bbox
    return float(right - left)


__all__ = ["DEFAULT_MODEL", "ENGINE_NAME", "MIN_FACE_PIXELS", "InsightFaceMatcher"]
