"""Maps raw OCR tokens onto CNIC fields.

EasyOCR returns tokens in reading order, but CNIC back pages are two-column,
so anything positional must re-sort by bounding-box x-position first. This
parser works on the joined text and labelled patterns instead, which is more
robust to that layout than positional heuristics.
"""

from __future__ import annotations

import re
from datetime import date, datetime

CNIC_RE = re.compile(r"\b(\d{5})\s*-?\s*(\d{7})\s*-?\s*(\d)\b")
DATE_RE = re.compile(r"\b(\d{2})[./-](\d{2})[./-](\d{4})\b")
NAME_LABEL_RE = re.compile(r"\bname\b[:\s]*([A-Za-z][A-Za-z\s.'-]{2,60})", re.IGNORECASE)
FATHER_LABEL_RE = re.compile(
    r"\b(?:father|husband)(?:\s+name)?\b[:\s]*([A-Za-z][A-Za-z\s.'-]{2,60})", re.IGNORECASE
)


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


def parse_name(text: str) -> str | None:
    match = NAME_LABEL_RE.search(text)
    return " ".join(match.group(1).split()) if match else None


def parse_father_name(text: str) -> str | None:
    match = FATHER_LABEL_RE.search(text)
    return " ".join(match.group(1).split()) if match else None


def split_birth_and_expiry(dates: list[date]) -> tuple[date | None, date | None]:
    """A CNIC carries date of birth, issue date and expiry.

    Ordering is reliable where the labels are not: birth is always the
    earliest, expiry always the latest.
    """
    if not dates:
        return None, None
    if len(dates) == 1:
        return dates[0], None
    return dates[0], dates[-1]


__all__ = [
    "parse_cnic_number",
    "parse_dates",
    "parse_father_name",
    "parse_name",
    "split_birth_and_expiry",
]
