"""Category-aware search vocabulary, not stock, specifications, or a complete catalogue.

Live eligible listing titles supplement this vocabulary. Exact product specs
are researched on demand and always require seller confirmation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

from .search_data import SEARCH_TERMS

FIELDS: dict[str, list[str]] = {
    "mobiles": [
        "Exact model / variant",
        "Storage",
        "RAM",
        "Battery health (if measured)",
        "PTA status (seller claim)",
        "Repairs / faults",
        "Included accessories",
    ],
    "electronics": [
        "Exact model / edition",
        "Capacity / size",
        "Included accessories",
        "Repairs / faults",
        "Warranty (seller claim)",
    ],
    "computers": [
        "Exact model",
        "Processor",
        "RAM",
        "Storage",
        "Graphics",
        "Battery condition",
        "Repairs / faults",
    ],
    "vehicles": [
        "Make / model / variant",
        "Year",
        "Mileage",
        "Transmission",
        "Registration city",
        "Accidents / repairs",
        "Documents (seller claim)",
    ],
    "vehicle-parts": [
        "Part number",
        "Compatible models",
        "Brand",
        "Condition / faults",
        "Quantity",
    ],
    "property-sale": [
        "Property type",
        "Area and unit",
        "Bedrooms",
        "Bathrooms",
        "Public locality",
        "Documentation (seller claim)",
        "Possession status",
    ],
    "property-rent": [
        "Property type",
        "Area and unit",
        "Bedrooms",
        "Furnished",
        "Monthly rent",
        "Deposit",
        "Public locality",
    ],
    "home-appliances": [
        "Exact model",
        "Capacity",
        "Dimensions",
        "Power / energy rating",
        "Repairs / faults",
        "Warranty (seller claim)",
    ],
    "furniture": ["Material", "Dimensions", "Colour", "Condition / faults", "Included pieces"],
    "fashion": ["Brand", "Size", "Material", "Colour", "Condition / faults"],
    "books-hobbies": ["Title / model", "Edition", "Language", "Condition", "Included items"],
    "animals": ["Species / breed", "Age", "Health records (seller claim)", "Included items"],
    "services": [
        "Service scope",
        "Service area",
        "Experience",
        "Availability",
        "What the price includes",
    ],
    "other": ["Brand / model", "Size / capacity", "Condition / faults", "Included items"],
}

PRIVATE_KEYS = re.compile(
    r"cnic|passport|selfie|address|phone|email|password|token|secret|latitude|longitude|contact|identity.?document",
    re.I,
)


def public_text(value: object, size: int = 1000) -> str:
    text = str(value or "")[:size]
    text = re.sub(r"\b\d{5}[- ]?\d{7}[- ]?\d\b", "[identity number removed]", text)
    text = re.sub(r"(?<!\w)(?:\+?92[- ]?|0)3\d{2}[- ]?\d{7}\b", "[phone removed]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email removed]", text)
    return text


def safe_facts(facts: dict[str, str]) -> dict[str, str]:
    return {
        public_text(k, 40): public_text(v, 160)
        for k, v in list(facts.items())[:24]
        if not PRIVATE_KEYS.search(k)
    }


def safe_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 2000:
        return None
    try:
        p = urlsplit(value)
        if p.scheme == "https" and p.hostname and not p.username and not p.password:
            return value
    except ValueError:
        pass
    return None


def normalize_search(value: str) -> str:
    value = value.casefold().replace("+", " plus ")
    for pattern, replacement in (
        (r"\bi\s+phone(?=\b|\d)", "iphone"),
        (r"\bmac\s+book\b", "macbook"),
        (r"\bchrome\s+book\b", "chromebook"),
        (r"\btechno\b", "tecno"),
        (r"\bhewlett[ -]+packard\b", "hp"),
        (r"\bplay\s*station\b", "playstation"),
        (r"\bps\s*([345])\b", r"playstation \1"),
    ):
        value = re.sub(pattern, replacement, value)
    value = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", value)
    words = re.sub(r"[^\w ]", " ", value).split()
    singular = {
        "laptops": "laptop",
        "phones": "phone",
        "mobiles": "mobile",
        "cars": "car",
        "bikes": "bike",
        "computers": "computer",
        "shoes": "shoe",
        "tablets": "tablet",
        "machines": "machine",
        "books": "book",
        "services": "service",
        "parts": "part",
        "accessories": "accessory",
        "chromebooks": "chromebook",
        "macbooks": "macbook",
        "refrigerators": "refrigerator",
    }
    return " ".join(singular.get(w, w) for w in words)


@dataclass(frozen=True)
class SearchTerm:
    text: str
    query: str
    category: str
    related: str
    depth: int


_TERMS = tuple(SearchTerm(*row) for row in SEARCH_TERMS)
_INDEX = tuple(
    (
        term,
        normalize_search(term.text).split(),
        normalize_search(term.text + " " + term.related).split(),
    )
    for term in _TERMS
)
_DRILL = frozenset(
    normalize_search(q)
    for q in (
        "iphone",
        "apple iphone",
        "samsung",
        "samsung galaxy",
        "oppo",
        "tecno",
        "infinix",
        "vivo",
        "redmi",
        "xiaomi",
        "poco",
        "pixel",
        "google pixel",
        "realme",
        "oneplus",
        "nokia",
        "hp",
        "dell",
        "lenovo",
        "macbook",
        "asus",
        "acer",
        "chromebook",
        "honda",
        "toyota",
        "suzuki",
        "yamaha",
        "kia",
        "hyundai",
        "daihatsu",
        "changan",
        "ps5",
        "xbox",
        "nintendo",
    )
)


def _matches(words: list[str], haystack: list[str]) -> bool:
    # Prefix only on the last typed word; model numbers such as 13 must not match 130.
    return all(
        any(
            word == candidate
            or (i == len(words) - 1 and not word.isdigit() and candidate.startswith(word))
            for candidate in haystack
        )
        for i, word in enumerate(words)
    )


@lru_cache(maxsize=512)
def search_terms(query: str, category: str | None) -> tuple[SearchTerm, ...]:
    normalized = normalize_search(query)
    words = normalized.split()
    scored = []
    for order, (term, title, searchable) in enumerate(_INDEX):
        if category and term.category != category:
            continue
        if not words:
            if term.depth != (1 if category else 0):
                continue
            scored.append(((0, 0, order), term))
            continue
        if not _matches(words, searchable):
            continue
        direct = _matches(words, title)
        if any(word.isdigit() for word in words) and not direct:
            continue
        exact = normalized == " ".join(title)
        # A brand request drills into models; generic requests show families first.
        if normalized in _DRILL:
            score = (
                0 if direct and term.depth == 2 else 1 if direct else 2,
                0 if exact else 1,
                order,
            )
        else:
            score = (0 if exact else 1 if direct else 2, term.depth, order)
        scored.append((score, term))
    return tuple(term for _, term in sorted(scored, key=lambda item: item[0]))


def vocabulary(q: str, category: str | None) -> list[tuple[str, str]]:
    """Compatibility helper for callers needing the first ten labels only."""
    return [(term.text, term.category) for term in search_terms(q, category)[:10]]


_BUDGET = re.compile(
    r"(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>hazar|hazaar|thousand|k\b|lakh|lac|lacs|lakhs|crore|million|ہزار|لاکھ|کروڑ)?",
    re.I,
)


def explicit_budget(message: str) -> float | None:
    """Recognise an explicit monetary phrase, never a bare model number/year."""
    message = message.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    for match in _BUDGET.finditer(message):
        prefix = message[max(0, match.start() - 25) : match.start()].lower()
        suffix = message[match.end() : match.end() + 22].lower()
        unit = (match.group("unit") or "").lower()
        monetary = (
            bool(unit)
            or bool(
                re.search(
                    r"(?:budget|under|below|upto|up to|pkr|rs\.?|rupees|bajet|بجٹ)"
                    r"\s*(?:is|of|hai|h|:)?\s*$",
                    prefix,
                )
            )
            or bool(re.match(r"\s*(?:pkr|rs\b|rupees|rupay|روپے)", suffix))
        )
        if not monetary:
            continue
        value = float(match.group("num").replace(",", ""))
        factor = 1
        if unit in {"hazar", "hazaar", "thousand", "k", "ہزار"}:
            factor = 1000
        if unit in {"lakh", "lac", "lacs", "lakhs", "لاکھ"}:
            factor = 100000
        if unit in {"crore", "کروڑ"}:
            factor = 10000000
        if unit == "million":
            factor = 1000000
        if 0 <= value * factor <= 1_000_000_000:
            return value * factor
    return None
