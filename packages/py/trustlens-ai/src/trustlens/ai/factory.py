"""Builds the AI adapters for the current configuration.

This is the one place that decides fake vs real. Heavy ML imports happen
lazily *inside* the branches, so importing this module from the API never
pulls in torch or tensorflow - which is what keeps the API image at ~200 MB
and the import-linter `api-has-no-ml-deps` contract green (ADR-0003).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trustlens.shared.config.settings import AiSettings
from trustlens.shared.logging import get_logger

if TYPE_CHECKING:
    from trustlens.core.domain.ports.ai import (
        FaceMatcher,
        LlmAnalyzer,
        OcrEngine,
        ScamClassifier,
    )

log = get_logger(__name__)


def build_ocr_engine(settings: AiSettings) -> OcrEngine:
    if settings.use_fake_ai:
        from trustlens.ai.fakes import FakeOcrEngine

        return FakeOcrEngine()

    from trustlens.ai.ocr.easyocr_engine import EasyOcrEngine

    return EasyOcrEngine(
        languages=settings.ocr_languages,
        use_gpu=settings.ocr_gpu,
        min_confidence=settings.ocr_min_confidence,
    )


def build_face_matcher(settings: AiSettings) -> FaceMatcher:
    if settings.use_fake_ai:
        from trustlens.ai.fakes import FakeFaceMatcher

        return FakeFaceMatcher()

    from trustlens.ai.face.deepface_matcher import DeepFaceMatcher

    return DeepFaceMatcher(
        model_name=settings.face_match_model,
        detector_backend=settings.face_detector_backend,
    )


def build_llm_analyzer(settings: AiSettings) -> LlmAnalyzer:
    """Either vendor satisfies `LlmAnalyzer`.

    Both pass the same contract test suite, so a use case genuinely cannot
    tell which one it received - Liskov substitution used deliberately rather
    than incidentally.
    """
    if settings.use_fake_ai:
        from trustlens.ai.fakes import StubLlmAnalyzer

        return StubLlmAnalyzer()

    if settings.ai_provider == "anthropic":
        from trustlens.ai.llm.anthropic_analyzer import AnthropicAnalyzer

        assert settings.ai_anthropic_api_key is not None  # validated by Settings
        return AnthropicAnalyzer(
            api_key=settings.ai_anthropic_api_key.get_secret_value(),
            model=settings.ai_anthropic_model,
            timeout=settings.ai_request_timeout_seconds,
            max_retries=settings.ai_max_retries,
            max_output_tokens=settings.ai_max_output_tokens,
            prompt_version=settings.ai_prompt_version,
        )

    from trustlens.ai.llm.openai_analyzer import OpenAiAnalyzer

    assert settings.ai_openai_api_key is not None
    return OpenAiAnalyzer(
        api_key=settings.ai_openai_api_key.get_secret_value(),
        model=settings.ai_openai_model,
        timeout=settings.ai_request_timeout_seconds,
        max_retries=settings.ai_max_retries,
        max_output_tokens=settings.ai_max_output_tokens,
        prompt_version=settings.ai_prompt_version,
    )


def build_scam_classifier(settings: AiSettings) -> ScamClassifier:
    if settings.use_fake_ai:
        from trustlens.ai.fakes import FakeScamClassifier

        return FakeScamClassifier(threshold=settings.classifier_threshold)

    from trustlens.ai.classifier.scam_classifier import TrainedScamClassifier

    return TrainedScamClassifier(
        model_version=settings.classifier_model_version,
        threshold=settings.classifier_threshold,
    )


__all__ = [
    "build_face_matcher",
    "build_llm_analyzer",
    "build_ocr_engine",
    "build_scam_classifier",
]
