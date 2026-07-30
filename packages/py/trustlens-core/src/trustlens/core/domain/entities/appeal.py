"""Appeals, moderation queue and API-client entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from trustlens.core.domain.enums import (
    ApiKeyStatus,
    AppealStatus,
    ReviewCaseType,
    ReviewStatus,
    UserRole,
)


@dataclass(frozen=True, slots=True)
class AppealMessage:
    id: UUID
    appeal_id: UUID
    sender_id: UUID
    sender_role: UserRole
    body: str
    created_at: datetime
    attachments: tuple[UUID, ...] = ()
    #: Reviewer notes the seller must not see. Keeps internal discussion out of
    #: the seller's view without needing a second table.
    is_internal: bool = False


@dataclass(frozen=True, slots=True)
class Appeal:
    """A challenge to one specific score computation.

    It references `trust_score_id`, not just the seller: appealing "my score"
    is meaningless once the score changes, whereas appealing *that
    computation* is precise, reviewable, and reproducible.
    """

    id: UUID
    seller_id: UUID
    trust_score_id: UUID
    submitted_by: UUID
    reason_category: str
    reason: str
    status: AppealStatus
    submitted_at: datetime
    created_at: datetime
    assigned_to: UUID | None = None
    assigned_at: datetime | None = None
    resolution_note: str | None = None
    decision: str | None = None
    resulting_score_id: UUID | None = None
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None
    messages: tuple[AppealMessage, ...] = ()
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    version: int = 1

    @property
    def is_open(self) -> bool:
        return self.status.is_open


@dataclass(frozen=True, slots=True)
class ReviewCase:
    """An item in the admin work queue.

    Separate from `Appeal` because most review work is *system*-initiated (a
    device cluster tripped a rule), not seller-initiated. Merging them would
    force every automatic flag to masquerade as an appeal.
    """

    id: UUID
    seller_id: UUID
    case_type: ReviewCaseType
    status: ReviewStatus
    created_at: datetime
    priority: int = 5
    trigger_reason: str | None = None
    related_entity_type: str | None = None
    related_entity_id: UUID | None = None
    assigned_to: UUID | None = None
    assigned_at: datetime | None = None
    decision: str | None = None
    decision_note: str | None = None
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None


@dataclass(frozen=True, slots=True)
class ApiClient:
    """A partner marketplace consuming the public Trust Score API."""

    id: UUID
    name: str
    slug: str
    contact_email: str
    status: str
    created_at: datetime
    marketplace_id: UUID | None = None
    contact_name: str | None = None
    rate_limit_tier: str = "free"
    monthly_quota: int = 10_000
    allowed_origins: tuple[str, ...] = ()
    allowed_ips: tuple[str, ...] = ()
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE" and self.deleted_at is None


@dataclass(frozen=True, slots=True)
class ApiKey:
    """A hashed API key.

    `key_prefix` is stored in the clear so lookup is an indexed equality match;
    the secret half is argon2-hashed and compared in constant time. Without a
    prefix you would have to hash every candidate key to find a match.
    """

    id: UUID
    api_client_id: UUID
    name: str
    key_prefix: str
    key_hash: bytes
    status: ApiKeyStatus
    created_at: datetime
    scopes: frozenset[str] = frozenset()
    last_used_at: datetime | None = None
    last_used_ip: str | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def is_usable_at(self, now: datetime) -> bool:
        if self.status != ApiKeyStatus.ACTIVE or self.revoked_at is not None:
            return False
        return self.expires_at is None or now < self.expires_at

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


@dataclass(frozen=True, slots=True)
class JobRun:
    """Job state mirrored into Postgres.

    ARQ keeps its own state in Redis, but Redis can evict; a seller polling
    "is my verification done?" and an admin looking at dead letters both need
    durable answers.
    """

    id: UUID
    job_name: str
    status: str
    queued_at: datetime
    job_key: str | None = None
    related_entity_type: str | None = None
    related_entity_id: UUID | None = None
    attempt: int = 0
    max_attempts: int = 3
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error_message: str | None = None
    error_type: str | None = None
    request_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None


@dataclass(frozen=True, slots=True)
class AuditLogEntry:
    id: UUID
    action: str
    entity_type: str
    occurred_at: datetime
    actor_id: UUID | None = None
    actor_type: str = "USER"
    entity_id: UUID | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None


__all__ = [
    "ApiClient",
    "ApiKey",
    "Appeal",
    "AppealMessage",
    "AuditLogEntry",
    "JobRun",
    "ReviewCase",
]
