"""Tests for the listing category vocabulary (P3-04).

The price signal compares a listing against the median of its own category, so
a category that does not fold consistently silently disables the signal. Real
data from the dev database had "Mobile Phones", "mobile-phones" and "mobiles"
as three separate buckets, which meant a phone was never compared against
other phones.
"""

from __future__ import annotations

import pytest

from trustlens.core.domain.errors import ValidationError
from trustlens.core.domain.value_objects import (
    LISTING_CATEGORIES,
    normalise_category,
    validate_category,
)


class TestNormalise:
    @pytest.mark.parametrize(
        "raw",
        ["mobiles", "Mobiles", "  MOBILES  ", "mobiles\n"],
    )
    def test_folds_case_and_whitespace(self, raw: str) -> None:
        assert normalise_category(raw) == "mobiles"

    @pytest.mark.parametrize(
        "raw",
        ["vehicle parts", "Vehicle Parts", "vehicle_parts", "vehicle-parts", "VEHICLE  PARTS"],
    )
    def test_folds_separators(self, raw: str) -> None:
        """The exact variants that fragmented the real corpus."""
        assert normalise_category(raw) == "vehicle-parts"

    def test_strips_punctuation(self) -> None:
        assert normalise_category("Mobiles!!") == "mobiles"

    def test_collapses_repeated_dashes(self) -> None:
        assert normalise_category("home---appliances") == "home-appliances"

    @pytest.mark.parametrize("raw", [None, "", "   ", "!!!"])
    def test_empty_becomes_none(self, raw: str | None) -> None:
        assert normalise_category(raw) is None


class TestValidate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Home Appliances", "home-appliances"),
            ("vehicle_parts", "vehicle-parts"),
            ("  Property For Rent  ", None),  # a synonym, not a variant - see below
        ],
    )
    def test_normalises_then_accepts(self, raw: str, expected: str | None) -> None:
        if expected is None:
            with pytest.raises(ValidationError):
                validate_category(raw)
        else:
            assert validate_category(raw) == expected

    def test_known_slug_passes_through(self) -> None:
        assert validate_category("property-rent") == "property-rent"

    def test_none_stays_none(self) -> None:
        """Category is optional; absent is not invalid."""
        assert validate_category(None) is None

    def test_unknown_category_is_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_category("crypto-investments")
        assert exc.value.field == "category"

    def test_synonyms_are_not_silently_accepted(self) -> None:
        """Normalisation cannot fold synonyms - which is why the set is fixed.

        "cell phones" is the same thing as "mobiles" to a human and a different
        bucket to a median, so it must be rejected rather than quietly stored.
        """
        with pytest.raises(ValidationError):
            validate_category("cell phones")

    def test_every_vocabulary_entry_is_already_canonical(self) -> None:
        """A entry that does not survive its own normalisation could never be
        stored, so the list would contain an unreachable option."""
        for slug in LISTING_CATEGORIES:
            assert normalise_category(slug) == slug
