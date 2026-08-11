"""Partner and API key lifecycle (Phase 6).

The properties worth protecting are the ones that decide whether handing a
marketplace a credential is safe:

* the plaintext key exists exactly once, and is never recoverable,
* rotation does not take the partner down, revocation does,
* a key cannot be issued for a partner who is not approved,
* scopes are granted explicitly, never inferred.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

import pytest

from trustlens.core.application.use_cases.public_api import (
    CLIENT_ACTIVE,
    CLIENT_PENDING,
    CLIENT_SUSPENDED,
    SCOPE_SCORE_READ,
    IssueApiKey,
    IssueApiKeyCommand,
    ListApiClients,
    RegisterApiClient,
    RegisterApiClientCommand,
    RevokeApiKey,
    RevokeApiKeyCommand,
    RotateApiKey,
    RotateApiKeyCommand,
    SetApiClientStatus,
    SetApiClientStatusCommand,
)
from trustlens.core.domain.entities import ApiClient, ApiKey
from trustlens.core.domain.enums import ApiKeyStatus
from trustlens.core.domain.errors import (
    ConflictError,
    EntityNotFound,
    InvalidStateError,
    ValidationError,
)

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
CLIENT_ID = UUID("00000000-0000-0000-0000-0000000000c1")
KEY_ID = UUID("00000000-0000-0000-0000-0000000000k1".replace("k", "9"))
ACTOR = UUID("00000000-0000-0000-0000-0000000000a1")


class FakeClock:
    def now(self) -> datetime:
        return NOW


class FakeIds:
    def __init__(self) -> None:
        self._n = 0

    def new(self) -> UUID:
        self._n += 1
        return UUID(int=self._n)


class FakeKeyFactory:
    """Deterministic, and records how many keys it minted."""

    def __init__(self) -> None:
        self.calls = 0

    def generate(self) -> tuple[str, str, bytes]:
        self.calls += 1
        return (f"tl_test_{self.calls}.secret{self.calls}", f"tl_test_{self.calls}", b"hash")

    def verify(self, secret: str, key_hash: bytes) -> bool:
        return True


def make_client(**overrides: Any) -> ApiClient:
    defaults: dict[str, Any] = {
        "id": CLIENT_ID,
        "name": "Daraz",
        "slug": "daraz",
        "contact_email": "api@daraz.pk",
        "status": CLIENT_ACTIVE,
        "created_at": NOW,
    }
    return ApiClient(**{**defaults, **overrides})


def make_key(**overrides: Any) -> ApiKey:
    defaults: dict[str, Any] = {
        "id": KEY_ID,
        "api_client_id": CLIENT_ID,
        "name": "production",
        "key_prefix": "tl_test_old",
        "key_hash": b"hash",
        "status": ApiKeyStatus.ACTIVE,
        "scopes": frozenset({SCOPE_SCORE_READ}),
        "created_at": NOW,
    }
    return ApiKey(**{**defaults, **overrides})


class FakeApiClients:
    def __init__(
        self, client: ApiClient | None = None, key: ApiKey | None = None, by_slug: bool = False
    ) -> None:
        self.client = client
        self.key = key
        self._by_slug = by_slug
        self.created: list[ApiClient] = []
        self.updated: list[ApiClient] = []
        self.added_keys: list[ApiKey] = []
        self.revoked: list[tuple[UUID, UUID, datetime]] = []
        self.expired: list[tuple[UUID, datetime]] = []
        self.usage = 0

    async def get(self, client_id: UUID) -> ApiClient | None:
        return self.client

    async def get_by_slug(self, slug: str) -> ApiClient | None:
        return self.client if self._by_slug else None

    async def create(self, client: ApiClient) -> ApiClient:
        self.created.append(client)
        return client

    async def update(self, client: ApiClient) -> ApiClient:
        self.updated.append(client)
        return client

    async def list_all(self) -> list[ApiClient]:
        return [self.client] if self.client else []

    async def get_key(self, key_id: UUID) -> ApiKey | None:
        return self.key

    async def list_keys(self, client_id: UUID) -> list[ApiKey]:
        return [self.key] if self.key else []

    async def add_key(self, key: ApiKey) -> ApiKey:
        self.added_keys.append(key)
        return key

    async def revoke_key(self, key_id: UUID, *, by: UUID, at: datetime) -> None:
        self.revoked.append((key_id, by, at))

    async def expire_key(self, key_id: UUID, *, at: datetime) -> None:
        self.expired.append((key_id, at))

    async def usage_this_month(self, client_id: UUID) -> int:
        return self.usage


class FakeAuditLogs:
    def __init__(self) -> None:
        self.entries: list[Any] = []

    async def record(self, entry: Any) -> None:
        self.entries.append(entry)


class FakeUow:
    def __init__(self, api_clients: FakeApiClients | None = None) -> None:
        self.api_clients = api_clients or FakeApiClients()
        self.audit_logs = FakeAuditLogs()
        self.committed = 0

    async def __aenter__(self) -> FakeUow:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def commit(self) -> None:
        self.committed += 1


def register_command(**overrides: Any) -> RegisterApiClientCommand:
    defaults: dict[str, Any] = {
        "name": "Daraz",
        "slug": "daraz",
        "contact_email": "api@daraz.pk",
        "actor_id": ACTOR,
    }
    return RegisterApiClientCommand(**{**defaults, **overrides})


class TestRegister:
    @pytest.mark.asyncio
    async def test_a_new_partner_starts_pending_not_active(self) -> None:
        # An unapproved partner must not be one forgotten checkbox away from
        # live traffic against real sellers' scores.
        uow = FakeUow()
        use_case = RegisterApiClient(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds())
        client = await use_case.execute(register_command())
        assert client.status == CLIENT_PENDING
        assert not client.is_active

    @pytest.mark.asyncio
    async def test_duplicate_slug_is_refused(self) -> None:
        uow = FakeUow(FakeApiClients(client=make_client(), by_slug=True))
        use_case = RegisterApiClient(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds())
        with pytest.raises(ConflictError):
            await use_case.execute(register_command())

    @pytest.mark.asyncio
    async def test_rejects_a_malformed_slug(self) -> None:
        uow = FakeUow()
        use_case = RegisterApiClient(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds())
        with pytest.raises(ValidationError):
            await use_case.execute(register_command(slug="Not A Slug!"))

    @pytest.mark.asyncio
    async def test_registration_is_audited(self) -> None:
        uow = FakeUow()
        use_case = RegisterApiClient(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds())
        await use_case.execute(register_command())
        assert [e.action for e in uow.audit_logs.entries] == ["api_client.registered"]


class TestIssue:
    def _use_case(self, uow: FakeUow, keys: FakeKeyFactory) -> IssueApiKey:
        return IssueApiKey(
            uow=cast(Any, uow), keys=cast(Any, keys), clock=FakeClock(), ids=FakeIds()
        )

    @pytest.mark.asyncio
    async def test_returns_the_plaintext_exactly_once(self) -> None:
        uow = FakeUow(FakeApiClients(client=make_client()))
        keys = FakeKeyFactory()
        issued = await self._use_case(uow, keys).execute(
            IssueApiKeyCommand(client_id=CLIENT_ID, name="production", actor_id=ACTOR)
        )
        assert issued.plaintext.startswith("tl_test_")
        # Only the hash is persisted - the plaintext is unrecoverable, so a
        # database dump is not a set of live credentials.
        assert uow.api_clients.added_keys[0].key_hash == b"hash"
        assert issued.plaintext not in str(uow.api_clients.added_keys[0])

    @pytest.mark.asyncio
    async def test_the_secret_never_reaches_the_audit_log(self) -> None:
        uow = FakeUow(FakeApiClients(client=make_client()))
        issued = await self._use_case(uow, FakeKeyFactory()).execute(
            IssueApiKeyCommand(client_id=CLIENT_ID, name="production", actor_id=ACTOR)
        )
        recorded = str(uow.audit_logs.entries[0].after)
        assert "secret" not in recorded
        assert issued.key.key_prefix in recorded

    @pytest.mark.asyncio
    async def test_refuses_a_key_for_a_pending_partner(self) -> None:
        uow = FakeUow(FakeApiClients(client=make_client(status=CLIENT_PENDING)))
        with pytest.raises(InvalidStateError):
            await self._use_case(uow, FakeKeyFactory()).execute(
                IssueApiKeyCommand(client_id=CLIENT_ID, name="production", actor_id=ACTOR)
            )

    @pytest.mark.asyncio
    async def test_refuses_a_key_for_a_suspended_partner(self) -> None:
        uow = FakeUow(FakeApiClients(client=make_client(status=CLIENT_SUSPENDED)))
        with pytest.raises(InvalidStateError):
            await self._use_case(uow, FakeKeyFactory()).execute(
                IssueApiKeyCommand(client_id=CLIENT_ID, name="production", actor_id=ACTOR)
            )

    @pytest.mark.asyncio
    async def test_rejects_an_unknown_scope(self) -> None:
        uow = FakeUow(FakeApiClients(client=make_client()))
        with pytest.raises(ValidationError):
            await self._use_case(uow, FakeKeyFactory()).execute(
                IssueApiKeyCommand(
                    client_id=CLIENT_ID,
                    name="production",
                    actor_id=ACTOR,
                    scopes=frozenset({"score:read", "admin:everything"}),
                )
            )

    @pytest.mark.asyncio
    async def test_an_unnamed_key_is_refused(self) -> None:
        # An unnamed key cannot be revoked knowingly: nobody dares kill the one
        # they cannot identify.
        uow = FakeUow(FakeApiClients(client=make_client()))
        with pytest.raises(ValidationError):
            await self._use_case(uow, FakeKeyFactory()).execute(
                IssueApiKeyCommand(client_id=CLIENT_ID, name="  ", actor_id=ACTOR)
            )

    @pytest.mark.asyncio
    async def test_expiry_is_applied_when_asked_for(self) -> None:
        uow = FakeUow(FakeApiClients(client=make_client()))
        issued = await self._use_case(uow, FakeKeyFactory()).execute(
            IssueApiKeyCommand(client_id=CLIENT_ID, name="temp", actor_id=ACTOR, expires_in_days=30)
        )
        assert issued.key.expires_at == NOW + timedelta(days=30)


class TestRotate:
    def _use_case(self, uow: FakeUow) -> RotateApiKey:
        return RotateApiKey(
            uow=cast(Any, uow), keys=cast(Any, FakeKeyFactory()), clock=FakeClock(), ids=FakeIds()
        )

    @pytest.mark.asyncio
    async def test_rotation_issues_a_new_key_and_expires_the_old_one(self) -> None:
        clients = FakeApiClients(client=make_client(), key=make_key())
        uow = FakeUow(clients)
        issued = await self._use_case(uow).execute(
            RotateApiKeyCommand(key_id=KEY_ID, actor_id=ACTOR)
        )

        assert issued.plaintext
        assert len(clients.added_keys) == 1
        # Expired, NOT revoked: the old key keeps working through the overlap
        # so the partner's deploy is not an outage. Revoking here is why
        # nobody rotates in practice, and why leaked keys stay live.
        assert clients.expired == [(KEY_ID, NOW + timedelta(hours=24))]
        assert clients.revoked == []

    @pytest.mark.asyncio
    async def test_the_replacement_inherits_the_original_scopes(self) -> None:
        scopes = frozenset({SCOPE_SCORE_READ, "score:batch"})
        clients = FakeApiClients(client=make_client(), key=make_key(scopes=scopes))
        uow = FakeUow(clients)
        await self._use_case(uow).execute(RotateApiKeyCommand(key_id=KEY_ID, actor_id=ACTOR))
        assert clients.added_keys[0].scopes == scopes

    @pytest.mark.asyncio
    async def test_a_revoked_key_cannot_be_rotated(self) -> None:
        clients = FakeApiClients(
            client=make_client(), key=make_key(status=ApiKeyStatus.REVOKED, revoked_at=NOW)
        )
        with pytest.raises(InvalidStateError):
            await self._use_case(FakeUow(clients)).execute(
                RotateApiKeyCommand(key_id=KEY_ID, actor_id=ACTOR)
            )

    @pytest.mark.asyncio
    async def test_unknown_key_is_not_found(self) -> None:
        with pytest.raises(EntityNotFound):
            await self._use_case(FakeUow(FakeApiClients())).execute(
                RotateApiKeyCommand(key_id=KEY_ID, actor_id=ACTOR)
            )


class TestRevoke:
    @pytest.mark.asyncio
    async def test_revocation_is_immediate_with_no_overlap(self) -> None:
        clients = FakeApiClients(client=make_client(), key=make_key())
        uow = FakeUow(clients)
        await RevokeApiKey(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds()).execute(
            RevokeApiKeyCommand(key_id=KEY_ID, actor_id=ACTOR)
        )
        assert clients.revoked == [(KEY_ID, ACTOR, NOW)]
        assert clients.expired == []

    @pytest.mark.asyncio
    async def test_revoking_twice_does_not_rewrite_who_did_it(self) -> None:
        earlier = datetime(2026, 1, 1, tzinfo=UTC)
        clients = FakeApiClients(client=make_client(), key=make_key(revoked_at=earlier))
        uow = FakeUow(clients)
        await RevokeApiKey(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds()).execute(
            RevokeApiKeyCommand(key_id=KEY_ID, actor_id=ACTOR)
        )
        assert clients.revoked == []
        assert uow.committed == 0


class TestStatusAndUsage:
    @pytest.mark.asyncio
    async def test_approving_a_partner_makes_it_active(self) -> None:
        clients = FakeApiClients(client=make_client(status=CLIENT_PENDING))
        uow = FakeUow(clients)
        updated = await SetApiClientStatus(
            uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds()
        ).execute(
            SetApiClientStatusCommand(client_id=CLIENT_ID, status=CLIENT_ACTIVE, actor_id=ACTOR)
        )
        assert updated.is_active

    @pytest.mark.asyncio
    async def test_an_unknown_status_is_refused(self) -> None:
        uow = FakeUow(FakeApiClients(client=make_client()))
        with pytest.raises(ValidationError):
            await SetApiClientStatus(uow=cast(Any, uow), clock=FakeClock(), ids=FakeIds()).execute(
                SetApiClientStatusCommand(client_id=CLIENT_ID, status="LIVE", actor_id=ACTOR)
            )

    @pytest.mark.asyncio
    async def test_usage_reports_remaining_quota(self) -> None:
        clients = FakeApiClients(client=make_client())
        clients.usage = 2_500
        usages = await ListApiClients(uow=cast(Any, FakeUow(clients))).execute()
        assert usages[0].used_this_month == 2_500
        assert usages[0].remaining == 7_500
        assert usages[0].percent_used == 25.0

    @pytest.mark.asyncio
    async def test_usage_never_reports_negative_remaining(self) -> None:
        # An over-quota partner is at zero remaining, not minus something.
        clients = FakeApiClients(client=make_client())
        clients.usage = 12_000
        usages = await ListApiClients(uow=cast(Any, FakeUow(clients))).execute()
        assert usages[0].remaining == 0
