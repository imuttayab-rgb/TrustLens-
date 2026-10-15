"""Exercise worker decisions with synthetic adapters; this is not an accuracy benchmark."""

from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from trustlens.core.domain.ports.ai import FaceMatchResult
from trustlens_worker.jobs import profiles


class Uow:
    def __init__(self, session):
        self.session = session
        self.commit = AsyncMock()
        self.flush = AsyncMock()
        self.sellers = NS(get=AsyncMock(return_value=NS()))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def result(value=None):
    r = Mock()
    r.scalar_one_or_none.return_value = value
    return r


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,expected",
    [
        ("real", "APPROVED"),
        ("fake", "ERROR"),
        ("group", "RETRY"),
        ("identity_changed", "RETRY"),
        ("unavailable", "ERROR"),
        ("superseded", "SUPERSEDED"),
    ],
)
async def test_photo_worker_never_approves_without_current_real_evidence(
    monkeypatch, mode, expected
):
    uid, pid, iid = uuid4(), uuid4(), uuid4()
    prior = uuid4()
    now = datetime.now(UTC)
    photo = NS(
        id=pid,
        user_id=uid,
        identity_id=iid,
        status="QUEUED",
        deleted_at=None,
        bucket="private",
        object_key="photo",
        sha256=sha256(b"photo").digest(),
        reason=None,
    )
    p = NS(name_status="VERIFIED", name_identity_id=iid, approved_photo_id=prior, version=1)
    seller = NS(id=uuid4(), deleted_at=None)
    identity = NS(id=iid)
    selfie = NS(file_id=uuid4())
    session = NS(
        execute=AsyncMock(
            side_effect=[
                result(),
                result(photo),
                result(p),
                result(seller),
                result(uuid4() if mode == "superseded" else pid),
            ]
        ),
        get=AsyncMock(side_effect=[NS(deleted_at=None), NS(bucket="private", object_key="selfie")]),
        refresh=AsyncMock(),
    )
    uow = Uow(session)
    face = (
        NS()
        if mode == "fake"
        else NS(
            compare_profile=AsyncMock(
                return_value=FaceMatchResult(
                    0.95,
                    0.05,
                    0.8,
                    "insightface",
                    "test",
                    raw={
                        "profile_face_count": 2 if mode == "group" else 1,
                        "reference_face_count": 1,
                    },
                )
            )
        )
    )
    if mode == "unavailable":
        face.compare_profile.side_effect = RuntimeError("offline")
    identities = [
        (identity, None, selfie),
        (NS(id=uuid4()) if mode == "identity_changed" else identity, None, selfie),
    ]
    monkeypatch.setattr(profiles, "current_identity", AsyncMock(side_effect=identities))
    publish = AsyncMock()
    monkeypatch.setattr(profiles, "sync_listing_publication", publish)
    ctx = {
        "uow": lambda: uow,
        "clock": NS(now=lambda: now),
        "face": face,
        "storage": NS(get=AsyncMock(side_effect=[b"photo", b"reference"])),
    }
    out = await profiles.check_photo(ctx, photo_id=str(pid))
    assert out["status"] == expected
    assert p.approved_photo_id == (pid if expected == "APPROVED" else prior)
    assert publish.await_count == (1 if expected == "APPROVED" else 0)
