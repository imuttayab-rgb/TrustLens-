"""Clock and id generation adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import uuid_utils


class SystemClock:
    """Always UTC. A naive datetime anywhere in this system is a bug - the
    DTZ ruff rules exist to stop one being introduced."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class Uuid7Generator:
    """Time-ordered UUIDs.

    UUIDv4 primary keys scatter B-tree inserts across the whole index, which
    hurts write throughput and cache locality on the high-volume tables
    (access_events, api_request_logs, audit_logs). UUIDv7 keeps insert
    locality like a bigserial while staying globally unique and
    non-enumerable in URLs.
    """

    def new(self) -> UUID:
        return UUID(str(uuid_utils.uuid7()))


__all__ = ["SystemClock", "Uuid7Generator"]
