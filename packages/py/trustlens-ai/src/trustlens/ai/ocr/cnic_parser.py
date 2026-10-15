"""Maps raw OCR tokens onto CNIC fields.

EasyOCR returns tokens in reading order, but CNIC back pages are two-column,
so anything positional must re-sort by bounding-box x-position first. This
parser works on the joined text and labelled patterns instead, which is more
robust to that layout than positional heuristics.

Safety rule for dates (real-OCR pilot): an expiry date is only reported when
the card yields at least three distinct dates (birth, issue, expiry). With two
dates the later one is usually the *issue* date - measured on a synthetic card
whose expiry line was removed - and reporting it as expiry would wrongly
reject a valid card as expired. Ambiguity therefore becomes "expiry unknown",
which the identity worker routes to a human reviewer.
"""

from __future__ import annotations

import re
from datetime import date, datetime

CNIC_RE = re.compile(r"\b(\d{5})\s*-?\s*(\d{7})\s*-?\s*(\d)\b")
DATE_RE = re.compile(r"\b(\d{2})[./-](\d{2})[./-](\d{4})\b")

#: A CNIC carries date of birth, date of issue and date of expiry. Fewer
#: distinct dates than this means the expiry cannot be told apart safely.
MIN_DATES_FOR_EXPIRY = 3

# Labels are matched per line. OCR often merges words ("FatherName"), so the
# space between the two label words is optional.
_NAME_LABEL_RE = re.compile(r"^\s*name\b\s*[:\-]?\s*(.*)$", re.IGNORECASE)
_FATHER_LABEL_RE = re.compile(r"^\s*(?:father|husband)\s*(?:name)?\s*[:\-]?\s*(.*)$", re.IGNORECASE)
# Words that belong to other printed labels; a "value" containing them is a
# mis-read label, not a person's name. Whole words only, so a real name that
# merely contains "card" or "date" (Ricardo, Sadaten) is never discarded.
_LABEL_WORDS_RE = re.compile(
    r"\b(?:name|father|husband|gender|country|identity|number|date|birth|issue|expiry|"
    r"pakistan|national|card|signature|holder)\b",
    re.IGNORECASE,
)
_PERSON_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,58}[A-Za-z.]$")


def parse_cnic_number(text: str) -> str | None:
    match = CNIC_RE.search(text)
    return "".join(match.groups()) if match else None


def parse_dates(text: str) -> list[date]:
    out: list[date] = []
    for day, month, year in DATE_RE.findall(text):
        try:
            out.append(datetime.strptime(f"{day}/{month}/{year}", "%d/%m/%Y").date())
        except ValueError:
            continue
    return sorted(out)


def _clean_person_name(candidate: str) -> str | None:
    """Return a normalised name, or None when the text is not a plausible name."""
    value = " ".join(candidate.split())
    if not value or _LABEL_WORDS_RE.search(value) or not _PERSON_NAME_RE.match(value):
        return None
    return value


def _labelled_value(lines: list[str], label: re.Pattern[str]) -> str | None:
    """Value printed after a label: on the same line, or else on the next line.

    Matching line by line stops a name from swallowing the following labels
    ("Name Ali Father Name ..."), which the earlier whole-text regex did.
    """
    for index, line in enumerate(lines):
        match = label.match(line)
        if match is None:
            continue
        same_line = _clean_person_name(match.group(1))
        if same_line:
            return same_line
        for following in lines[index + 1 : index + 3]:
            if following:
                return _clean_person_name(following)
    return None


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines()]


def parse_name(text: str) -> str | None:
    # A "Father Name" line must never be read as the holder's "Name" label.
    holder_lines = [line for line in _lines(text) if not _FATHER_LABEL_RE.match(line)]
    return _labelled_value(holder_lines, _NAME_LABEL_RE)


def parse_father_name(text: str) -> str | None:
    return _labelled_value(_lines(text), _FATHER_LABEL_RE)


def split_birth_and_expiry(dates: list[date]) -> tuple[date | None, date | None]:
    """Return (date of birth, expiry) from the dates printed on a CNIC.

    Birth is the earliest date. Expiry is the latest date, but ONLY when at
    least three distinct dates were read; otherwise expiry is None (unknown),
    because the later of two dates is normally the issue date.
    """
    distinct = sorted(set(dates))
    if not distinct:
        return None, None
    if len(distinct) < MIN_DATES_FOR_EXPIRY:
        return distinct[0], None
    return distinct[0], distinct[-1]


__all__ = [
    "MIN_DATES_FOR_EXPIRY",
    "parse_cnic_number",
    "parse_dates",
    "parse_father_name",
    "parse_name",
    "split_birth_and_expiry",
]
