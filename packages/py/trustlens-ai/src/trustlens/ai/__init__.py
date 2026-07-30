"""TrustLens AI adapters.

Import `factory` rather than a concrete adapter: the factory keeps heavy ML
imports lazy so the API never inherits them (ADR-0003).
"""

from trustlens.ai.factory import (
    build_face_matcher,
    build_llm_analyzer,
    build_ocr_engine,
    build_scam_classifier,
)

__all__ = [
    "build_face_matcher",
    "build_llm_analyzer",
    "build_ocr_engine",
    "build_scam_classifier",
]
