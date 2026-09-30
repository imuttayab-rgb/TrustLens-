"""Public API schemas.

These models are deliberately PII-free. There is no email, phone, CNIC, image
URL or legal name field anywhere in this module - so a future contributor
cannot leak one by adding a line to a serialiser. An automated test asserts
the absence of forbidden keys in every public response.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class PublicSchema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class PublicReasonModel(PublicSchema):
    code: str = Field(description="Stable reason code. Switch on this, not on `text`.")
    impact: str = Field(description="POSITIVE | NEGATIVE | NEUTRAL")
    category: str = Field(
        default="",
        description=(
            "Signal family: IDENTITY | PHONE | EMAIL | DEVICE | NETWORK | "
            "BEHAVIOUR | LISTING. Names the kind of check, never what was "
            "checked, so it carries no PII."
        ),
    )
    text: str = Field(description="Buyer-readable explanation.")


class PublicScoreResponse(PublicSchema):
    seller_ref: str
    score: int = Field(ge=0, le=100)
    risk_level: str = Field(description="LOW | MEDIUM | HIGH | UNKNOWN")
    risk_label: str
    confidence: float = Field(ge=0, le=1, description="How much evidence the score is based on.")
    verifications: dict[str, str] = Field(description="Per-check status: identity, phone, email.")
    reasons: list[PublicReasonModel]
    model_version: str
    computed_at: str
    expires_at: str
    unavailable_signals: list[str] = Field(
        default_factory=list,
        description=(
            "Checks that could not be performed. These are excluded from the "
            "score rather than counted as failures."
        ),
    )
    member_since: str = Field(default="", description="ISO timestamp the seller account opened.")
    bio: str | None = Field(default=None, description="Seller-authored storefront description.")
    city: str | None = Field(default=None)
    follower_count: int = Field(default=0, ge=0)
    completed_sales: int = Field(default=0, ge=0)


class BatchLookupRequest(PublicSchema):
    seller_refs: list[str] = Field(min_length=1, max_length=50)


class BatchLookupResponse(PublicSchema):
    results: list[dict[str, Any]]
    not_found: list[str] = Field(default_factory=list)


class PublicStatusResponse(PublicSchema):
    status: str
    scoring_model_version: str
    api_version: str


class RegisterSellerRequest(PublicSchema):
    """Partner-initiated seller onboarding (assumption A3)."""

    external_seller_ref: str = Field(max_length=120)
    display_name: str = Field(min_length=2, max_length=150)
    contact_email: str = Field(max_length=254)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    city: str | None = Field(default=None, max_length=80)
    account_opened_at: str | None = Field(
        default=None,
        description=(
            "When the seller joined YOUR platform. Supplying it lets an "
            "established seller keep their account-age credit."
        ),
    )


class RegisterSellerResponse(PublicSchema):
    seller_ref: str
    invite_url: str
    status: str


__all__ = [
    "BatchLookupRequest",
    "BatchLookupResponse",
    "PublicReasonModel",
    "PublicScoreResponse",
    "PublicStatusResponse",
    "RegisterSellerRequest",
    "RegisterSellerResponse",
]
