"""Seller handle rules.

A handle is the seller's public identity: buyers reach the page at
`/seller/<handle>` and read a Trust Score there. That makes the handle itself
an attack surface. Someone who registers `daraz-official` and scores well has
borrowed a marketplace's reputation, and on a product whose entire promise is
"this seller is who they say they are", that is the one failure that discredits
the whole score.

Pure functions, no I/O: uniqueness needs the database and is checked by the
caller, but what a handle is *allowed* to say is decided here.
"""

from __future__ import annotations

import re
import unicodedata

#: Marketplaces and platforms operating in Pakistan, plus the global names a
#: local scammer is most likely to trade on. Impersonating any of these is the
#: specific vector the proposal calls out.
RESERVED_BRANDS = frozenset(
    {
        "olx",
        "daraz",
        "shopify",
        "alibaba",
        "aliexpress",
        "amazon",
        "ebay",
        "telemart",
        "goto",
        "priceoye",
        "homeshopping",
        "yayvo",
        "symbios",
        "mega",
        "carfirst",
        "pakwheels",
        "zameen",
        "foodpanda",
        "careem",
        "easypaisa",
        "jazzcash",
        "sadapay",
        "nayapay",
        "hbl",
        "meezan",
        "ubl",
        "nadra",
        "trustlens",
    }
)

#: Words that imply the account speaks for the platform rather than to it.
RESERVED_AUTHORITY = frozenset(
    {
        "admin",
        "administrator",
        "moderator",
        "support",
        "help",
        "helpdesk",
        "official",
        "verified",
        "staff",
        "team",
        "security",
        "billing",
        "payments",
        "refund",
        "refunds",
        "noreply",
        "no-reply",
        "root",
        "system",
        "trust",
        "trustlens-team",
    }
)

#: Route names. A handle that collides with one of these would shadow a real
#: page: `/seller/login` is not a seller.
RESERVED_ROUTES = frozenset(
    {
        "api",
        "app",
        "www",
        "login",
        "logout",
        "register",
        "signup",
        "signin",
        "dashboard",
        "settings",
        "account",
        "profile",
        "seller",
        "sellers",
        "listing",
        "listings",
        "check",
        "search",
        "about",
        "terms",
        "privacy",
        "contact",
        "docs",
        "static",
        "assets",
        "public",
        "new",
        "edit",
        "delete",
    }
)

RESERVED_HANDLES = RESERVED_BRANDS | RESERVED_AUTHORITY | RESERVED_ROUTES

#: Suffixes and prefixes that turn a brand into a claim of officialness.
#: `olx` is caught by the exact check; `olx-official` needs this one.
AUTHORITY_AFFIXES = (
    "official",
    "support",
    "help",
    "admin",
    "team",
    "verified",
    "service",
    "care",
    "hq",
)

MIN_HANDLE_LENGTH = 3
MAX_HANDLE_LENGTH = 40

_HANDLE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: Characters that look like ASCII but are not. Mapped before comparison so a
#: Greek-alpha "daraz" or a digit-substituted "0lx" cannot slip past a list
#: that only knows the plain spelling.
#:
#: Every non-ASCII key is written as a `\uXXXX` escape on purpose. These
#: glyphs are visually identical to their Latin counterparts *and to each
#: other*, so literals here are unreviewable: the first draft of this table
#: used Greek omicron (U+03BF) where it meant Cyrillic o (U+043E), leaving the
#: far likelier attack unmapped, and no amount of staring at the source would
#: have shown it. Escapes make the codepoint the thing under review.
_CONFUSABLES = str.maketrans(
    {
        # ASCII substitutions
        "0": "o",
        "1": "l",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "$": "s",
        "@": "a",
        "!": "i",
        "|": "l",
        # Greek
        "\u03b1": "a",  # GREEK SMALL LETTER ALPHA
        "\u03bf": "o",  # GREEK SMALL LETTER OMICRON
        "\u03c1": "p",  # GREEK SMALL LETTER RHO
        "\u03c5": "u",  # GREEK SMALL LETTER UPSILON
        # Cyrillic
        "\u0430": "a",  # CYRILLIC SMALL LETTER A
        "\u0432": "b",  # CYRILLIC SMALL LETTER VE
        "\u0435": "e",  # CYRILLIC SMALL LETTER IE
        "\u043a": "k",  # CYRILLIC SMALL LETTER KA
        "\u043c": "m",  # CYRILLIC SMALL LETTER EM
        "\u043d": "h",  # CYRILLIC SMALL LETTER EN
        "\u043e": "o",  # CYRILLIC SMALL LETTER O
        "\u0440": "p",  # CYRILLIC SMALL LETTER ER
        "\u0441": "c",  # CYRILLIC SMALL LETTER ES
        "\u0443": "y",  # CYRILLIC SMALL LETTER U
        "\u0445": "x",  # CYRILLIC SMALL LETTER HA
        "\u0455": "s",  # CYRILLIC SMALL LETTER DZE
        "\u0456": "i",  # CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I
        "\u0458": "j",  # CYRILLIC SMALL LETTER JE
    }
)


def slugify_handle(raw: str) -> str:
    """Turn arbitrary display text into the handle shape.

    Unicode is folded to ASCII first, so an accented or non-Latin display name
    still produces a URL-safe handle instead of an empty string.
    """
    decomposed = unicodedata.normalize("NFKD", raw)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    hyphenated = "".join(c if c.isalnum() else "-" for c in lowered)
    collapsed = re.sub(r"-{2,}", "-", hyphenated).strip("-")
    return collapsed[:MAX_HANDLE_LENGTH].strip("-")


def _canonical(handle: str) -> str:
    """Strip the noise an impersonator hides behind.

    `d-a-r-a-z`, `daraz00` and `d4raz` all canonicalise to `daraz`, so one
    blocklist entry covers the family rather than one spelling of it.

    Order matters: the confusable map runs *before* non-ASCII is discarded.
    Reversed, Cyrillic o (U+043E) would be stripped as noise rather than folded
    to Latin `o`, so a handle rendering identically to `olx` on screen would
    canonicalise to just `l` and sail past the blocklist.
    """
    folded = handle.lower().translate(_CONFUSABLES)
    normalised = unicodedata.normalize("NFKD", folded)
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z]", "", ascii_only)


def is_reserved(handle: str) -> bool:
    """Whether this handle impersonates a brand, the platform, or a route."""
    normalised = handle.lower().strip("-")
    if normalised in RESERVED_HANDLES:
        return True

    canonical = _canonical(normalised)
    if canonical in {_canonical(word) for word in RESERVED_HANDLES}:
        return True

    # `olx-official`, `official-daraz`, `daraz-support`: a reserved brand
    # wearing an authority word. Either order, and either side.
    parts = [part for part in normalised.split("-") if part]
    if len(parts) >= 2:
        canonical_parts = {_canonical(part) for part in parts}
        canonical_brands = {_canonical(brand) for brand in RESERVED_BRANDS}
        if canonical_parts & canonical_brands and any(
            _canonical(part) in {_canonical(a) for a in AUTHORITY_AFFIXES} for part in parts
        ):
            return True

    # A bare authority claim anywhere in the handle: `pay-support`, `admin-2`.
    authority = {_canonical(word) for word in RESERVED_AUTHORITY}
    return any(_canonical(part) in authority for part in parts)


def validate_handle(handle: str) -> list[str]:
    """Return every problem with a handle; empty means acceptable.

    A list rather than an exception so a form can show all the reasons at
    once, matching PasswordPolicy.validate.
    """
    problems: list[str] = []

    if len(handle) < MIN_HANDLE_LENGTH:
        problems.append(f"Use at least {MIN_HANDLE_LENGTH} characters.")
    if len(handle) > MAX_HANDLE_LENGTH:
        problems.append(f"Use at most {MAX_HANDLE_LENGTH} characters.")
    if not _HANDLE_RE.match(handle):
        problems.append("Use lowercase letters, numbers and single hyphens between words.")
    if is_reserved(handle):
        problems.append("This name is reserved. Choose something that is clearly your own.")

    return problems


__all__ = [
    "AUTHORITY_AFFIXES",
    "MAX_HANDLE_LENGTH",
    "MIN_HANDLE_LENGTH",
    "RESERVED_AUTHORITY",
    "RESERVED_BRANDS",
    "RESERVED_HANDLES",
    "RESERVED_ROUTES",
    "is_reserved",
    "slugify_handle",
    "validate_handle",
]
