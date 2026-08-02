"""Tests for CNIC structural validation and cross-checks (P1-04).

The CNIC numbers here are structurally valid but synthetic. Do not replace them
with real ones - test files end up in git history, and a CNIC is sensitive
personal data under Pakistan's data protection regime.
"""

from __future__ import annotations

from datetime import date

import pytest

from trustlens.ai.ocr.cnic_validation import (
    ExpiryStatus,
    Gender,
    expiry_status,
    gender_from_cnic,
    is_well_formed,
    normalise_cnic,
    parse_gender,
    province_of,
    validate,
)

TODAY = date(2026, 7, 31)

# Last digit 1 (odd) -> male; 2 (even) -> female.
MALE_CNIC = "35202-1234567-1"
FEMALE_CNIC = "35202-1234567-2"


class TestNormalise:
    @pytest.mark.parametrize(
        "raw",
        ["35202-1234567-1", "3520212345671", "35202 1234567 1", " 35202--1234567--1 "],
    )
    def test_accepts_any_separator(self, raw: str) -> None:
        assert normalise_cnic(raw) == "3520212345671"

    @pytest.mark.parametrize("raw", [None, "", "352021234567", "35202123456712", "abc"])
    def test_rejects_wrong_length(self, raw: str | None) -> None:
        assert normalise_cnic(raw) is None


class TestWellFormed:
    def test_accepts_valid(self) -> None:
        assert is_well_formed(MALE_CNIC)

    @pytest.mark.parametrize("first_digit", ["0", "8", "9"])
    def test_rejects_unallocated_province_code(self, first_digit: str) -> None:
        assert not is_well_formed(f"{first_digit}5202-1234567-1")

    @pytest.mark.parametrize("cnic", ["0000000000000", "1111111111111"])
    def test_rejects_repeated_digit_placeholders(self, cnic: str) -> None:
        """These pass a naive length check but appear in forgeries and test data."""
        assert not is_well_formed(cnic)


class TestProvince:
    def test_maps_first_digit(self) -> None:
        assert province_of(MALE_CNIC) == "Punjab"
        assert province_of("42101-1234567-1") == "Sindh"

    def test_none_when_unparseable(self) -> None:
        assert province_of("nope") is None


class TestGenderFromNumber:
    def test_odd_final_digit_is_male(self) -> None:
        assert gender_from_cnic(MALE_CNIC) is Gender.MALE

    def test_even_final_digit_is_female(self) -> None:
        assert gender_from_cnic(FEMALE_CNIC) is Gender.FEMALE

    def test_none_when_unparseable(self) -> None:
        assert gender_from_cnic("352021234567") is None


class TestParseGenderFromText:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Gender: M", Gender.MALE),
            ("gender f", Gender.FEMALE),
            ("Sex: Female", Gender.FEMALE),
            ("GENDER: MALE", Gender.MALE),
        ],
    )
    def test_reads_labelled_field(self, text: str, expected: Gender) -> None:
        assert parse_gender(text) is expected

    def test_falls_back_to_bare_token(self) -> None:
        assert parse_gender("Date of Birth 01.01.1990\nM\nPunjab") is Gender.MALE

    def test_label_wins_over_bare_token(self) -> None:
        """A stray letter must not override an explicitly labelled field."""
        assert parse_gender("F\nGender: M") is Gender.MALE

    def test_does_not_mistake_an_initial_for_gender(self) -> None:
        assert parse_gender("Name: Muhammad Ali") is None

    def test_none_for_empty(self) -> None:
        assert parse_gender(None) is None


class TestExpiry:
    def test_future_date_is_valid(self) -> None:
        assert expiry_status(date(2030, 1, 1), today=TODAY) is ExpiryStatus.VALID

    def test_past_date_is_expired(self) -> None:
        assert expiry_status(date(2020, 1, 1), today=TODAY) is ExpiryStatus.EXPIRED

    def test_today_still_counts_as_valid(self) -> None:
        assert expiry_status(TODAY, today=TODAY) is ExpiryStatus.VALID

    def test_lifetime_text_overrides_missing_date(self) -> None:
        assert expiry_status(None, today=TODAY, text="Expiry: Lifetime") is ExpiryStatus.LIFETIME

    def test_missing_date_is_unknown(self) -> None:
        assert expiry_status(None, today=TODAY) is ExpiryStatus.UNKNOWN


class TestValidate:
    def test_consistent_card_is_plausible(self) -> None:
        result = validate(
            cnic_number=MALE_CNIC,
            text="Name: Ahmad Khan\nGender: M",
            expiry=date(2030, 1, 1),
            today=TODAY,
        )
        assert result.is_plausible
        assert not result.needs_manual_review
        assert result.gender_consistent is True
        assert result.province == "Punjab"
        assert result.failures == ()

    def test_gender_mismatch_is_caught(self) -> None:
        """Number says female, card says male - mis-read or crude forgery."""
        result = validate(
            cnic_number=FEMALE_CNIC,
            text="Gender: M",
            expiry=date(2030, 1, 1),
            today=TODAY,
        )
        assert not result.is_plausible
        assert result.needs_manual_review
        assert result.gender_consistent is False
        assert "CNIC_GENDER_MISMATCH" in result.failures

    def test_expired_card_flagged_but_not_a_review_case(self) -> None:
        """Expiry is a fact the seller can fix; it is not an ambiguity."""
        result = validate(
            cnic_number=MALE_CNIC,
            text="Gender: M",
            expiry=date(2020, 1, 1),
            today=TODAY,
        )
        assert not result.is_plausible
        assert not result.needs_manual_review
        assert "CNIC_EXPIRED" in result.failures

    def test_missing_number_routes_to_review(self) -> None:
        result = validate(cnic_number=None, text="blurry", expiry=None, today=TODAY)
        assert result.needs_manual_review
        assert "CNIC_NUMBER_NOT_FOUND" in result.failures

    def test_unreadable_gender_does_not_fail_the_card(self) -> None:
        """Absent evidence is not contrary evidence - consistency stays unknown."""
        result = validate(
            cnic_number=MALE_CNIC,
            text="Name: Ahmad Khan",
            expiry=date(2030, 1, 1),
            today=TODAY,
        )
        assert result.gender_consistent is None
        assert result.is_plausible
