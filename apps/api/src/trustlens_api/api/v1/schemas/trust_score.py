"""Trust score schemas - the shape that makes a score explainable."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from trustlens_api.api.v1.schemas.common import Schema


class SignalBreakdown(Schema):
    code: str
    category: str
    status: str = Field(description="PASS | PARTIAL | FAIL | UNAVAILABLE | NOT_APPLICABLE")
    points_awarded: float
    points_possible: float
    confidence: float
    reason_code: str = Field(description="Stable machine-readable code; switch on this.")
    reason_text: str = Field(description="Buyer-readable sentence.")
    evidence: dict = Field(default_factory=dict, description="Non-PII supporting values.")


class CategoryRollup(Schema):
    category: str
    points_awarded: float
    points_possible: float
    status: str


class ImprovementItem(Schema):
    signal_code: str
    points_available: float
    action: str


class TrustScoreResponse(Schema):
    seller_id: UUID
    score: int = Field(ge=0, le=100)
    risk_level: str = Field(description="LOW | MEDIUM | HIGH | UNKNOWN")
    risk_label: str
    confidence: float
    model_version: str
    computed_at: datetime
    valid_until: datetime
    #: Set when a failed critical signal clamped the score. Its presence tells
    #: a reviewer the score was capped, not computed.
    cap_applied: int | None = None
    is_manual_override: bool = False
    categories: list[CategoryRollup]
    signals: list[SignalBreakdown]
    unavailable_signals: list[str] = Field(default_factory=list)
    summary: str


class TrustScoreHistoryItem(Schema):
    id: UUID
    score: int
    risk_level: str
    model_version: str
    trigger: str
    computed_at: datetime
    is_manual_override: bool = False


class RecomputeRequest(Schema):
    reason: str | None = Field(default=None, max_length=500)


class OverrideScoreRequest(Schema):
    score: int = Field(ge=0, le=100)
    #: Required by a database CHECK constraint as well - overriding the engine
    #: must always be attributable.
    reason: str = Field(min_length=10, max_length=1000)


__all__ = [
    "CategoryRollup",
    "ImprovementItem",
    "OverrideScoreRequest",
    "RecomputeRequest",
    "SignalBreakdown",
    "TrustScoreHistoryItem",
    "TrustScoreResponse",
]
