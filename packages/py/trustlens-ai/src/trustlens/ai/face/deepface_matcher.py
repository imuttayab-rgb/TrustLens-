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
        self._compare_lock = asyncio.Lock()

    async def compare(
        self, document_image: bytes, selfie_image: bytes, *, threshold: float
    ) -> FaceMatchResult:
        async with self._compare_lock:
            return await asyncio.to_thread(
                self._compare_sync, document_image, selfie_image, threshold
            )

    async def compare_profile(
        self, photo: bytes, reference: bytes, *, threshold: float
    ) -> FaceMatchResult:
        async with self._compare_lock:
            return await asyncio.to_thread(self._profile_sync, photo, reference, threshold)

    def _profile_sync(self, photo: bytes, reference: bytes, threshold: float) -> FaceMatchResult:
        import dataclasses

        import cv2
        import numpy as np
        from deepface import DeepFace

        counts = []
        try:
            for raw in (photo, reference):
                decoded = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
                if decoded is None:
                    raise ValueError("Unreadable photo")
                faces = DeepFace.extract_faces(
                    img_path=decoded,
                    detector_backend=self._detector_backend,
                    enforce_detection=True,
                )
                counts.append(len(faces))
                if (
                    len(faces) != 1
                    or min(faces[0]["facial_area"]["w"], faces[0]["facial_area"]["h"]) < 80
                ):
                    raise ValueError("One clear face required")
        except ValueError:
            return FaceMatchResult(
                similarity=0,
                distance=1,
                threshold=threshold,
                engine="deepface",
                engine_version=self._model_name,
                face_detected_in_document=False,
                face_detected_in_selfie=False,
                raw={
                    "profile_face_count": counts[0] if counts else 0,
                    "reference_face_count": counts[1] if len(counts) > 1 else 0,
                    "reason": "one_clear_face_required",
                },
            )
        result = self._compare_sync(photo, reference, threshold)
        return dataclasses.replace(
            result, raw={**result.raw, "profile_face_count": 1, "reference_face_count": 1}
        )

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
