"""Combine real OCR from both CNIC sides into one cautious reading.

Why this exists: OCR reads printed characters; it cannot prove a card is
genuine. The only automatic decision TrustLens takes from OCR is "this card
has clearly expired". That is a hard rejection, so it must rest on a reading
we trust:

* the expiry was found on exactly one consistent date (no conflict between
  the front and the back),
* the photo was sharp/bright enough and the OCR was confident, and
* both sides do not disagree about the CNIC number (a mismatch can mean two
  different cards were shown).

Anything short of that is reported as an *issue* and routed to a human
reviewer instead of rejecting a possibly valid seller. Pure functions only:
no I/O, no logging of personal data, deterministic for tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from trustlens.ai.ocr.cnic_parser import parse_dates
from trustlens.ai.ocr.cnic_validation import normalise_cnic
from trustlens.core.domain.ports.ai import OcrResult

#: Below this preprocessing quality (0..1, blur/exposure) an expiry date is
#: shown to the reviewer but never used for an automatic rejection.
MIN_QUALITY_FOR_EXPIRY = 0.25
#: Mean OCR token confidence required before an expiry can reject a seller.
MIN_CONFIDENCE_FOR_EXPIRY = 0.70
#: Plausible CNIC validity window (issue -> expiry), in years. A gap outside
#: it usually means one digit of a year was mis-read (2031 read as 2024), so
#: the date goes to a human instead of rejecting a possibly valid card.
MIN_VALIDITY_YEARS = 4
MAX_VALIDITY_YEARS = 16

# Short machine codes; the review queue stores at most 120 characters.
ISSUE_SIDES_DISAGREE = "CNIC_SIDES_DISAGREE"
ISSUE_EXPIRY_CONFLICT = "CNIC_EXPIRY_CONFLICT"
ISSUE_EXPIRY_LOW_CONFIDENCE = "CNIC_EXPIRY_LOW_CONFIDENCE"
ISSUE_EXPIRY_IMPLAUSIBLE = "CNIC_EXPIRY_IMPLAUSIBLE"
ISSUE_EXPIRY_UNREADABLE = "CNIC_EXPIRY_UNREADABLE"


@dataclass(frozen=True, slots=True)
class CnicReading:
    """What the two sides of the card say, plus why a human may be needed."""

    cnic_number: str | None
    expiry_date: date | None
    #: Which side the expiry came from ("CNIC_FRONT" / "CNIC_BACK").
    expiry_source: str | None
    #: True only when `expiry_date` is safe to enforce automatically.
    expiry_reliable: bool
    sides_disagree: bool
    combined_text: str
    issues: tuple[str, ...] = ()


def _readable_enough(result: OcrResult) -> bool:
    quality_ok = result.quality_score is None or result.quality_score >= MIN_QUALITY_FOR_EXPIRY
    return quality_ok and result.confidence >= MIN_CONFIDENCE_FOR_EXPIRY


def _validity_plausible(result: OcrResult, expiry: date) -> bool:
    """Issue date (second-latest printed date) must sit a normal span before expiry."""
    dates = sorted(set(parse_dates(result.text)))
    if len(dates) < 3 or dates[-1] != expiry:
        return False
    issue = dates[-2]
    years = (expiry - issue).days / 365.25
    return MIN_VALIDITY_YEARS <= years <= MAX_VALIDITY_YEARS


def combine_cnic_sides(front: OcrResult, back: OcrResult | None) -> CnicReading:
    """Merge front and (optional) back OCR into one conservative reading."""
    sides = [("CNIC_FRONT", front)] + ([("CNIC_BACK", back)] if back is not None else [])
    issues: list[str] = []

    numbers = {
        number for _, result in sides if (number := normalise_cnic(result.cnic_number)) is not None
    }
    sides_disagree = len(numbers) > 1
    if sides_disagree:
        issues.append(ISSUE_SIDES_DISAGREE)
    # Prefer the front number, but never pick one when the sides disagree:
    # a wrong number could create a false "duplicate account" rejection.
    cnic_number = None if sides_disagree else next(iter(numbers), None)

    found = [(side, result) for side, result in sides if result.expiry_date is not None]
    distinct = {result.expiry_date for _, result in found}
    expiry_date: date | None = None
    expiry_source: str | None = None
    expiry_reliable = False
    if len(distinct) > 1:
        issues.append(ISSUE_EXPIRY_CONFLICT)
    elif found:
        expiry_source, source_result = found[0]
        expiry_date = source_result.expiry_date
        if not _readable_enough(source_result) or sides_disagree:
            issues.append(ISSUE_EXPIRY_LOW_CONFIDENCE)
        elif expiry_date is None or not _validity_plausible(source_result, expiry_date):
            issues.append(ISSUE_EXPIRY_IMPLAUSIBLE)
        else:
            expiry_reliable = True

    combined_text = "\n".join(result.text for _, result in sides if result.text)
    return CnicReading(
        cnic_number=cnic_number,
        expiry_date=expiry_date,
        expiry_source=expiry_source,
        expiry_reliable=expiry_reliable,
        sides_disagree=sides_disagree,
        combined_text=combined_text,
        issues=tuple(issues),
    )


__all__ = [
    "ISSUE_EXPIRY_CONFLICT",
    "ISSUE_EXPIRY_IMPLAUSIBLE",
    "ISSUE_EXPIRY_LOW_CONFIDENCE",
    "ISSUE_EXPIRY_UNREADABLE",
    "ISSUE_SIDES_DISAGREE",
    "MAX_VALIDITY_YEARS",
    "MIN_CONFIDENCE_FOR_EXPIRY",
    "MIN_QUALITY_FOR_EXPIRY",
    "MIN_VALIDITY_YEARS",
    "CnicReading",
    "combine_cnic_sides",
]
