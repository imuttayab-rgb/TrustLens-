"""Identity and access entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from trustlens.core.domain.enums import (
    AccountStatus,
    ConsentType,
    OtpPurpose,
    TokenPurpose,
    UserRole,
)
from trustlens.core.domain.value_objects import Email, PhoneE164


@dataclass(frozen=True, slots=True)
class Permission:
    """`resource:action[:scope]`, e.g. `seller:read:self`.

    The `:self` / `:any` suffix is deliberate: a seller and an admin both
    "read a seller", but only one may read someone else's. Encoding scope in
    the permission keeps ownership logic in one guard instead of an ad-hoc
    `if owner_id != user.id` at every call site.
    """

    id: UUID
    key: str
    resource: str
    action: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class Role:
    id: UUID
    key: UserRole
    name: str
    description: str = ""
    is_system: bool = True
    permissions: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: Email
    full_name: str
    status: AccountStatus
    primary_role: UserRole
    created_at: datetime
    roles: frozenset[UserRole] = frozenset()
    permissions: frozenset[str] = frozenset()
    email_verified_at: datetime | None = None
    mfa_enabled: bool = False
    failed_login_count: int = 0
    locked_until: datetime | None = None
    last_login_at: datetime | None = None
    password_changed_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    version: int = 1

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_active(self) -> bool:
        return self.status == AccountStatus.ACTIVE and self.deleted_at is None

    def is_locked_at(self, now: datetime) -> bool:
        return self.locked_until is not None and self.locked_until > now

    def has_role(self, role: UserRole) -> bool:
        return role in self.roles or role == self.primary_role

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    @property
    def requires_mfa(self) -> bool:
        """Admin and reviewer accounts can override scores and view identity
        documents - the highest-value targets in the system."""
        return bool(self.roles & {UserRole.ADMIN, UserRole.REVIEWER})


@dataclass(frozen=True, slots=True)
class RefreshToken:
    """A rotating refresh token.

    Only the hash is ever persisted. `family_id` ties a rotation chain
    together so that presenting an already-rotated token can revoke every
    descendant at once (ADR-0006).
    """

    id: UUID
    user_id: UUID
    token_hash: bytes
    family_id: UUID
    expires_at: datetime
    created_at: datetime
    parent_id: UUID | None = None
    device_id: UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    revoked_at: datetime | None = None
    revoked_reason: str | None = None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired_at(self, now: datetime) -> bool:
        return now >= self.expires_at

    def is_usable_at(self, now: datetime) -> bool:
        return not self.is_revoked and not self.is_expired_at(now)


@dataclass(frozen=True, slots=True)
class VerificationToken:
    """Single-use, hashed token for email verification / password reset."""

    id: UUID
    user_id: UUID
    purpose: TokenPurpose
    token_hash: bytes
    target: str
    expires_at: datetime
    created_at: datetime
    consumed_at: datetime | None = None

    def is_usable_at(self, now: datetime) -> bool:
        return self.consumed_at is None and now < self.expires_at


@dataclass(frozen=True, slots=True)
class OtpCode:
    """A hashed one-time code.

    The code is HMAC-hashed with a server pepper held outside the database, so
    a database leak does not hand out live codes.
    """

    id: UUID
    user_id: UUID
    phone_number_id: UUID | None
    purpose: OtpPurpose
    code_hash: bytes
    expires_at: datetime
    created_at: datetime
    attempts: int = 0
    max_attempts: int = 5
    consumed_at: datetime | None = None
    sent_at: datetime | None = None

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def attempts_exhausted(self) -> bool:
        return self.attempts >= self.max_attempts

    def is_usable_at(self, now: datetime) -> bool:
        return not self.is_consumed and not self.attempts_exhausted and now < self.expires_at


@dataclass(frozen=True, slots=True)
class Consent:
    """Versioned, timestamped consent.

    Required before any biometric processing: TrustLens compares a face to a
    national ID photo, which is biometric data under most data-protection
    regimes and an ethical baseline regardless.
    """

    id: UUID
    user_id: UUID
    consent_type: ConsentType
    version: str
    granted: bool
    granted_at: datetime
    ip: str | None = None
    user_agent: str | None = None
    revoked_at: datetime | None = None

    @property
    def is_effective(self) -> bool:
        return self.granted and self.revoked_at is None


@dataclass(frozen=True, slots=True)
class AuthenticatedActor:
    """Whoever is making the current request.

    Three principal types exist (user, API client, system job), so nothing in
    the codebase may assume "there is a current user".
    """

    user_id: UUID | None
    roles: frozenset[UserRole] = frozenset()
    permissions: frozenset[str] = frozenset()
    api_client_id: UUID | None = None
    scopes: frozenset[str] = frozenset()
    is_system: bool = False
    session_id: UUID | None = None

    @classmethod
    def system(cls) -> AuthenticatedActor:
        return cls(user_id=None, is_system=True)

    def has_permission(self, permission: str) -> bool:
        return self.is_system or permission in self.permissions

    def has_any_role(self, *roles: UserRole) -> bool:
        return bool(self.roles & set(roles))


@dataclass(frozen=True, slots=True)
class Notification:
    id: UUID
    user_id: UUID
    type: str
    title: str
    body: str
    created_at: datetime
    channel: str = "IN_APP"
    data: dict[str, object] = field(default_factory=dict)
    read_at: datetime | None = None
    sent_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NewUserRegistration:
    """Input bundle for registration - avoids a 6-positional-argument call."""

    email: Email
    full_name: str
    password: str
    as_seller: bool = False
    phone: PhoneE164 | None = None


__all__ = [
    "AuthenticatedActor",
    "Consent",
    "NewUserRegistration",
    "Notification",
    "OtpCode",
    "Permission",
    "RefreshToken",
    "Role",
    "User",
    "VerificationToken",
]
