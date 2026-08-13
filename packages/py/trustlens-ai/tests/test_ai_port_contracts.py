"""One contract every OcrEngine and FaceMatcher must satisfy.

Written *before* the ONNX adapters, not after. The point of a ports-and-
adapters design is that a use case cannot tell which adapter it received - but
that is only true if every adapter actually behaves the same, and "it seemed to
work when I swapped it" is not that guarantee.

So this suite is parametrised over adapters rather than written per adapter.
The fake runs always. The heavy ones (easyocr/deepface, and later the ONNX
pair) run only when their extra is installed, and are skipped otherwise, so
this stays runnable on a laptop and in CI without a 2.5 GB install.

What is pinned here is the *contract*, not the accuracy:

* the declared dataclass comes back, with values in their declared ranges,
* `engine` and `engine_version` are populated - the report has to be able to
  say which model produced which number, and an unlabelled measurement is not
  a measurement,
* bad input produces a low-confidence result or a "no face found" result, and
  never an exception that escapes the adapter. A seller who uploads a blurry
  photo must get a review, not a 500 - that is the whole of P1-05.

Accuracy is Phase 1's job and needs real CNIC images (P1-01, P1-06). This is
the floor beneath that: whatever the numbers turn out to be, the shape of the
answer is the same from every engine.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from typing import Any

import pytest

from trustlens.ai.fakes import FakeFaceMatcher, FakeOcrEngine
from trustlens.core.domain.ports.ai import (
    FaceMatcher,
    FaceMatchResult,
    OcrEngine,
    OcrResult,
)

#: A one-pixel PNG. Structurally a real image, semantically nothing - which is
#: exactly the "user uploaded a screenshot of their wallpaper" case.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000100ffff03000006"
    "000557bfabd40000000049454e44ae426082"
)

#: Not an image at all. An adapter must not raise on this.
GARBAGE = b"this is not an image, it is a text file someone renamed"

#: Empty. The degenerate case that tends to reach a decoder unguarded.
EMPTY = b""


def _installed(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


# Each entry: (id, factory). Factories are lazy so an uninstalled heavy
# dependency is never imported at collection time.
OCR_ADAPTERS: list[tuple[str, Callable[[], Any]]] = [("fake", FakeOcrEngine)]
FACE_ADAPTERS: list[tuple[str, Callable[[], Any]]] = [("fake", FakeFaceMatcher)]

if _installed("easyocr"):

    def _easyocr() -> Any:
        from trustlens.ai.ocr.easyocr_engine import EasyOcrEngine

        return EasyOcrEngine(languages=["en"], use_gpu=False, min_confidence=0.3)

    OCR_ADAPTERS.append(("easyocr", _easyocr))

if _installed("deepface"):

    def _deepface() -> Any:
        from trustlens.ai.face.deepface_matcher import DeepFaceMatcher

        return DeepFaceMatcher(model_name="ArcFace", detector_backend="opencv")

    FACE_ADAPTERS.append(("deepface", _deepface))


# The ONNX adapters arrive in Step 3. Registered by import path rather than
# a direct import so this suite is already waiting for them: the day the
# module lands it is picked up here automatically and has to pass the same
# contract as everything else, with no edit to remember.
def _register_optional(
    adapters: list[tuple[str, Callable[[], Any]]],
    *,
    name: str,
    requires: str,
    module: str,
    attr: str,
) -> None:
    if not (_installed(requires) and _installed(module)):
        return

    def factory() -> Any:
        import importlib

        return getattr(importlib.import_module(module), attr)()

    adapters.append((name, factory))


_register_optional(
    OCR_ADAPTERS,
    name="rapidocr",
    requires="rapidocr_onnxruntime",
    module="trustlens.ai.ocr.rapidocr_engine",
    attr="RapidOcrEngine",
)
_register_optional(
    FACE_ADAPTERS,
    name="insightface",
    requires="insightface",
    module="trustlens.ai.face.insightface_matcher",
    attr="InsightFaceMatcher",
)


@pytest.fixture(params=[f for _, f in OCR_ADAPTERS], ids=[i for i, _ in OCR_ADAPTERS])
def ocr(request: pytest.FixtureRequest) -> OcrEngine:
    engine: OcrEngine = request.param()
    return engine


@pytest.fixture(params=[f for _, f in FACE_ADAPTERS], ids=[i for i, _ in FACE_ADAPTERS])
def face(request: pytest.FixtureRequest) -> FaceMatcher:
    matcher: FaceMatcher = request.param()
    return matcher


class TestOcrContract:
    def test_it_satisfies_the_protocol(self, ocr: OcrEngine) -> None:
        assert isinstance(ocr, OcrEngine)

    @pytest.mark.asyncio
    async def test_it_returns_an_ocr_result(self, ocr: OcrEngine) -> None:
        result = await ocr.extract(TINY_PNG, document_type="CNIC_FRONT")
        assert isinstance(result, OcrResult)

    @pytest.mark.asyncio
    async def test_confidence_is_a_ratio(self, ocr: OcrEngine) -> None:
        # The scoring policy multiplies by this. A confidence of 87 rather
        # than 0.87 would quietly award 87x the points it should.
        result = await ocr.extract(TINY_PNG, document_type="CNIC_FRONT")
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_the_engine_identifies_itself(self, ocr: OcrEngine) -> None:
        # Without this the report cannot say which model produced a number,
        # and a benchmark comparing two engines has nothing to label its rows.
        result = await ocr.extract(TINY_PNG, document_type="CNIC_FRONT")
        assert result.engine
        assert result.engine_version

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "payload", [GARBAGE, EMPTY, TINY_PNG], ids=["garbage", "empty", "tiny"]
    )
    async def test_unreadable_input_does_not_raise(self, ocr: OcrEngine, payload: bytes) -> None:
        # P1-05: an unreadable upload must become a low-confidence result that
        # routes to manual review, never an exception. A seller cannot appeal
        # against a 500, and a FAILED identity signal caps their score.
        result = await ocr.extract(payload, document_type="CNIC_FRONT")
        assert isinstance(result, OcrResult)
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_nothing_readable_means_no_claimed_fields(self, ocr: OcrEngine) -> None:
        # An engine that invents a CNIC number from noise is worse than one
        # that admits it read nothing: the invented one gets a seller verified.
        result = await ocr.extract(GARBAGE, document_type="CNIC_FRONT")
        assert not result.has_required_fields

    @pytest.mark.asyncio
    async def test_a_selfie_is_not_asked_for_document_fields(self, ocr: OcrEngine) -> None:
        result = await ocr.extract(TINY_PNG, document_type="SELFIE")
        assert result.text == ""
        assert result.cnic_number is None

    @pytest.mark.asyncio
    async def test_it_is_deterministic(self, ocr: OcrEngine) -> None:
        # The same upload must produce the same verdict. Without this a seller
        # who retries gets a different score from identical evidence, and no
        # benchmark is reproducible.
        first = await ocr.extract(TINY_PNG, document_type="CNIC_FRONT")
        second = await ocr.extract(TINY_PNG, document_type="CNIC_FRONT")
        assert first.confidence == second.confidence
        assert first.cnic_number == second.cnic_number


class TestFaceContract:
    THRESHOLD = 0.62

    def test_it_satisfies_the_protocol(self, face: FaceMatcher) -> None:
        assert isinstance(face, FaceMatcher)

    @pytest.mark.asyncio
    async def test_it_returns_a_face_match_result(self, face: FaceMatcher) -> None:
        result = await face.compare(TINY_PNG, TINY_PNG, threshold=self.THRESHOLD)
        assert isinstance(result, FaceMatchResult)

    @pytest.mark.asyncio
    async def test_similarity_is_a_ratio(self, face: FaceMatcher) -> None:
        result = await face.compare(TINY_PNG, TINY_PNG, threshold=self.THRESHOLD)
        assert 0.0 <= result.similarity <= 1.0

    @pytest.mark.asyncio
    async def test_the_threshold_is_echoed_back(self, face: FaceMatcher) -> None:
        # The caller decides the threshold; the adapter reports which one it
        # applied. A stored score whose threshold is unknown cannot be
        # re-derived later, which makes an appeal unanswerable.
        result = await face.compare(TINY_PNG, TINY_PNG, threshold=self.THRESHOLD)
        assert result.threshold == self.THRESHOLD

    @pytest.mark.asyncio
    async def test_is_match_follows_the_threshold(self, face: FaceMatcher) -> None:
        result = await face.compare(TINY_PNG, TINY_PNG, threshold=self.THRESHOLD)
        assert result.is_match == (result.similarity >= result.threshold)

    @pytest.mark.asyncio
    async def test_the_engine_identifies_itself(self, face: FaceMatcher) -> None:
        result = await face.compare(TINY_PNG, TINY_PNG, threshold=self.THRESHOLD)
        assert result.engine
        assert result.engine_version

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", [GARBAGE, EMPTY], ids=["garbage", "empty"])
    async def test_undetectable_faces_do_not_raise(self, face: FaceMatcher, payload: bytes) -> None:
        # "No face in this photo" is a user-fixable problem - retake the
        # selfie - and must be reported as evidence, not thrown. DeepFace
        # raises ValueError here; the adapter's job is to catch it.
        result = await face.compare(payload, payload, threshold=self.THRESHOLD)
        assert isinstance(result, FaceMatchResult)
        assert 0.0 <= result.similarity <= 1.0

    @pytest.mark.asyncio
    async def test_a_missing_face_is_reported_as_such(self, face: FaceMatcher) -> None:
        # Distinguishable from "compared, did not match": one means retake the
        # photo, the other means the person is not who they claim. Collapsing
        # them tells an honest seller they failed a check they never took.
        result = await face.compare(GARBAGE, GARBAGE, threshold=self.THRESHOLD)
        assert not (result.face_detected_in_document and result.face_detected_in_selfie)
        assert not result.is_match

    @pytest.mark.asyncio
    async def test_it_is_deterministic(self, face: FaceMatcher) -> None:
        first = await face.compare(TINY_PNG, TINY_PNG, threshold=self.THRESHOLD)
        second = await face.compare(TINY_PNG, TINY_PNG, threshold=self.THRESHOLD)
        assert first.similarity == second.similarity


class TestCoverage:
    def test_the_fake_is_always_exercised(self) -> None:
        # Guards the guard: if the adapter lists were ever emptied by a bad
        # refactor, every parametrised test above would silently pass zero
        # cases.
        assert "fake" in {name for name, _ in OCR_ADAPTERS}
        assert "fake" in {name for name, _ in FACE_ADAPTERS}
