"""Real-OCR CNIC expiry pilot tests.

Every image here is SYNTHETIC: drawn with OpenCV text on a blank card, no real
person, no real CNIC, no photograph. The number 35202-1234567-1 is the repo's
documented placeholder. The real RapidOCR engine is exercised when it is
installed (the worker image ships it); the pure rules are always tested.
"""

from __future__ import annotations

from datetime import date

import pytest

from trustlens.ai.ocr.cnic_parser import parse_father_name, parse_name, split_birth_and_expiry
from trustlens.core.domain.ports.ai import OcrResult
from trustlens_worker.jobs.cnic_reading import (
    ISSUE_EXPIRY_CONFLICT,
    ISSUE_EXPIRY_IMPLAUSIBLE,
    ISSUE_EXPIRY_LOW_CONFIDENCE,
    ISSUE_SIDES_DISAGREE,
    combine_cnic_sides,
)

TEXT = (
    "Name\nTest Sample Person\nFather Name\nSample Parent Khan\nGender M\n"
    "Identity Number\n35202-1234567-1\n01.01.1990\n15.03.2021\n15.03.2031"
)


def result(
    *,
    text: str = TEXT,
    expiry: date | None = date(2031, 3, 15),
    number: str | None = "3520212345671",
    confidence: float = 0.95,
    quality: float | None = 0.8,
) -> OcrResult:
    return OcrResult(
        text=text, confidence=confidence, engine="rapidocr", engine_version="test",
        cnic_number=number, expiry_date=expiry, quality_score=quality,
    )


class TestParser:
    def test_two_dates_never_report_issue_date_as_expiry(self) -> None:
        # Measured: a card with no readable expiry line still shows birth and
        # issue dates. The later one must NOT be taken as an (expired) expiry.
        birth, expiry = split_birth_and_expiry([date(1990, 1, 1), date(2021, 3, 15)])
        assert birth == date(1990, 1, 1)
        assert expiry is None

    def test_three_dates_give_birth_and_expiry(self) -> None:
        dates = [date(1990, 1, 1), date(2021, 3, 15), date(2031, 3, 15)]
        assert split_birth_and_expiry(dates) == (date(1990, 1, 1), date(2031, 3, 15))

    def test_duplicate_dates_are_not_counted_twice(self) -> None:
        dates = [date(1990, 1, 1), date(2021, 3, 15), date(2021, 3, 15)]
        assert split_birth_and_expiry(dates)[1] is None

    def test_name_reads_next_line_and_stops_at_labels(self) -> None:
        assert parse_name(TEXT) == "Test Sample Person"
        assert parse_father_name(TEXT) == "Sample Parent Khan"

    def test_merged_label_words_are_not_names(self) -> None:
        merged = "Name\nTestSamplePerson\nFatherName\nDemoFather Name\nGender M"
        assert parse_name(merged) == "TestSamplePerson"
        # "DemoFather Name" contains the label word "Name": not trusted.
        assert parse_father_name(merged) is None


class TestCombineSides:
    def test_clear_front_gives_reliable_expiry(self) -> None:
        reading = combine_cnic_sides(result(), None)
        assert reading.expiry_reliable and reading.expiry_date == date(2031, 3, 15)
        assert reading.expiry_source == "CNIC_FRONT" and not reading.issues

    def test_expiry_on_back_is_used_when_front_has_none(self) -> None:
        reading = combine_cnic_sides(result(expiry=None), result(number=None))
        assert reading.expiry_reliable and reading.expiry_source == "CNIC_BACK"

    def test_conflicting_expiries_go_to_review(self) -> None:
        back = result(expiry=date(2030, 1, 1))
        reading = combine_cnic_sides(result(), back)
        assert not reading.expiry_reliable and ISSUE_EXPIRY_CONFLICT in reading.issues

    def test_different_numbers_on_each_side_go_to_review(self) -> None:
        reading = combine_cnic_sides(result(), result(number="3520276543213"))
        assert reading.sides_disagree and reading.cnic_number is None
        assert ISSUE_SIDES_DISAGREE in reading.issues and not reading.expiry_reliable

    @pytest.mark.parametrize(("confidence", "quality"), [(0.5, 0.8), (0.95, 0.1)])
    def test_unclear_photo_never_enforces_expiry(self, confidence: float, quality: float) -> None:
        reading = combine_cnic_sides(result(confidence=confidence, quality=quality), None)
        assert not reading.expiry_reliable and ISSUE_EXPIRY_LOW_CONFIDENCE in reading.issues

    def test_implausible_validity_span_goes_to_review(self) -> None:
        # Issue 2021 -> expiry 2022: almost certainly a mis-read year.
        text = TEXT.replace("15.03.2031", "15.03.2022")
        reading = combine_cnic_sides(result(text=text, expiry=date(2022, 3, 15)), None)
        assert not reading.expiry_reliable and ISSUE_EXPIRY_IMPLAUSIBLE in reading.issues


# ---------------------------------------------------------------------------
# The real engine on synthetic cards. Skipped only where RapidOCR is absent.
# ---------------------------------------------------------------------------


def _synthetic_card(expiry: str | None, *, blur: int = 0) -> bytes:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    image = np.full((540, 860, 3), 235, dtype=np.uint8)
    lines = [
        ("PAKISTAN  National Identity Card", 40, 60),
        ("Name", 40, 120), ("Test Sample Person", 40, 150),
        ("Father Name", 40, 200), ("Demo Father Name", 40, 230),
        ("Gender  M", 40, 280),
        ("Identity Number", 40, 330), ("35202-1234567-1", 40, 360),
        ("Date of Birth", 40, 410), ("01.01.1990", 40, 440),
        ("Date of Issue", 330, 410), ("15.03.2021", 330, 440),
    ]
    if expiry:
        lines += [("Date of Expiry", 600, 410), (expiry, 600, 440)]
    for text, x, y in lines:
        cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2,
                    cv2.LINE_AA)
    if blur:
        image = cv2.GaussianBlur(image, (blur, blur), 0)
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    assert ok
    return bytes(buffer.tobytes())


@pytest.fixture(scope="module")
def engine():  # type: ignore[no-untyped-def]
    pytest.importorskip("rapidocr_onnxruntime")
    from trustlens.ai.ocr.rapidocr_engine import RapidOcrEngine

    return RapidOcrEngine(min_confidence=0.60)


class TestRealEngineOnSyntheticCards:
    async def test_valid_card_reads_future_expiry(self, engine) -> None:  # type: ignore[no-untyped-def]
        ocr = await engine.extract(_synthetic_card("15.03.2031"), document_type="CNIC_FRONT")
        reading = combine_cnic_sides(ocr, None)
        assert ocr.engine == "rapidocr" and ocr.cnic_number == "3520212345671"
        assert reading.expiry_reliable and reading.expiry_date == date(2031, 3, 15)

    async def test_expired_card_reads_past_expiry(self, engine) -> None:  # type: ignore[no-untyped-def]
        ocr = await engine.extract(_synthetic_card("15.03.2025"), document_type="CNIC_FRONT")
        reading = combine_cnic_sides(ocr, None)
        assert reading.expiry_reliable and reading.expiry_date == date(2025, 3, 15)

    async def test_missing_expiry_is_unknown_not_expired(self, engine) -> None:  # type: ignore[no-untyped-def]
        ocr = await engine.extract(_synthetic_card(None), document_type="CNIC_FRONT")
        assert ocr.expiry_date is None
        assert not combine_cnic_sides(ocr, None).expiry_reliable

    async def test_blurred_card_is_not_enforced(self, engine) -> None:  # type: ignore[no-untyped-def]
        ocr = await engine.extract(
            _synthetic_card("15.03.2025", blur=21), document_type="CNIC_FRONT"
        )
        assert not combine_cnic_sides(ocr, None).expiry_reliable
