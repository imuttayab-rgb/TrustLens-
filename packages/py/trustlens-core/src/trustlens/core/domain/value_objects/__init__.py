"""Value objects.

Each one validates at construction, so an invalid value cannot exist anywhere
downstream. This is why the rest of the domain has almost no defensive checks:
if you hold a `PhoneE164`, it is already E.164.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from trustlens.core.domain.enums import RiskLevel
from trustlens.core.domain.errors import ValidationError
from trustlens.core.domain.value_objects.listing_category import (
    LISTING_CATEGORIES,
    normalise_category,
    validate_category,
)

# ── Score ────────────────────────────────────────────────────────────

#: Risk band boundaries (assumption A1 in docs/01). Kept here rather than in
#: config because they are part of the published product meaning of a score:
#: changing them changes what "LOW risk" tells a buyer.
HIGH_RISK_MAX = 39
MEDIUM_RISK_MAX = 69


@dataclass(frozen=True, slots=True)
class Score:
    """An integer trust score, 0-100 inclusive."""

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise ValidationError("score must be an integer", field="score")
        if not 0 <= self.value <= 100:
            raise ValidationError(
                f"score must be between 0 and 100, got {self.value}", field="score"
            )

    @classmethod
    def clamped(cls, value: float) -> Score:
        """Build from a raw computation, rounding and clamping into range."""
        return cls(max(0, min(100, round(value))))

    @property
    def risk_level(self) -> RiskLevel:
        if self.value <= HIGH_RISK_MAX:
            return RiskLevel.HIGH
        if self.value <= MEDIUM_RISK_MAX:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Confidence:
    """How much we trust the evidence behind a signal or a score, 0.0-1.0."""

    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValidationError(
                f"confidence must be between 0.0 and 1.0, got {self.value}", field="confidence"
            )

    @classmethod
    def certain(cls) -> Confidence:
        return cls(1.0)

    @classmethod
    def unknown(cls) -> Confidence:
        return cls(0.0)

    def __float__(self) -> float:
        return self.value


# ── Contact ──────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


@dataclass(frozen=True, slots=True)
class Email:
    """A normalised email address.

    Normalisation happens before validation and before any uniqueness check -
    otherwise `Test@x.com` and `test@x.com` become two accounts.
    """

    value: str

    def __post_init__(self) -> None:
        normalised = self.value.strip().lower()
        if not _EMAIL_RE.match(normalised):
            raise ValidationError(f"invalid email address: {self.value!r}", field="email")
        if len(normalised) > 254:
            raise ValidationError("email address too long", field="email")
        object.__setattr__(self, "value", normalised)

    @property
    def domain(self) -> str:
        return self.value.rsplit("@", 1)[1]

    @property
    def local_part(self) -> str:
        return self.value.rsplit("@", 1)[0]

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PhoneE164:
    """A phone number in E.164 form (`+` followed by 8-15 digits)."""

    value: str

    def __post_init__(self) -> None:
        compact = re.sub(r"[\s\-()]", "", self.value.strip())
        if not _E164_RE.match(compact):
            raise ValidationError(
                f"phone number must be in E.164 format, e.g. +923001234567 (got {self.value!r})",
                field="phone_number",
            )
        object.__setattr__(self, "value", compact)

    @property
    def country_calling_code(self) -> str:
        # Sufficient for the country-consistency signal; full parsing would
        # need a numbering-plan library, which the signal does not warrant.
        return self.value[1:3]

    def masked(self) -> str:
        """Safe for display and for logs."""
        return f"{self.value[:4]}{'*' * (len(self.value) - 6)}{self.value[-2:]}"

    def __str__(self) -> str:
        return self.value


# ── Identity ─────────────────────────────────────────────────────────

_CNIC_RE = re.compile(r"^\d{5}-?\d{7}-?\d$")


@dataclass(frozen=True, slots=True)
class CnicNumber:
    """A Pakistani CNIC number, stored digits-only (13 digits).

    Assumption A2: the proposal says "CNIC" without expansion. Format is
    5 digits (region) + 7 (serial) + 1 (gender parity digit).
    """

    value: str

    def __post_init__(self) -> None:
        raw = self.value.strip()
        if not _CNIC_RE.match(raw):
            raise ValidationError(
                "CNIC must be 13 digits, e.g. 35202-1234567-1", field="cnic_number"
            )
        digits = raw.replace("-", "")
        if digits == "0" * 13:
            raise ValidationError("CNIC number is not valid", field="cnic_number")
        object.__setattr__(self, "value", digits)

    @property
    def formatted(self) -> str:
        return f"{self.value[:5]}-{self.value[5:12]}-{self.value[12]}"

    def masked(self) -> str:
        """The ONLY form that may be returned by an API or written to a log."""
        return f"*****-*****{self.value[10:12]}-{self.value[12]}"

    def __str__(self) -> str:  # pragma: no cover - guard against accidental leaks
        # Deliberately masked: an f-string in a log line must not print a CNIC.
        return self.masked()


@dataclass(frozen=True, slots=True)
class DeviceFingerprint:
    """An opaque client-supplied device fingerprint.

    Treated as untrusted input: it is a *signal*, never an identity. A client
    can forge it, which is why device evidence is worth 10 of 100 points and
    is always corroborated by server-observed IP data.
    """

    value: str

    def __post_init__(self) -> None:
        v = self.value.strip()
        if not 16 <= len(v) <= 256:
            raise ValidationError(
                "device fingerprint has an implausible length", field="fingerprint"
            )
        if not re.fullmatch(r"[A-Za-z0-9+/=_-]+", v):
            raise ValidationError(
                "device fingerprint contains invalid characters", field="fingerprint"
            )
        object.__setattr__(self, "value", v)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Money:
    """An amount with a currency. Never a float."""

    amount: float
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValidationError("amount cannot be negative", field="price")
        code = self.currency.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValidationError("currency must be a 3-letter ISO 4217 code", field="currency")
        object.__setattr__(self, "currency", code)

    def __str__(self) -> str:
        return f"{self.amount:,.2f} {self.currency}"


@dataclass(frozen=True, slots=True)
class DateOfBirth:
    value: date

    def __post_init__(self) -> None:
        if self.value.year < 1900:
            raise ValidationError("date of birth is implausible", field="date_of_birth")

    def age_on(self, today: date) -> int:
        return (
            today.year
            - self.value.year
            - ((today.month, today.day) < (self.value.month, self.value.day))
        )


__all__ = [
    "HIGH_RISK_MAX",
    "LISTING_CATEGORIES",
    "MEDIUM_RISK_MAX",
    "CnicNumber",
    "Confidence",
    "DateOfBirth",
    "DeviceFingerprint",
    "Email",
    "Money",
    "PhoneE164",
    "Score",
    "normalise_category",
    "validate_category",
]
