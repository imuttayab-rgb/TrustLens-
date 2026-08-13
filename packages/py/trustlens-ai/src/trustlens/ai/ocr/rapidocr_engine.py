"""CNIC OCR via RapidOCR (ONNX runtime).

Same job as `easyocr_engine`, one sixth of the weight. EasyOCR pulls PyTorch
(~800 MB) to run models that are a few tens of megabytes; RapidOCR runs
PaddleOCR's detection and recognition models through `onnxruntime` instead.
That is what takes the worker image from ~2.5 GB to something a free tier will
host, and it is the whole reason this file exists (see docs/20-go-live-plan).

Not a downgrade: the models are the same class of thing, and neither engine has
been measured on real CNICs yet (P1-01). Both stay in the tree behind
`OCR_ENGINE` precisely so Phase 1 can benchmark them against each other and put
a number, rather than an opinion, in the report.

Everything after the raw read - deskewing, quality scoring, CNIC field parsing,
structural validation - is shared with the EasyOCR path. Only the "turn pixels
into text tokens" step differs, which is what keeps the comparison honest.

**Measured on a dev machine (12 cores, CPU only), 2026-08-13:** ~13 s to load
the models once, then ~2 s per document. That is slow enough to matter and is
why identity verification is a queued job the seller polls, not something held
open on a request - a design this confirms rather than changes. On a free tier
with a fraction of a core it will be slower still; the number to quote in the
report is the one measured on the deployed instance, not this one.
"""

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
from trustlens.shared.logging import get_logger

log = get_logger(__name__)

ENGINE_NAME = "rapidocr"
ENGINE_VERSION = "1.3-onnx"


class RapidOcrEngine:
    """`OcrEngine` backed by RapidOCR's ONNX models."""

    def __init__(self, *, min_confidence: float = 0.60, threads: int | None = None) -> None:
        self._min_confidence = min_confidence
        # None means "let onnxruntime decide". Measured on a 12-core dev
        # machine: 1 thread ~2.6 s, 4 threads ~2.0 s per document. Worth
        # setting explicitly on a free tier, where the default guess is made
        # against the host's core count rather than the container's share.
        self._threads = threads
        self._reader: Any | None = None

    def _get_reader(self) -> Any:
        """Built once, lazily.

        Loading the detection and recognition models costs seconds (~13 s cold
        on a dev machine). The worker keeps one engine for its whole life (see
        `startup` in the worker), so this must never be per-call - and it is
        why the weights are baked into the image rather than fetched at boot.
        """
        if self._reader is None:
            from rapidocr_onnxruntime import RapidOCR

            options: dict[str, Any] = {}
            if self._threads is not None:
                options["intra_op_num_threads"] = self._threads
            self._reader = RapidOCR(**options)
        return self._reader

    async def extract(self, image: bytes, *, document_type: str) -> OcrResult:
        # Inference is CPU-bound and synchronous; off the event loop so one
        # slow document does not stall every other job in the worker.
        return await asyncio.to_thread(self._extract_sync, image, document_type)

    def _extract_sync(self, image: bytes, document_type: str) -> OcrResult:
        try:
            prepared, quality = prepare_for_ocr(image)
        except Exception as exc:
            # Undecodable bytes are a user-fixable upload problem, not a
            # server error. An exception here would become a 500 the seller
            # cannot appeal; a zero-confidence result routes them to manual
            # review instead (P1-05).
            log.info("ocr_undecodable_input", engine=ENGINE_NAME, error=type(exc).__name__)
            return _empty(reason="undecodable_image")

        try:
            detections, _elapsed = self._get_reader()(prepared)
        except Exception as exc:
            log.warning("ocr_engine_failed", engine=ENGINE_NAME, error=type(exc).__name__)
            return _empty(reason="engine_error", quality=quality)

        # RapidOCR returns None rather than an empty list when it finds
        # nothing, which is the case a plain `for` over the result would raise
        # on - and "no text in this photo" is an ordinary outcome, not a bug.
        #
        # Confidences are carried alongside as plain floats rather than read
        # back out of the dicts: a `dict[str, Any]` makes every later
        # comparison untyped, and this is arithmetic that decides whether a
        # seller's document was legible.
        tokens: list[dict[str, Any]] = []
        confidences: list[float] = []
        for box, raw_text, raw_confidence in detections or []:
            confidence = float(raw_confidence)
            tokens.append({"text": str(raw_text), "confidence": confidence, "bbox": _as_bbox(box)})
            confidences.append(confidence)

        kept = [
            (token, confidence)
            for token, confidence in zip(tokens, confidences, strict=True)
            if confidence >= self._min_confidence
        ]
        text = "\n".join(str(token["text"]) for token, _ in kept)
        mean_confidence = sum(c for _, c in kept) / len(kept) if kept else 0.0

        if document_type == "SELFIE":
            # A selfie has no fields to read. Confidence still reports how
            # legible the image was, which the quality gate uses.
            return OcrResult(
                text="",
                confidence=round(mean_confidence, 4),
                engine=ENGINE_NAME,
                engine_version=ENGINE_VERSION,
                quality_score=quality,
            )

        dates = parse_dates(text)
        birth, expiry = split_birth_and_expiry(dates)
        return OcrResult(
            text=text,
            confidence=round(mean_confidence, 4),
            engine=ENGINE_NAME,
            engine_version=ENGINE_VERSION,
            tokens=tuple(tokens),
            full_name=parse_name(text),
            cnic_number=parse_cnic_number(text),
            date_of_birth=birth,
            expiry_date=expiry,
            father_name=parse_father_name(text),
            quality_score=quality,
            raw={"engine": ENGINE_NAME, "token_count": len(tokens), "kept": len(kept)},
        )


def _empty(*, reason: str, quality: float = 0.0) -> OcrResult:
    return OcrResult(
        text="",
        confidence=0.0,
        engine=ENGINE_NAME,
        engine_version=ENGINE_VERSION,
        quality_score=quality,
        raw={"engine": ENGINE_NAME, "reason": reason},
    )


def _as_bbox(box: Any) -> list[list[float]]:
    """Normalise the polygon to plain floats.

    RapidOCR hands back numpy arrays; those do not survive JSON serialisation
    into the evidence column, and the failure would appear far from here.
    """
    try:
        return [[float(x), float(y)] for x, y in box]
    except (TypeError, ValueError):
        return []


__all__ = ["ENGINE_NAME", "ENGINE_VERSION", "RapidOcrEngine"]
