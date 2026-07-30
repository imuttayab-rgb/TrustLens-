"""EasyOCR adapter (mandated by the proposal)."""

from __future__ import annotations

import asyncio
from typing import Any

from trustlens.ai.ocr.cnic_parser import (
    parse_cnic_number,
    parse_dates,
    parse_father_name,
    parse_name,
    split_birth_and_expiry,
)
from trustlens.ai.ocr.preprocessing import prepare_for_ocr
from trustlens.core.domain.ports.ai import OcrResult


class EasyOcrEngine:
    """Wraps EasyOCR behind the `OcrEngine` port.

    The reader is expensive to construct (it loads model weights), so it is
    built once, lazily, and reused. Recognition is CPU-bound and runs in a
    thread so it cannot block the worker's event loop.
    """

    def __init__(
        self,
        *,
        languages: list[str] | None = None,
        use_gpu: bool = False,
        min_confidence: float = 0.6,
    ) -> None:
        self._languages = languages or ["en"]
        self._use_gpu = use_gpu
        self._min_confidence = min_confidence
        self._reader: Any = None

    def _get_reader(self) -> Any:
        if self._reader is None:
            import easyocr

            self._reader = easyocr.Reader(self._languages, gpu=self._use_gpu, verbose=False)
        return self._reader

    async def extract(self, image: bytes, *, document_type: str) -> OcrResult:
        return await asyncio.to_thread(self._extract_sync, image, document_type)

    def _extract_sync(self, image: bytes, document_type: str) -> OcrResult:
        import easyocr  # noqa: F401  (import error surfaces here, not at call time)

        prepared, quality = prepare_for_ocr(image)
        detections = self._get_reader().readtext(prepared, detail=1, paragraph=False)

        tokens = [
            {"text": text, "confidence": float(confidence), "bbox": _as_bbox(box)}
            for box, text, confidence in detections
        ]
        kept = [t for t in tokens if t["confidence"] >= self._min_confidence]
        text = "\n".join(str(t["text"]) for t in kept)
        mean_confidence = sum(float(t["confidence"]) for t in kept) / len(kept) if kept else 0.0

        if document_type == "SELFIE":
            return OcrResult(
                text="",
                confidence=mean_confidence,
                engine="easyocr",
                engine_version="1.7",
                quality_score=quality,
            )

        dates = parse_dates(text)
        birth, expiry = split_birth_and_expiry(dates)
        return OcrResult(
            text=text,
            confidence=round(mean_confidence, 4),
            engine="easyocr",
            engine_version="1.7",
            tokens=tuple(tokens),
            full_name=parse_name(text),
            cnic_number=parse_cnic_number(text),
            date_of_birth=birth,
            expiry_date=expiry,
            father_name=parse_father_name(text),
            quality_score=quality,
            raw={"token_count": len(tokens), "kept": len(kept)},
        )


def _as_bbox(box: Any) -> list[list[float]]:
    return [[float(x), float(y)] for x, y in box]


__all__ = ["EasyOcrEngine"]
