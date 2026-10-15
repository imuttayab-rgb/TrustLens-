"""The factory builds the adapter the configuration asked for.

`factory.py` is the only place that decides fake vs real, and now also which
real engine. That makes it the one file where a mistake is invisible: a wrong
branch does not crash, it quietly runs the wrong model, and the score still
looks plausible.

These assert on the *class chosen*, not on inference, so they run everywhere -
including on a laptop with neither the `ml` nor the `onnx` extra installed. The
heavy branches are checked by patching the import, since importing torch to
prove a branch was taken defeats the point of the branch.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from trustlens.ai import factory
from trustlens.ai.fakes import FakeFaceMatcher, FakeOcrEngine
from trustlens.shared.config.settings import AiSettings


def settings(**overrides: Any) -> AiSettings:
    """A real AiSettings, not a stand-in.

    An earlier version used a hand-rolled stub, which type-checks as the wrong
    class and - worse - would keep passing after AiSettings renamed a field the
    factory reads. Constructing the real thing means a rename breaks here
    rather than at worker startup.

    `use_fake_ai=False` because these tests are about which *real* engine gets
    chosen; the fake switch has its own test below. That switch also makes the
    LLM key mandatory - a good rule, and one worth tripping over here rather
    than at deploy time - so a placeholder is supplied. It is never used: these
    tests build OCR and face adapters, not the LLM one.
    """
    defaults: dict[str, Any] = {
        "use_fake_ai": False,
        "ai_provider": "anthropic",
        "ai_anthropic_api_key": "test-key-not-used",
    }
    return AiSettings(**{**defaults, **overrides})


@pytest.fixture
def stub_modules(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """Replace the heavy adapter modules with recording stubs.

    The real ones import torch / tensorflow / onnxruntime at construction. The
    question here is only "which class did the factory reach for", and that is
    answerable without any of them being installed.
    """
    built: dict[str, list[Any]] = {"ocr": [], "face": []}

    def _module(name: str, attr: str, bucket: str) -> None:
        module = types.ModuleType(name)

        class Recorded:
            def __init__(self, **kwargs: Any) -> None:
                self.kwargs = kwargs
                built[bucket].append(self)

        Recorded.__name__ = attr
        setattr(module, attr, Recorded)
        monkeypatch.setitem(sys.modules, name, module)

    _module("trustlens.ai.ocr.easyocr_engine", "EasyOcrEngine", "ocr")
    _module("trustlens.ai.ocr.rapidocr_engine", "RapidOcrEngine", "ocr")
    _module("trustlens.ai.face.deepface_matcher", "DeepFaceMatcher", "face")
    _module("trustlens.ai.face.insightface_matcher", "InsightFaceMatcher", "face")
    return built


class TestFakeSwitch:
    def test_fake_ai_wins_over_every_engine_choice(self) -> None:
        # USE_FAKE_AI is the offline escape hatch (NFR-8). If an engine name
        # could override it, a lab machine with no internet would try to load
        # a model and the whole demo would fail at startup.
        cfg = settings(use_fake_ai=True, ocr_engine="rapidocr", face_engine="insightface")
        assert isinstance(factory.build_ocr_engine(cfg), FakeOcrEngine)
        assert isinstance(factory.build_face_matcher(cfg), FakeFaceMatcher)

    def test_real_face_is_opt_in_without_enabling_real_ocr_or_llm(
        self, stub_modules: dict[str, list[Any]]
    ) -> None:
        # The FYP can show a REAL local 1:1 card/photo comparison without
        # switching all AI ports (which would require a paid LLM API key).
        cfg = settings(
            use_fake_ai=True,
            face_match_real_in_demo=True,
            face_engine="insightface",
            ocr_engine="rapidocr",
        )
        assert isinstance(factory.build_ocr_engine(cfg), FakeOcrEngine)
        factory.build_face_matcher(cfg)
        assert type(stub_modules["face"][-1]).__name__ == "InsightFaceMatcher"

    def test_real_ocr_is_opt_in_without_enabling_the_llm(
        self, stub_modules: dict[str, list[Any]]
    ) -> None:
        # OCR_REAL_IN_DEMO reads CNICs with the local engine while the LLM and
        # classifier stay on their offline stand-ins (no paid API key).
        from trustlens.ai.fakes import FakeScamClassifier, StubLlmAnalyzer

        cfg = settings(use_fake_ai=True, ocr_real_in_demo=True, ocr_engine="rapidocr")
        factory.build_ocr_engine(cfg)
        assert type(stub_modules["ocr"][-1]).__name__ == "RapidOcrEngine"
        assert isinstance(factory.build_llm_analyzer(cfg), StubLlmAnalyzer)
        assert isinstance(factory.build_scam_classifier(cfg), FakeScamClassifier)
        assert isinstance(factory.build_face_matcher(cfg), FakeFaceMatcher)

    def test_real_ocr_flag_defaults_off(self) -> None:
        cfg = settings(use_fake_ai=True, ocr_engine="rapidocr")
        assert cfg.ocr_real_in_demo is False
        assert isinstance(factory.build_ocr_engine(cfg), FakeOcrEngine)


class TestOcrSelection:
    def test_default_is_easyocr(self, stub_modules: dict[str, list[Any]]) -> None:
        factory.build_ocr_engine(settings())
        assert type(stub_modules["ocr"][-1]).__name__ == "EasyOcrEngine"

    def test_rapidocr_is_selected_by_name(self, stub_modules: dict[str, list[Any]]) -> None:
        factory.build_ocr_engine(settings(ocr_engine="rapidocr"))
        assert type(stub_modules["ocr"][-1]).__name__ == "RapidOcrEngine"

    def test_the_confidence_floor_reaches_the_engine(
        self, stub_modules: dict[str, list[Any]]
    ) -> None:
        # A threshold that silently defaults would change which tokens are kept
        # and therefore the confidence a seller is scored on.
        factory.build_ocr_engine(settings(ocr_engine="rapidocr", ocr_min_confidence=0.42))
        assert stub_modules["ocr"][-1].kwargs["min_confidence"] == 0.42


class TestFaceSelection:
    def test_default_is_deepface(self, stub_modules: dict[str, list[Any]]) -> None:
        factory.build_face_matcher(settings())
        assert type(stub_modules["face"][-1]).__name__ == "DeepFaceMatcher"

    def test_insightface_is_selected_by_name(self, stub_modules: dict[str, list[Any]]) -> None:
        factory.build_face_matcher(settings(face_engine="insightface"))
        assert type(stub_modules["face"][-1]).__name__ == "InsightFaceMatcher"

    def test_the_onnx_model_name_is_passed_through(
        self, stub_modules: dict[str, list[Any]]
    ) -> None:
        # buffalo_s and buffalo_l differ by ~250 MB and a cold start. Getting
        # the wrong one deployed is exactly the mistake that fits on a free
        # tier in testing and does not in production.
        factory.build_face_matcher(settings(face_engine="insightface", face_onnx_model="buffalo_l"))
        assert stub_modules["face"][-1].kwargs["model_name"] == "buffalo_l"

    def test_deepface_does_not_receive_the_onnx_model(
        self, stub_modules: dict[str, list[Any]]
    ) -> None:
        # The two engines name their models differently (ArcFace vs buffalo_s).
        # Crossing them would be a TypeError at worker startup, in production.
        factory.build_face_matcher(settings(face_onnx_model="buffalo_l"))
        assert stub_modules["face"][-1].kwargs["model_name"] == "ArcFace"


class TestSettingsContract:
    def test_the_real_settings_expose_what_the_factory_reads(self) -> None:
        # These are the fields factory.py reads. Naming them explicitly means
        # a rename fails here rather than at worker startup in production.
        for field in (
            "ocr_engine", "face_engine", "face_onnx_model", "use_fake_ai",
            "face_match_real_in_demo", "ocr_real_in_demo",
        ):
            assert field in AiSettings.model_fields, f"AiSettings lost {field}"

    def test_engine_names_are_constrained(self) -> None:
        # A free-text engine name would fall through to the default branch and
        # run the heavy engine while the config claimed otherwise.
        with pytest.raises(ValueError, match="ocr_engine"):
            # A str where a Literal is declared: mypy rejects it statically,
            # and this proves pydantic rejects it at runtime too - the case
            # that matters, since the value arrives from an env var.
            AiSettings(ocr_engine="tesseract")
