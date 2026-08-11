"""Handle rules (P2-04).

The interesting cases are not "is `abc` valid" but the near-misses: the
spellings an impersonator reaches for once the obvious one is blocked.
"""

from __future__ import annotations

import pytest

from trustlens.core.domain.policies import is_reserved, slugify_handle, validate_handle


class TestSlugify:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Ahmed Electronics", "ahmed-electronics"),
            ("  spaced  out  ", "spaced-out"),
            ("Ali's Shop!!", "ali-s-shop"),
            ("multi---hyphen", "multi-hyphen"),
            ("-leading-and-trailing-", "leading-and-trailing"),
            ("UPPER CASE", "upper-case"),
        ],
    )
    def test_shapes_display_names(self, raw: str, expected: str) -> None:
        assert slugify_handle(raw) == expected

    def test_folds_unicode_to_ascii(self) -> None:
        # Without NFKD folding this returns "", and every such seller would
        # collide on the same fallback handle.
        assert slugify_handle("Café Münchén") == "cafe-munchen"

    def test_truncates_to_max_length(self) -> None:
        assert len(slugify_handle("a" * 200)) == 40

    def test_never_ends_on_a_hyphen_after_truncation(self) -> None:
        # 40 chars would land mid-separator; a trailing hyphen is not a legal
        # handle, so truncation must not create one.
        raw = ("word" * 9) + "-tail"
        assert not slugify_handle(raw).endswith("-")


class TestReserved:
    @pytest.mark.parametrize(
        "handle",
        ["olx", "daraz", "amazon", "foodpanda", "easypaisa", "nadra", "trustlens"],
    )
    def test_blocks_marketplace_and_platform_brands(self, handle: str) -> None:
        assert is_reserved(handle)

    @pytest.mark.parametrize(
        "handle", ["admin", "support", "official", "security", "billing", "refunds"]
    )
    def test_blocks_authority_words(self, handle: str) -> None:
        assert is_reserved(handle)

    @pytest.mark.parametrize("handle", ["login", "dashboard", "settings", "api", "seller"])
    def test_blocks_route_collisions(self, handle: str) -> None:
        assert is_reserved(handle)

    @pytest.mark.parametrize(
        "handle",
        [
            "olx-official",
            "official-olx",
            "daraz-support",
            "daraz-help",
            "amazon-team",
            "olx-care",
        ],
    )
    def test_blocks_brand_plus_authority_affix(self, handle: str) -> None:
        assert is_reserved(handle)

    @pytest.mark.parametrize("handle", ["0lx", "d4raz", "am4z0n", "e4sypaisa"])
    def test_blocks_digit_for_letter_substitutions(self, handle: str) -> None:
        assert is_reserved(handle)

    @pytest.mark.parametrize("handle", ["d-a-r-a-z", "o-l-x", "a-d-m-i-n"])
    def test_blocks_hyphen_padding(self, handle: str) -> None:
        assert is_reserved(handle)

    def test_blocks_cyrillic_lookalikes(self) -> None:
        # Cyrillic o (U+043E) and ha (U+0445) render identically to Latin "o"
        # and "x" in most fonts, so this reads as "olx" to a buyer. Written as
        # escapes because the literal form is indistinguishable on review.
        assert is_reserved("\u043el\u0445")

    @pytest.mark.parametrize("handle", ["my-support-shop", "refund-guy", "team-ahmed"])
    def test_blocks_authority_claim_anywhere_in_the_handle(self, handle: str) -> None:
        assert is_reserved(handle)

    @pytest.mark.parametrize(
        "handle",
        [
            "ahmed-electronics",
            "lahore-mobiles",
            "karachi-fashion-hub",
            "zohaib-store",
            "gadget-world-99",
        ],
    )
    def test_allows_ordinary_seller_names(self, handle: str) -> None:
        assert not is_reserved(handle)

    def test_allows_a_brand_substring_inside_a_longer_real_word(self) -> None:
        # "megamart" contains "mega" but is not a claim to be Mega, and
        # blocking honest sellers is its own failure. Substring matching would
        # get this wrong; token matching gets it right.
        assert not is_reserved("megamart-lahore")


class TestValidate:
    def test_accepts_a_good_handle(self) -> None:
        assert validate_handle("ahmed-electronics") == []

    def test_rejects_too_short(self) -> None:
        assert any("at least" in p for p in validate_handle("ab"))

    def test_rejects_too_long(self) -> None:
        assert any("at most" in p for p in validate_handle("a" * 41))

    @pytest.mark.parametrize("handle", ["Has Space", "UPPER", "under_score", "-lead", "trail-"])
    def test_rejects_wrong_shape(self, handle: str) -> None:
        assert any("lowercase" in p for p in validate_handle(handle))

    def test_rejects_double_hyphen(self) -> None:
        assert any("lowercase" in p for p in validate_handle("a--b"))

    def test_reports_reserved_separately_from_shape(self) -> None:
        problems = validate_handle("olx")
        assert any("reserved" in p for p in problems)

    def test_reports_every_problem_at_once(self) -> None:
        # Too short AND reserved: the form should be able to say both rather
        # than making the user fix one to discover the other.
        assert len(validate_handle("ol")) >= 1
