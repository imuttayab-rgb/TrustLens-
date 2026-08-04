"""Infrastructure ports: time, ids, storage, cache, queue, notifications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import TYPE_CHECKING, Any, Protocol, Self, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from trustlens.core.domain.entities import IpReputation
    from trustlens.core.domain.enums import LineType
    from trustlens.core.domain.ports.repositories import (
        ApiClientRepository,
        AppealRepository,
        AuditLogRepository,
        ConsentRepository,
        DeviceRepository,
        EmailAddressRepository,
        FileRepository,
        IdentityRepository,
        JobRunRepository,
        ListingRepository,
        NotificationRepository,
        OtpRepository,
        PhoneNumberRepository,
        RefreshTokenRepository,
        ReviewCaseRepository,
        ScoringModelRepository,
        SellerRepository,
        TrustScoreRepository,
        UserRepository,
        VerificationTokenRepository,
    )


@runtime_checkable
class Clock(Protocol):
    """Injected time.

    Looks like over-engineering until you test "is this score older than 30
    days?" - with a real clock that test is slow or flaky; with a frozen clock
    it is one line. `datetime.now()` inside trustlens.core is a lint error.
    """

    def now(self) -> datetime: ...


@runtime_checkable
class IdGenerator(Protocol):
    """Injected identifiers.

    Production uses UUIDv7 (time-ordered, so index inserts stay local on the
    high-volume tables); tests use a deterministic sequence so snapshot
    assertions stay readable.
    """

    def new(self) -> UUID: ...


@runtime_checkable
class UnitOfWork(Protocol):
    """Transaction boundary, owned by the use case.

    Repositories are exposed as attributes so a use case touching three
    aggregates still commits once. Entering the context opens a transaction;
    leaving without `commit()` rolls back.
    """

    users: UserRepository
    sellers: SellerRepository
    identities: IdentityRepository
    phone_numbers: PhoneNumberRepository
    email_addresses: EmailAddressRepository
    devices: DeviceRepository
    listings: ListingRepository
    trust_scores: TrustScoreRepository
    scoring_models: ScoringModelRepository
    appeals: AppealRepository
    review_cases: ReviewCaseRepository
    api_clients: ApiClientRepository
    refresh_tokens: RefreshTokenRepository
    verification_tokens: VerificationTokenRepository
    otps: OtpRepository
    consents: ConsentRepository
    files: FileRepository
    notifications: NotificationRepository
    audit_logs: AuditLogRepository
    job_runs: JobRunRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def publish(self, event: Any) -> None:
        """Stage a domain event on the transactional outbox.

        Written in the SAME transaction as the state change, then relayed by a
        poller. Without this, "score updated but the webhook never fired" (or
        the reverse) is only a matter of time.
        """
        ...

    async def rollback(self) -> None: ...

    async def flush(self) -> None: ...


@runtime_checkable
class Cache(Protocol):
    """Key/value cache.

    Never a system of record: losing all of it must cost latency, never data.
    """

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None: ...

    async def delete(self, *keys: str) -> int: ...

    async def delete_pattern(self, pattern: str) -> int: ...

    async def incr(self, key: str, *, ttl_seconds: int | None = None) -> int: ...

    async def exists(self, key: str) -> bool: ...

    async def acquire_lock(self, key: str, *, ttl_seconds: int) -> bool: ...

    async def release_lock(self, key: str) -> None: ...


@runtime_checkable
class JobQueue(Protocol):
    """Background job enqueueing.

    Jobs are enqueued **by name**, never by importing the worker function.
    Importing it would drag torch and tensorflow into the API through the
    import graph and silently undo ADR-0003 - so this signature is load-bearing.
    """

    async def enqueue(
        self,
        job_name: str,
        *args: Any,
        job_id: str | None = None,
        defer_seconds: int | None = None,
        **kwargs: Any,
    ) -> str: ...

    async def status(self, job_id: str) -> str | None: ...


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    url: str
    fields: dict[str, str]
    object_key: str
    expires_at: datetime


@runtime_checkable
class ObjectStorage(Protocol):
    """Binary storage.

    Uploads are presigned so image bytes never traverse the API process -
    removing both a memory-exhaustion vector and a large chunk of latency.
    """

    async def presign_upload(
        self, *, bucket: str, object_key: str, content_type: str, max_bytes: int, ttl_seconds: int
    ) -> PresignedUpload: ...

    async def presign_download(self, *, bucket: str, object_key: str, ttl_seconds: int) -> str: ...

    async def get(self, *, bucket: str, object_key: str) -> bytes: ...

    async def put(
        self, *, bucket: str, object_key: str, data: bytes, content_type: str
    ) -> None: ...

    async def delete(self, *, bucket: str, object_key: str) -> None: ...

    async def exists(self, *, bucket: str, object_key: str) -> bool: ...

    async def head(self, *, bucket: str, object_key: str) -> dict[str, Any] | None: ...


@runtime_checkable
class EmailSender(Protocol):
    async def send(
        self,
        *,
        to: str,
        subject: str,
        template: str,
        context: dict[str, Any],
    ) -> None: ...


@runtime_checkable
class SmsSender(Protocol):
    async def send(self, *, to: str, message: str) -> None: ...


@runtime_checkable
class IpIntelligence(Protocol):
    """IP reputation lookup.

    Implementations chain: a metered HTTP provider first, an offline
    ASN/datacenter list as fallback, so the system still runs (with lower
    confidence) when the provider is unreachable or no key is configured.
    """

    async def lookup(self, ip: str) -> IpReputation: ...


@runtime_checkable
class PhoneLookup(Protocol):
    """Carrier / line-type lookup - the VOIP-detection half of the PHONE signal."""

    async def lookup(self, e164: str) -> tuple[LineType, str | None, dict[str, Any]]: ...


__all__ = [
    "Cache",
    "Clock",
    "EmailSender",
    "IdGenerator",
    "IpIntelligence",
    "JobQueue",
    "ObjectStorage",
    "PhoneLookup",
    "PresignedUpload",
    "SmsSender",
    "UnitOfWork",
]
