"""DeepFace adapter (mandated by the proposal)."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from trustlens.core.domain.ports.ai import FaceMatchResult


class DeepFaceMatcher:
    """Compares a selfie against the photo on an identity document.

    DeepFace works on file paths, so images are written to a temporary
    directory that is removed immediately afterwards - biometric data must not
    linger on a worker's disk.
    """

    def __init__(
        self, *, model_name: str = "ArcFace", detector_backend: str = "retinaface"
    ) -> None:
        self._model_name = model_name
        self._detector_backend = detector_backend

    async def compare(
        self, document_image: bytes, selfie_image: bytes, *, threshold: float
    ) -> FaceMatchResult:
        return await asyncio.to_thread(self._compare_sync, document_image, selfie_image, threshold)

    def _compare_sync(
        self, document_image: bytes, selfie_image: bytes, threshold: float
    ) -> FaceMatchResult:
        from deepface import DeepFace

        with tempfile.TemporaryDirectory(prefix="tl-face-") as tmp:
            doc_path = Path(tmp) / "document.jpg"
            selfie_path = Path(tmp) / "selfie.jpg"
            doc_path.write_bytes(document_image)
            selfie_path.write_bytes(selfie_image)

            try:
                result: dict[str, Any] = DeepFace.verify(
                    img1_path=str(doc_path),
                    img2_path=str(selfie_path),
                    model_name=self._model_name,
                    detector_backend=self._detector_backend,
                    enforce_detection=True,
                )
            except ValueError as exc:
                # DeepFace raises ValueError when it cannot find a face. That
                # is a user-fixable input problem ("retake your selfie"), not
                # a match failure, so it is reported distinctly.
                message = str(exc).lower()
                return FaceMatchResult(
                    similarity=0.0,
                    distance=1.0,
                    threshold=threshold,
                    engine="deepface",
                    engine_version=self._model_name,
                    face_detected_in_document="img1" not in message,
                    face_detected_in_selfie="img2" not in message,
                    raw={"error": str(exc)},
                )

        distance = float(result.get("distance", 1.0))
        model_threshold = float(result.get("threshold", 0.68))
        # DeepFace returns a distance; convert to a 0..1 similarity so the
        # domain only ever reasons about "higher is better".
        similarity = max(0.0, min(1.0, 1.0 - (distance / max(model_threshold * 2, 1e-6))))

        return FaceMatchResult(
            similarity=round(similarity, 4),
            distance=round(distance, 4),
            threshold=threshold,
            engine="deepface",
            engine_version=self._model_name,
            liveness_passed=None,  # a real liveness challenge is future scope
            raw={k: v for k, v in result.items() if k != "facial_areas"},
        )


__all__ = ["DeepFaceMatcher"]
