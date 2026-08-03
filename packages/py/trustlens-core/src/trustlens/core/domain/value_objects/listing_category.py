"""The controlled vocabulary of listing categories.

Mirrors `LISTING_CATEGORIES` in `packages/constants`. Kept as a plain frozenset
rather than an enum so a category added on the frontend does not require a
migration before the backend will accept it - but unknown values are still
rejected, so the two cannot drift silently either.

Why a fixed list at all: the `LISTING_PRICE_REALISTIC` signal compares a
listing against the median price of its own category. With free-text
categories, sellers produced "Mobile Phones", "mobile-phones" and "mobiles" as
three separate buckets for one category, so a phone was never compared against
other phones and "too good to be true" could never fire.
"""

from __future__ import annotations

import re

from trustlens.core.domain.errors import ValidationError

LISTING_CATEGORIES: frozenset[str] = frozenset(
    {
        "mobiles",
        "electronics",
        "computers",
        "vehicles",
        "vehicle-parts",
        "property-sale",
        "property-rent",
        "home-appliances",
        "furniture",
        "fashion",
        "books-hobbies",
        "animals",
        "services",
        "other",
    }
)

_SEPARATORS = re.compile(r"[\s_]+")
_INVALID = re.compile(r"[^a-z0-9-]")
_REPEATED_DASH = re.compile(r"-{2,}")


def normalise_category(raw: str | None) -> str | None:
    """Fold a free-text category into its canonical slug.

    Handles the mechanical variants - case, spaces, underscores - so
    "Mobile Phones", "mobile_phones" and "MOBILE-PHONES" all reach the same
    bucket. It cannot fold synonyms ("mobiles" vs "cell phones"); that is
    exactly why the accepted set is fixed.
    """
    if raw is None:
        return None
    slug = _SEPARATORS.sub("-", raw.strip().lower())
    slug = _INVALID.sub("", slug)
    slug = _REPEATED_DASH.sub("-", slug).strip("-")
    return slug or None


def validate_category(raw: str | None) -> str | None:
    """Normalise and check against the vocabulary. None stays None."""
    slug = normalise_category(raw)
    if slug is None:
        return None
    if slug not in LISTING_CATEGORIES:
        raise ValidationError(
            "Choose one of the listed categories.",
            field="category",
        )
    return slug


__all__ = ["LISTING_CATEGORIES", "normalise_category", "validate_category"]
