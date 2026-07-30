"""Seller and marketplace entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from trustlens.core.domain.enums import VerificationStatus


@dataclass(frozen=True, slots=True)
class Marketplace:
    """A platform a seller trades on (OLX-style, rentals, vehicles, freelance).

    Needed to scope `external_seller_ref` - a partner looks a seller up by
    *their* id, not ours - and to report fraud rates per platform.
    """

    id: UUID
    name: str
    slug: str
    website_url: str | None = None
    country_code: str | None = None
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class SellerProfile:
    """Seller-specific attributes, separate from the account.

    The four `*_status` fields and `current_trust_score_id` are denormalised
    so the dashboard and public page render in one round trip. They are
    written by the same use case, inside the same transaction, as the
    authoritative rows - so they cannot drift.
    """

    id: UUID
    user_id: UUID
    handle: str
    display_name: str
    account_opened_at: datetime
    created_at: datetime
    marketplace_id: UUID | None = None
    external_seller_ref: str | None = None
    business_type: str | None = None
    city: str | None = None
    country_code: str | None = None
    bio: str | None = None
    current_trust_score_id: UUID | None = None
    identity_status: VerificationStatus = VerificationStatus.NOT_STARTED
    phone_status: VerificationStatus = VerificationStatus.NOT_STARTED
    email_status: VerificationStatus = VerificationStatus.NOT_STARTED
    is_flagged: bool = False
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    version: int = 1

    def account_age_days(self, now: datetime) -> int:
        return max(0, (now - self.account_opened_at).days)

    @property
    def is_fully_verified(self) -> bool:
        return all(
            s == VerificationStatus.VERIFIED
            for s in (self.identity_status, self.phone_status, self.email_status)
        )


__all__ = ["Marketplace", "SellerProfile"]
