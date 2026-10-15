"""Small deterministic profile rules; no fuzzy identity auto-approval."""

from __future__ import annotations

import math
import unicodedata


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return " ".join(value.casefold().split())


def clean_name(value: str) -> str:
    value = " ".join(unicodedata.normalize("NFKC", value).split())
    if not 2 <= len(value) <= 150 or any(unicodedata.category(c).startswith("C") for c in value):
        raise ValueError("Enter your full name as printed on your ID (2–150 characters).")
    if not any(c.isalpha() for c in value) or not all(
        c.isalpha() or unicodedata.category(c).startswith("M") or c in " .'-’" for c in value
    ):
        raise ValueError("Use the name printed on your ID, without numbers or symbols.")
    return value


def public_name(value: str) -> str:
    """Only first/last name is public; never guess a transliteration."""
    parts = clean_name(value).split()
    return " ".join((parts[0], parts[-1])) if len(parts) > 1 else parts[0]


def can_confirm_name(
    entered: str, extracted: str | None, *, engine: str | None, confidence: float | None
) -> bool:
    return bool(
        extracted
        and engine
        and engine.lower() in {"rapidocr", "easyocr"}
        and confidence is not None
        and math.isfinite(confidence)
        and 0.85 <= confidence <= 1
        and normalize_name(entered) == normalize_name(extracted)
    )


def photo_result_approved(result: object) -> bool:
    raw = getattr(result, "raw", {}) or {}
    return bool(
        getattr(result, "engine", "").lower() in {"insightface", "deepface"}
        and raw.get("profile_face_count") == 1
        and raw.get("reference_face_count") == 1
        and getattr(result, "face_detected_in_document", False)
        and getattr(result, "face_detected_in_selfie", False)
        and 0.80 <= getattr(result, "threshold", 2) <= 1
        and getattr(result, "threshold", 2) <= getattr(result, "similarity", -1) <= 1
    )
