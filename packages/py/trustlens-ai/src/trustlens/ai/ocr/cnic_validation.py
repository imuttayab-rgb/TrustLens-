"""Structural validation and cross-checks for a parsed CNIC.

None of this proves a CNIC is *real* - NADRA exposes no public verification
API, so a genuine-looking forgery cannot be distinguished from a genuine card
by software alone. What these checks establish is *plausibility*: that the
number is structurally well-formed, that the fields agree with each other, and
that the card has not expired.

The cross-checks matter more than they look. A CNIC number encodes the holder's
gender in its final digit, so a card whose printed gender disagrees with its
number is either mis-read by OCR or crudely forged. Catching that costs one
comparison and no external call.

Everything here is a pure function of its inputs - `today` is passed in rather
than read from the clock - so the results are reproducible and testable, and a
verification decision can be replayed during an appeal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

#: 5 digits (locality) + 7 digits (family/serial) + 1 check-ish digit (gender).
CNIC_DIGITS = 13

#: First digit of the locality code. NADRA allocates 1-7 by region; anything
#: else means the number was mis-read or invented.
PROVINCE_BY_FIRST_DIGIT: dict[str, str] = {
    "1": "Khyber Pakhtunkhwa",
    "2": "FATA",
    "3": "Punjab",
    "4": "Sindh",
    "5": "Balochistan",
    "6": "Islamabad (ICT)",
    "7": "Gilgit-Baltistan / AJK",
}

_NON_DIGITS = re.compile(r"\D")
_GENDER_LABEL_RE = re.compile(
    r"\b(?:gender|sex)\b[:\s]*(m|f|male|female)\b",
    re.IGNORECASE,
)
#: Some CNICs print an unlabelled bare M / F near the date fields.
_BARE_GENDER_RE = re.compile(r"(?<![A-Za-z])([MF])(?![A-Za-z])")


class Gender(StrEnum):
    MALE = "M"
    FEMALE = "F"


class ExpiryStatus(StrEnum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    LIFETIME = "LIFETIME"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class CnicValidation:
    """The full plausibility verdict for one parsed CNIC."""

    cnic_number: str | None
    format_valid: bool
    province: str | None
    gender_from_number: Gender | None
    gender_from_text: Gender | None
    gender_consistent: bool | None
    expiry_status: ExpiryStatus
    failures: tuple[str, ...] = ()

    @property
    def is_plausible(self) -> bool:
        """True when nothing contradicts the document being genuine.

        Deliberately *not* named `is_valid`: passing means we found no
        inconsistency, not that the card was checked against any register.
        """
        return self.format_valid and self.gender_consistent is not False and not self.failures

    @property
    def needs_manual_review(self) -> bool:
        """Ambiguity routes to a human rather than to a FAIL.

        A seller cannot appeal against a blurry photograph, so an unreadable
        or self-inconsistent card becomes a review case, not a rejection.
        """
        return not self.format_valid or self.gender_consistent is False


def normalise_cnic(raw: str | None) -> str | None:
    """Strip formatting and return 13 bare digits, or None if that is not what it is."""
    if not raw:
        return None
    digits = _NON_DIGITS.sub("", raw)
    return digits if len(digits) == CNIC_DIGITS else None


def is_well_formed(cnic: str | None) -> bool:
    """Structural check on a normalised CNIC.

    Rejects repeated-digit placeholders (0000000000000, 1111111111111) because
    they pass a naive length check and appear in test data and lazy forgeries
    alike.
    """
    normalised = normalise_cnic(cnic)
    if normalised is None:
        return False
    if normalised[0] not in PROVINCE_BY_FIRST_DIGIT:
        return False
    return len(set(normalised)) > 1


def province_of(cnic: str | None) -> str | None:
    normalised = normalise_cnic(cnic)
    if normalised is None:
        return None
    return PROVINCE_BY_FIRST_DIGIT.get(normalised[0])


def gender_from_cnic(cnic: str | None) -> Gender | None:
    """The final digit encodes gender: odd is male, even is female."""
    normalised = normalise_cnic(cnic)
    if normalised is None:
        return None
    return Gender.MALE if int(normalised[-1]) % 2 else Gender.FEMALE


def parse_gender(text: str | None) -> Gender | None:
    """Recover the printed gender from OCR text.

    Prefers an explicitly labelled field; falls back to a bare M/F token only
    when no label was found, since a bare letter is easy to confuse with an
    initial in a name.
    """
    if not text:
        return None
    if match := _GENDER_LABEL_RE.search(text):
        return Gender.MALE if match.group(1).upper().startswith("M") else Gender.FEMALE
    if match := _BARE_GENDER_RE.search(text):
        return Gender(match.group(1).upper())
    return None


def expiry_status(expiry: date | None, *, today: date, text: str | None = None) -> ExpiryStatus:
    """Classify the card's expiry.

    Lifetime CNICs carry no usable expiry date, so an absent date is only
    `UNKNOWN` when the document does not say otherwise.
    """
    if text and re.search(r"\blife\s*time\b", text, re.IGNORECASE):
        return ExpiryStatus.LIFETIME
    if expiry is None:
        return ExpiryStatus.UNKNOWN
    return ExpiryStatus.VALID if expiry >= today else ExpiryStatus.EXPIRED


def validate(
    *,
    cnic_number: str | None,
    text: str | None,
    expiry: date | None,
    today: date,
) -> CnicValidation:
    """Run every structural check and cross-check over one parsed CNIC."""
    normalised = normalise_cnic(cnic_number)
    format_valid = is_well_formed(normalised)

    from_number = gender_from_cnic(normalised) if format_valid else None
    from_text = parse_gender(text)
    consistent: bool | None = None
    if from_number is not None and from_text is not None:
        consistent = from_number is from_text

    status = expiry_status(expiry, today=today, text=text)

    failures: list[str] = []
    if normalised is None:
        failures.append("CNIC_NUMBER_NOT_FOUND")
    elif not format_valid:
        failures.append("CNIC_FORMAT_INVALID")
    if consistent is False:
        failures.append("CNIC_GENDER_MISMATCH")
    if status is ExpiryStatus.EXPIRED:
        failures.append("CNIC_EXPIRED")

    return CnicValidation(
        cnic_number=normalised,
        format_valid=format_valid,
        province=province_of(normalised),
        gender_from_number=from_number,
        gender_from_text=from_text,
        gender_consistent=consistent,
        expiry_status=status,
        failures=tuple(failures),
    )


__all__ = [
    "CNIC_DIGITS",
    "PROVINCE_BY_FIRST_DIGIT",
    "CnicValidation",
    "ExpiryStatus",
    "Gender",
    "expiry_status",
    "gender_from_cnic",
    "is_well_formed",
    "normalise_cnic",
    "parse_gender",
    "province_of",
    "validate",
]
