"""Partner and API key management (feature F9, Phase 6).

The public score endpoint already exists and already authenticates keys. What
was missing is everything around a key's *life*: who gets one, how it is
rotated when a partner leaks it into a git repository, and how it is killed.

Three properties this module holds.

* **The secret is shown exactly once.** Only an argon2 hash is stored, so a
  lost key cannot be recovered - it is rotated. Any design where support can
  read a partner's key back to them is a design where a database dump is a
  set of live credentials.
* **Rotation is not revocation.** A partner who rotates gets a new key while
  the old one keeps working for a short overlap, because the alternative is
  an outage in the middle of their deploy. Revocation is immediate and has no
  overlap - that is the whole point of it.
* **Scopes are granted, never assumed.** A key with no scopes can authenticate
  and do nothing, which is the correct default for a credential whose blast
  radius is somebody else's marketplace.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from trustlens.core.domain.entities import ApiClient, ApiKey, AuditLogEntry
from trustlens.core.domain.enums import ApiKeyStatus
from trustlens.core.domain.errors import (
    ConflictError,
    EntityNotFound,
    InvalidStateError,
    ValidationError,
)
from trustlens.core.domain.ports import ApiKeyGenerator, Clock, IdGenerator, UnitOfWork

#: What a partner key may be allowed to do. Deliberately small: every scope
#: here is a promise about data leaving the system, and the public API exposes
#: no PII by construction (docs/06).
SCOPE_SCORE_READ = "score:read"
SCOPE_SCORE_BATCH = "score:batch"
SCOPE_WEBHOOK_MANAGE = "webhook:manage"

SCOPES = frozenset({SCOPE_SCORE_READ, SCOPE_SCORE_BATCH, SCOPE_WEBHOOK_MANAGE})

#: A new key issued by a rotation overlaps the old one for this long. Long
#: enough to redeploy, short enough that a leaked key is not usable for a week.
ROTATION_GRACE = timedelta(hours=24)

#: Statuses an API client can hold. PENDING clients authenticate nothing:
#: registering interest is not the same as being approved.
CLIENT_PENDING = "PENDING"
CLIENT_ACTIVE = "ACTIVE"
CLIENT_SUSPENDED = "SUSPENDED"


@dataclass(frozen=True, slots=True)
class RegisterApiClientCommand:
    name: str
    slug: str
    contact_email: str
    actor_id: UUID
    contact_name: str | None = None
    marketplace_id: UUID | None = None
    rate_limit_tier: str = "free"
    monthly_quota: int = 10_000


class RegisterApiClient:
    """Create a partner. No key is issued here - approval comes first."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: RegisterApiClientCommand) -> ApiClient:
        name = cmd.name.strip()
        slug = cmd.slug.strip().lower()
        if len(name) < 2:
            raise ValidationError("Enter the partner's name.", field="name")
        if not slug.replace("-", "").isalnum() or len(slug) < 2:
            raise ValidationError(
                "Use lowercase letters, numbers and hyphens for the slug.", field="slug"
            )
        if cmd.monthly_quota < 1:
            raise ValidationError("A quota below one request is not a quota.", field="monthlyQuota")

        now = self._clock.now()
        async with self._uow:
            existing = await self._uow.api_clients.get_by_slug(slug)
            if existing is not None:
                raise ConflictError("A partner with that slug already exists.")

            client = await self._uow.api_clients.create(
                ApiClient(
                    id=self._ids.new(),
                    name=name,
                    slug=slug,
                    contact_email=cmd.contact_email.strip().lower(),
                    contact_name=cmd.contact_name,
                    marketplace_id=cmd.marketplace_id,
                    # PENDING, not ACTIVE: an unapproved partner must not be one
                    # forgotten checkbox away from live traffic.
                    status=CLIENT_PENDING,
                    rate_limit_tier=cmd.rate_limit_tier,
                    monthly_quota=cmd.monthly_quota,
                    created_at=now,
                )
            )
            await self._uow.audit_logs.record(
                AuditLogEntry(
                    id=self._ids.new(),
                    action="api_client.registered",
                    entity_type="api_clients",
                    entity_id=client.id,
                    actor_id=cmd.actor_id,
                    occurred_at=now,
                    before=None,
                    after={"slug": slug, "status": CLIENT_PENDING},
                )
            )
            await self._uow.commit()
        return client


@dataclass(frozen=True, slots=True)
class SetApiClientStatusCommand:
    client_id: UUID
    status: str
    actor_id: UUID


class SetApiClientStatus:
    """Approve, suspend or reinstate a partner.

    Suspending is the blunt instrument that stops all of a partner's traffic
    without hunting down each key they hold.
    """

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: SetApiClientStatusCommand) -> ApiClient:
        if cmd.status not in {CLIENT_PENDING, CLIENT_ACTIVE, CLIENT_SUSPENDED}:
            raise ValidationError("Unknown status.", field="status")

        now = self._clock.now()
        async with self._uow:
            client = await self._uow.api_clients.get(cmd.client_id)
            if client is None:
                raise EntityNotFound("api_client", cmd.client_id)

            updated: ApiClient = await self._uow.api_clients.update(
                dataclasses.replace(client, status=cmd.status, updated_at=now)
            )
            await self._uow.audit_logs.record(
                AuditLogEntry(
                    id=self._ids.new(),
                    action="api_client.status_changed",
                    entity_type="api_clients",
                    entity_id=client.id,
                    actor_id=cmd.actor_id,
                    occurred_at=now,
                    before={"status": client.status},
                    after={"status": cmd.status},
                )
            )
            await self._uow.commit()
        return updated


@dataclass(frozen=True, slots=True)
class IssueApiKeyCommand:
    client_id: UUID
    name: str
    actor_id: UUID
    scopes: frozenset[str] = frozenset({SCOPE_SCORE_READ})
    expires_in_days: int | None = None


@dataclass(frozen=True, slots=True)
class IssuedKey:
    """The one and only time the plaintext key exists outside the partner."""

    key: ApiKey
    #: Never persisted, never logged, never returned again.
    plaintext: str


class IssueApiKey:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        keys: ApiKeyGenerator,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._uow = uow
        self._keys = keys
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: IssueApiKeyCommand) -> IssuedKey:
        name = cmd.name.strip()
        if not name:
            raise ValidationError("Name the key, so it can be revoked knowingly.", field="name")

        unknown = set(cmd.scopes) - SCOPES
        if unknown:
            raise ValidationError(f"Unknown scope: {', '.join(sorted(unknown))}.", field="scopes")

        now = self._clock.now()
        async with self._uow:
            client = await self._uow.api_clients.get(cmd.client_id)
            if client is None:
                raise EntityNotFound("api_client", cmd.client_id)
            # A key for a partner who cannot use it is a live credential with
            # no owner watching it.
            if not client.is_active:
                raise InvalidStateError(
                    "This partner is not active, so a key would not authenticate."
                )

            plaintext, prefix, key_hash = self._keys.generate()
            key = await self._uow.api_clients.add_key(
                ApiKey(
                    id=self._ids.new(),
                    api_client_id=client.id,
                    name=name,
                    key_prefix=prefix,
                    key_hash=key_hash,
                    status=ApiKeyStatus.ACTIVE,
                    scopes=frozenset(cmd.scopes),
                    created_at=now,
                    expires_at=(
                        now + timedelta(days=cmd.expires_in_days) if cmd.expires_in_days else None
                    ),
                )
            )
            await self._uow.audit_logs.record(
                AuditLogEntry(
                    id=self._ids.new(),
                    action="api_key.issued",
                    entity_type="api_keys",
                    entity_id=key.id,
                    actor_id=cmd.actor_id,
                    occurred_at=now,
                    before=None,
                    # The prefix identifies the key in the audit trail; the
                    # secret half is not here and is not anywhere.
                    after={"prefix": prefix, "scopes": sorted(cmd.scopes)},
                )
            )
            await self._uow.commit()

        return IssuedKey(key=key, plaintext=plaintext)


@dataclass(frozen=True, slots=True)
class RotateApiKeyCommand:
    key_id: UUID
    actor_id: UUID
    grace: timedelta = ROTATION_GRACE


class RotateApiKey:
    """Issue a replacement and expire the old key after a short overlap.

    The overlap is the point. Revoking-then-issuing takes the partner down for
    however long their deploy takes, so in practice nobody rotates, and a key
    that leaked into a public repository stays live for months.
    """

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        keys: ApiKeyGenerator,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._uow = uow
        self._keys = keys
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: RotateApiKeyCommand) -> IssuedKey:
        now = self._clock.now()
        async with self._uow:
            old = await self._uow.api_clients.get_key(cmd.key_id)
            if old is None:
                raise EntityNotFound("api_key", cmd.key_id)
            if old.status is not ApiKeyStatus.ACTIVE:
                raise InvalidStateError("Only an active key can be rotated.")

            plaintext, prefix, key_hash = self._keys.generate()
            replacement = await self._uow.api_clients.add_key(
                ApiKey(
                    id=self._ids.new(),
                    api_client_id=old.api_client_id,
                    name=f"{old.name} (rotated)",
                    key_prefix=prefix,
                    key_hash=key_hash,
                    status=ApiKeyStatus.ACTIVE,
                    scopes=old.scopes,
                    created_at=now,
                    expires_at=old.expires_at,
                )
            )

            # The old key expires rather than being revoked outright: still
            # usable during the overlap, dead immediately after it.
            await self._uow.api_clients.expire_key(old.id, at=now + cmd.grace)

            await self._uow.audit_logs.record(
                AuditLogEntry(
                    id=self._ids.new(),
                    action="api_key.rotated",
                    entity_type="api_keys",
                    entity_id=old.id,
                    actor_id=cmd.actor_id,
                    occurred_at=now,
                    before={"prefix": old.key_prefix},
                    after={
                        "prefix": prefix,
                        "old_expires_at": (now + cmd.grace).isoformat(),
                    },
                )
            )
            await self._uow.commit()

        return IssuedKey(key=replacement, plaintext=plaintext)


@dataclass(frozen=True, slots=True)
class RevokeApiKeyCommand:
    key_id: UUID
    actor_id: UUID


class RevokeApiKey:
    """Kill a key now. No overlap - that is what revocation means."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: RevokeApiKeyCommand) -> None:
        now = self._clock.now()
        async with self._uow:
            key = await self._uow.api_clients.get_key(cmd.key_id)
            if key is None:
                raise EntityNotFound("api_key", cmd.key_id)
            # Revoking twice is not an error worth raising on, but it must not
            # rewrite who revoked it or when.
            if key.revoked_at is not None:
                return

            await self._uow.api_clients.revoke_key(key.id, by=cmd.actor_id, at=now)
            await self._uow.audit_logs.record(
                AuditLogEntry(
                    id=self._ids.new(),
                    action="api_key.revoked",
                    entity_type="api_keys",
                    entity_id=key.id,
                    actor_id=cmd.actor_id,
                    occurred_at=now,
                    before={"status": key.status.value},
                    after={"status": ApiKeyStatus.REVOKED.value},
                )
            )
            await self._uow.commit()


@dataclass(frozen=True, slots=True)
class ClientUsage:
    client: ApiClient
    used_this_month: int
    quota: int

    @property
    def remaining(self) -> int:
        return max(0, self.quota - self.used_this_month)

    @property
    def percent_used(self) -> float:
        return round(100 * self.used_this_month / self.quota, 1) if self.quota else 0.0


class ListApiClients:
    """Every partner, with this month's usage against quota."""

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self) -> tuple[ClientUsage, ...]:
        async with self._uow:
            clients = await self._uow.api_clients.list_all()
            usages = [
                ClientUsage(
                    client=client,
                    used_this_month=await self._uow.api_clients.usage_this_month(client.id),
                    quota=client.monthly_quota,
                )
                for client in clients
            ]
        return tuple(usages)


class ListApiKeys:
    """Keys for one partner. Hashes never leave the repository layer."""

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, client_id: UUID) -> tuple[ApiKey, ...]:
        async with self._uow:
            client = await self._uow.api_clients.get(client_id)
            if client is None:
                raise EntityNotFound("api_client", client_id)
            keys = await self._uow.api_clients.list_keys(client_id)
        return tuple(keys)


def expiry_for(key: ApiKey, now: datetime) -> str:
    """Human-readable key state, used by the admin list."""
    if key.revoked_at is not None:
        return "revoked"
    if key.expires_at is None:
        return "active"
    if key.expires_at <= now:
        return "expired"
    return f"expires {key.expires_at.date().isoformat()}"


__all__ = [
    "CLIENT_ACTIVE",
    "CLIENT_PENDING",
    "CLIENT_SUSPENDED",
    "ROTATION_GRACE",
    "SCOPES",
    "SCOPE_SCORE_BATCH",
    "SCOPE_SCORE_READ",
    "SCOPE_WEBHOOK_MANAGE",
    "ClientUsage",
    "IssueApiKey",
    "IssueApiKeyCommand",
    "IssuedKey",
    "ListApiClients",
    "ListApiKeys",
    "RegisterApiClient",
    "RegisterApiClientCommand",
    "RevokeApiKey",
    "RevokeApiKeyCommand",
    "RotateApiKey",
    "RotateApiKeyCommand",
    "SetApiClientStatus",
    "SetApiClientStatusCommand",
    "expiry_for",
]
