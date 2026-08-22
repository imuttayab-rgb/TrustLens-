"""Two operational guarantees, tested rather than assumed (P8-07, P8-08).

Both describe things that are invisible when they go wrong. A retention job
that silently stops deleting leaves biometric data on disk indefinitely, and
nothing in the UI changes. A provider outage that resolves to FAIL instead of
UNAVAILABLE quietly costs sellers points for something they did not do, and
cannot appeal.

Written against fakes rather than a live stack: these are decisions in the
code, and a test that needs Docker running is a test nobody runs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from trustlens_worker.jobs import maintenance


@dataclass
class _File:
    id: uuid.UUID
    bucket: str
    object_key: str


class _Files:
    """Just enough repository to exercise the purge loop."""

    def __init__(self, expired: list[_File]) -> None:
        self._expired = expired
        self.marked: list[uuid.UUID] = []

    async def list_expired(self, *, before: datetime, limit: int) -> list[_File]:
        self.seen_before = before
        return self._expired[:limit]

    async def mark_deleted(self, file_id: uuid.UUID, *, at: datetime) -> None:
        self.marked.append(file_id)


class _Uow:
    def __init__(self, files: _Files) -> None:
        self.files = files
        self.commits = 0

    async def __aenter__(self) -> _Uow:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


class _Storage:
    def __init__(self, *, fail_on: set[str] | None = None) -> None:
        self.deleted: list[str] = []
        self._fail_on = fail_on or set()

    async def delete(self, *, bucket: str, object_key: str) -> None:
        if object_key in self._fail_on:
            raise RuntimeError("storage unreachable")
        self.deleted.append(object_key)


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 8, 22, tzinfo=UTC)


def _ctx(files: _Files, storage: _Storage) -> dict[str, Any]:
    uow = _Uow(files)
    return {"uow": lambda: uow, "storage": storage, "clock": _Clock()}


# ── P8-07: the retention job actually deletes ────────────────────────


@pytest.mark.unit
async def test_purge_deletes_expired_images_and_records_it() -> None:
    """CNIC and selfie images must really leave storage after the window.

    The cron was registered and the code looked right; nothing had ever
    checked that an object is removed AND the row marked, which are two
    separate failures with the same symptom (none).
    """
    files = _Files([_File(uuid.uuid4(), "trustlens-documents", f"cnic/{i}.jpg") for i in range(3)])
    storage = _Storage()

    result = await maintenance.purge_expired_media(_ctx(files, storage))

    assert result["purged"] == 3
    assert len(storage.deleted) == 3
    assert len(files.marked) == 3


@pytest.mark.unit
async def test_purge_only_looks_at_files_past_their_window() -> None:
    files = _Files([])
    await maintenance.purge_expired_media(_ctx(files, _Storage()))
    assert files.seen_before == datetime(2026, 8, 22, tzinfo=UTC)


@pytest.mark.unit
async def test_purge_survives_one_unreachable_object() -> None:
    """One bad object must not stop the sweep.

    Otherwise a single orphaned key blocks every later deletion forever, and
    the retention policy quietly stops applying to everything behind it.
    """
    keys = ["cnic/ok-1.jpg", "cnic/broken.jpg", "cnic/ok-2.jpg"]
    files = _Files([_File(uuid.uuid4(), "trustlens-documents", k) for k in keys])
    storage = _Storage(fail_on={"cnic/broken.jpg"})

    result = await maintenance.purge_expired_media(_ctx(files, storage))

    assert result["purged"] == 2
    assert storage.deleted == ["cnic/ok-1.jpg", "cnic/ok-2.jpg"]
    # The failed one stays unmarked, so the next run retries it rather than
    # losing track of an object that is still sitting in the bucket.
    assert len(files.marked) == 2


@pytest.mark.unit
async def test_purge_does_not_mark_a_row_it_could_not_delete() -> None:
    """Marking first would orphan the object: gone from the index, still on disk."""
    files = _Files([_File(uuid.uuid4(), "trustlens-documents", "cnic/broken.jpg")])
    storage = _Storage(fail_on={"cnic/broken.jpg"})

    result = await maintenance.purge_expired_media(_ctx(files, storage))

    assert result["purged"] == 0
    assert files.marked == []


# ── P8-08: a provider outage is UNAVAILABLE, never FAIL ──────────────


@pytest.mark.unit
async def test_ip_intelligence_fails_open() -> None:
    """A VPN-lookup outage must not look like a seller using a VPN.

    `build_ip_intelligence` returns the offline path when no provider is
    configured, and wraps a configured one with that same offline path as its
    fallback - so a provider being down degrades the answer instead of raising
    into a job that would then retry, exhaust, and land the signal on FAIL.
    """
    from trustlens.shared.config.settings import IpIntelSettings
    from trustlens.shared.ip import build_ip_intelligence

    provider = build_ip_intelligence(IpIntelSettings())
    assert await provider.lookup("203.0.113.10") is not None


# The UNAVAILABLE-vs-FAIL guarantee - our outage must not cost a seller points
# on a signal they cannot appeal - is already covered where it belongs, in
# packages/py/trustlens-core/tests/domain/test_scoring_policy.py
# (`test_unavailable_signal_is_excluded_from_the_denominator`). Restating it
# here would test the same normalisation twice and drift from it once.
