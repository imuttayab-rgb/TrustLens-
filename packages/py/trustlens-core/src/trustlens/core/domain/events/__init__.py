"""Domain events.

Published inside the use case's transaction via the outbox, so an event can
never be emitted for a change that then rolls back ("score updated but the
webhook never fired", or worse, the reverse).

Score recomputation is driven by these rather than called inline: any signal
change - identity, phone, email, device, listing, admin override, weight
change - then recomputes through exactly one code path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from trustlens.core.domain.enums import RiskLevel, ScoreTrigger


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base event. `occurred_at` is passed in, never read from a clock here."""

    event_type: ClassVar[str] = "domain.event"
    aggregate_type: ClassVar[str] = "unknown"

    aggregate_id: UUID
    occurred_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)

    def to_outbox(self) -> dict[str, Any]:
        return {
            "aggregate_type": self.aggregate_type,
            "aggregate_id": str(self.aggregate_id),
            "event_type": self.event_type,
            "payload": self.payload,
            "occurred_at": self.occurred_at,
        }


# ── Account ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class UserRegistered(DomainEvent):
    event_type: ClassVar[str] = "user.registered"
    aggregate_type: ClassVar[str] = "user"


@dataclass(frozen=True, slots=True)
class EmailVerified(DomainEvent):
    event_type: ClassVar[str] = "user.email_verified"
    aggregate_type: ClassVar[str] = "user"


@dataclass(frozen=True, slots=True)
class PhoneVerified(DomainEvent):
    event_type: ClassVar[str] = "user.phone_verified"
    aggregate_type: ClassVar[str] = "user"


@dataclass(frozen=True, slots=True)
class RefreshTokenReuseDetected(DomainEvent):
    """Security-critical: raises an alert as well as revoking the family."""

    event_type: ClassVar[str] = "auth.token_reuse_detected"
    aggregate_type: ClassVar[str] = "user"


# ── Verification ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IdentitySubmitted(DomainEvent):
    event_type: ClassVar[str] = "identity.submitted"
    aggregate_type: ClassVar[str] = "seller"


@dataclass(frozen=True, slots=True)
class IdentityVerified(DomainEvent):
    event_type: ClassVar[str] = "identity.verified"
    aggregate_type: ClassVar[str] = "seller"


@dataclass(frozen=True, slots=True)
class IdentityRejected(DomainEvent):
    event_type: ClassVar[str] = "identity.rejected"
    aggregate_type: ClassVar[str] = "seller"


@dataclass(frozen=True, slots=True)
class DuplicateIdentityDetected(DomainEvent):
    """One CNIC across several accounts - opens a review case automatically."""

    event_type: ClassVar[str] = "identity.duplicate_detected"
    aggregate_type: ClassVar[str] = "seller"


# ── Listings ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ListingCreated(DomainEvent):
    event_type: ClassVar[str] = "listing.created"
    aggregate_type: ClassVar[str] = "listing"


@dataclass(frozen=True, slots=True)
class ListingAnalysed(DomainEvent):
    event_type: ClassVar[str] = "listing.analysed"
    aggregate_type: ClassVar[str] = "listing"


# ── Scoring ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TrustScoreComputed(DomainEvent):
    event_type: ClassVar[str] = "trust_score.computed"
    aggregate_type: ClassVar[str] = "seller"

    @classmethod
    def build(
        cls,
        *,
        seller_id: UUID,
        score: int,
        risk_level: RiskLevel,
        previous_score: int | None,
        trigger: ScoreTrigger,
        model_version: str,
        occurred_at: datetime,
    ) -> TrustScoreComputed:
        return cls(
            aggregate_id=seller_id,
            occurred_at=occurred_at,
            payload={
                "seller_id": str(seller_id),
                "score": score,
                "risk_level": risk_level.value,
                "previous_score": previous_score,
                "delta": None if previous_score is None else score - previous_score,
                "trigger": trigger.value,
                "model_version": model_version,
            },
        )


@dataclass(frozen=True, slots=True)
class TrustScoreOverridden(DomainEvent):
    event_type: ClassVar[str] = "trust_score.overridden"
    aggregate_type: ClassVar[str] = "seller"


@dataclass(frozen=True, slots=True)
class ScoringModelActivated(DomainEvent):
    """Triggers a bulk recompute; old scores are kept as history."""

    event_type: ClassVar[str] = "scoring_model.activated"
    aggregate_type: ClassVar[str] = "scoring_model"


# ── Appeals & moderation ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AppealSubmitted(DomainEvent):
    event_type: ClassVar[str] = "appeal.submitted"
    aggregate_type: ClassVar[str] = "appeal"


@dataclass(frozen=True, slots=True)
class AppealResolved(DomainEvent):
    event_type: ClassVar[str] = "appeal.resolved"
    aggregate_type: ClassVar[str] = "appeal"


@dataclass(frozen=True, slots=True)
class SellerFlagged(DomainEvent):
    event_type: ClassVar[str] = "seller.flagged"
    aggregate_type: ClassVar[str] = "seller"


__all__ = [
    "AppealResolved",
    "AppealSubmitted",
    "DomainEvent",
    "DuplicateIdentityDetected",
    "EmailVerified",
    "IdentityRejected",
    "IdentitySubmitted",
    "IdentityVerified",
    "ListingAnalysed",
    "ListingCreated",
    "PhoneVerified",
    "RefreshTokenReuseDetected",
    "ScoringModelActivated",
    "SellerFlagged",
    "TrustScoreComputed",
    "TrustScoreOverridden",
    "UserRegistered",
]
