"""Business rules as pure functions.

Nothing here does I/O, reads a clock directly, or knows what a database is.
That is deliberate: these are the rules the FYP will be examined on, and they
need to be readable and exhaustively testable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from trustlens.core.domain.entities.user import User
from trustlens.core.domain.enums import AppealStatus, RiskLevel
from trustlens.core.domain.errors import AppealLimitReached, AppealNotAllowed
from trustlens.core.domain.policies.scoring import (
    DEFAULT_MIN_EVIDENCE_WEIGHT,
    ScoreComputation,
    ScoringPolicy,
    rank_improvements,
)
from trustlens.core.domain.value_objects import HIGH_RISK_MAX, MEDIUM_RISK_MAX, Score

# ── Risk bands ───────────────────────────────────────────────────────


def band_for(score: int) -> RiskLevel:
    """Score -> risk band (assumption A1).

    Boundaries are inclusive on the upper edge: 39 is HIGH, 40 is MEDIUM,
    69 is MEDIUM, 70 is LOW. Off-by-one here would silently reclassify
    sellers, so it is covered by explicit boundary tests.
    """
    if score <= HIGH_RISK_MAX:
        return RiskLevel.HIGH
    if score <= MEDIUM_RISK_MAX:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def band_label(level: RiskLevel) -> str:
    return {
        RiskLevel.LOW: "Low risk",
        RiskLevel.MEDIUM: "Medium risk",
        RiskLevel.HIGH: "High risk",
        RiskLevel.UNKNOWN: "Not enough information",
    }[level]


# ── Score freshness ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    """When does a score need recomputing? (assumption A14)"""

    validity_days: int = 30

    def valid_until(self, computed_at: datetime) -> datetime:
        return computed_at + timedelta(days=self.validity_days)

    def is_stale(self, *, computed_at: datetime, now: datetime) -> bool:
        return now >= self.valid_until(computed_at)


# ── Device linkage ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DeviceLinkagePolicy:
    """How many accounts on one device is suspicious?

    Two accounts on a shared family device is ordinary; five is the pattern
    the proposal names as "multiple accounts created from one device". The
    middle ground degrades gradually rather than falling off a cliff, because
    a hard threshold punishes the household on the wrong side of it.
    """

    safe_max: int = 2
    suspicious_at: int = 5

    def ratio_for(self, linked_accounts: int) -> float:
        if linked_accounts <= self.safe_max:
            return 1.0
        if linked_accounts >= self.suspicious_at:
            return 0.0
        span = self.suspicious_at - self.safe_max
        return round(1.0 - (linked_accounts - self.safe_max) / span, 3)


# ── Account age ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AccountAgePolicy:
    """Graded credit for account age. Nothing a seller can rush."""

    full_credit_days: int = 180
    partial_bands: tuple[tuple[int, float], ...] = ((90, 0.66), (30, 0.33))

    def ratio_for(self, age_days: int) -> float:
        if age_days >= self.full_credit_days:
            return 1.0
        for threshold, ratio in self.partial_bands:
            if age_days >= threshold:
                return ratio
        return 0.0


# ── Appeals ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AppealPolicy:
    """Who may appeal, how often, and against what."""

    max_open: int = 1
    max_per_window: int = 3
    window_days: int = 30

    def assert_can_submit(
        self,
        *,
        open_appeals: int,
        appeals_in_window: int,
        score_is_current: bool,
    ) -> None:
        if not score_is_current:
            raise AppealNotAllowed(
                "Only the current trust score can be appealed. "
                "Your score has been recomputed since this one."
            )
        if open_appeals >= self.max_open:
            raise AppealNotAllowed(
                "You already have an open appeal. Please wait for it to be resolved."
            )
        if appeals_in_window >= self.max_per_window:
            raise AppealLimitReached(
                f"You can submit at most {self.max_per_window} appeals every "
                f"{self.window_days} days.",
                retry_after=self.window_days * 86400,
            )

    @staticmethod
    def assert_can_resolve(status: AppealStatus) -> None:
        if not status.is_open:
            raise AppealNotAllowed("This appeal has already been resolved.")


# ── Password ─────────────────────────────────────────────────────────

#: Deliberately short: this is a tripwire for the worst choices, not a
#: replacement for a breach corpus. A real deployment loads a k-anonymity
#: breach list; NIST 800-63B favours a blocklist over composition rules.
COMMON_PASSWORDS = frozenset(
    {
        "password",
        "password123",
        "12345678",
        "qwertyuiop",
        "letmein123",
        "trustlens",
        "administrator",
        "iloveyou123",
    }
)


@dataclass(frozen=True, slots=True)
class PasswordPolicy:
    min_length: int = 12

    def validate(self, password: str, *, email: str | None = None) -> list[str]:
        """Return a list of problems; empty means acceptable.

        Returns rather than raises so a form can show every issue at once
        instead of making the user discover them one at a time.
        """
        problems: list[str] = []
        if len(password) < self.min_length:
            problems.append(f"Use at least {self.min_length} characters.")
        if password.lower() in COMMON_PASSWORDS:
            problems.append("This password is too common.")
        if email and email.split("@")[0].lower() in password.lower():
            problems.append("Do not use your email address in your password.")
        if password.isdigit():
            problems.append("Use more than just numbers.")
        if len(set(password)) < 5:
            problems.append("Use a wider variety of characters.")
        return problems


# ── Login throttling ─────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LoginThrottlePolicy:
    soft_limit: int = 5
    hard_limit: int = 10
    base_lock_seconds: int = 60

    def lock_until(self, *, failed_count: int, now: datetime) -> datetime | None:
        """Exponential backoff past the hard limit, capped at one hour."""
        if failed_count < self.hard_limit:
            return None
        exponent = min(failed_count - self.hard_limit, 6)
        seconds = min(self.base_lock_seconds * (2**exponent), 3600)
        return now + timedelta(seconds=seconds)


# ── MFA ──────────────────────────────────────────────────────────────


def mfa_required_for(user: User) -> bool:
    """Admin and reviewer accounts can override scores and read identity
    documents, so they are the highest-value targets in the system."""
    return user.requires_mfa


__all__ = [
    "COMMON_PASSWORDS",
    "DEFAULT_MIN_EVIDENCE_WEIGHT",
    "AccountAgePolicy",
    "AppealPolicy",
    "DeviceLinkagePolicy",
    "FreshnessPolicy",
    "LoginThrottlePolicy",
    "PasswordPolicy",
    "Score",
    "ScoreComputation",
    "ScoringPolicy",
    "band_for",
    "band_label",
    "mfa_required_for",
    "rank_improvements",
]
