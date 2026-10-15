"""Real PostgreSQL integration coverage; media API has a deterministic test double."""

from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import AsyncMock
import base64
import jwt
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import text
from trustlens.db import models as m
from trustlens.core.domain.errors import (
    EntityNotFound,
    InvalidStateError,
    PermissionDenied,
    RateLimitExceeded,
    ValidationError,
)
from trustlens_api.modules.calling.service import CallService
from trustlens_api.modules.calling.media import CallMedia
from trustlens_api.modules.calling.push import valid_subscription, save_subscription, disable_subscription
from test_chat_retention_voice import engine, chat  # noqa: F401

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(loop_scope="module")
async def calls(chat):  # noqa: F811 - imported shared pytest fixture
    chat.c.settings.calls = SimpleNamespace(
        calls_enabled=True,
        calls_livekit_url="ws://127.0.0.1:7880",
        calls_livekit_internal_url="http://127.0.0.1:7880",
        calls_livekit_api_key="testkey",
        calls_livekit_api_secret=SecretStr("s" * 40),
        calls_vapid_public_key="configured",
    )
    media = CallMedia(chat.c.settings, chat.clock)
    media.create = AsyncMock()
    media.delete = AsyncMock()
    chat.c.call_media = media
    chat.calls = CallService(chat.uow, chat.c)
    chat.a, chat.b = uuid4(), uuid4()
    yield chat


async def start(c):
    row = await c.calls.start(c.buyer, c.cid, uuid4(), c.a)
    return UUID(row["id"])


async def test_accept_audio_ack_mute_end_and_retained_history(calls):
    c = calls
    id = await start(c)
    row = await c.calls.get(id, c.buyer)
    assert row.state == "calling"
    with pytest.raises(InvalidStateError):
        await c.calls.join(c.buyer, id, c.a)
    await c.calls.act(c.seller, id, c.b, "ring")
    assert (await c.calls.active(c.buyer, c.a))["state"] == "ringing"
    await c.calls.act(c.seller, id, c.b, "accept")
    access = await c.calls.join(c.buyer, id, c.a)
    claims = jwt.decode(access["token"], "s" * 40, algorithms=["HS256"])
    assert claims["sub"] == f"{c.buyer}:{c.a}"
    assert claims["video"]["canPublishSources"] == ["microphone"]
    assert claims["video"]["canPublishData"] is False
    assert claims["exp"] - claims["nbf"] == 65
    assert (await c.calls.act(c.buyer, id, c.a, "sync", connected=True))["state"] == "connecting"
    assert (await c.calls.act(c.seller, id, c.b, "sync", connected=True))["state"] == "active"
    await c.calls.act(c.seller, id, c.b, "sync", muted=True, health={"receivedBytes": 2345})
    assert (await c.calls.active(c.buyer, c.a))["remoteMuted"]
    assert (await c.calls.act(c.buyer, id, c.a, "end"))["reason"] == "ended"
    assert await c.calls.active(c.seller, c.b) is None
    assert (await c.calls.history(c.seller, c.cid))[0]["connectedAt"]
    with pytest.raises(InvalidStateError):
        await c.calls.join(c.buyer, id, c.a)
    for sql in [
        f"DELETE FROM chat_calls WHERE id='{id}'",
        f"UPDATE chat_calls SET reason='fake' WHERE id='{id}'",
    ]:
        await c.uow.session.execute(
            text(
                "DO $$ DECLARE rejected boolean := false; BEGIN BEGIN "
                + sql
                + "; EXCEPTION WHEN raise_exception THEN rejected := true; END; IF NOT rejected THEN RAISE EXCEPTION 'Retention failed'; END IF; END $$"
            )
        )
    await c.uow.commit()


async def test_outsider_other_tab_and_busy(calls):
    c = calls
    id = await start(c)
    with pytest.raises(EntityNotFound):
        await c.calls.get(id, c.outsider)
    with pytest.raises(EntityNotFound):
        await c.calls.history(c.outsider, c.cid)
    with pytest.raises(PermissionDenied):
        await c.calls.act(c.buyer, id, uuid4(), "end")
    with pytest.raises(PermissionDenied):
        await c.calls.act(c.buyer, id, c.a, "ring")
    with pytest.raises(InvalidStateError):
        await start(c)
    await c.calls.act(c.seller, id, c.b, "accept")
    with pytest.raises(PermissionDenied):
        await c.calls.act(c.seller, id, uuid4(), "accept")
    with pytest.raises(PermissionDenied):
        await c.calls.join(c.seller, id, uuid4())
    await c.calls.act(c.seller, id, c.b, "end")


async def test_duplicate_id_does_not_create_extra_room(calls):
    c = calls
    id = await start(c)
    row = await c.calls.start(c.buyer, c.cid, id, c.a)
    assert row["id"] == str(id)
    assert c.c.call_media.create.await_count == 1
    await c.calls.act(c.buyer, id, c.a, "end")


async def test_unacknowledged_call_stays_calling_and_expires(calls):
    c = calls
    await start(c)
    c.clock.value += timedelta(seconds=44)
    assert (await c.calls.active(c.buyer, c.a))["state"] == "calling"
    c.clock.value += timedelta(seconds=1)
    assert await c.calls.active(c.seller, c.b) is None
    assert (await c.calls.history(c.seller, c.cid))[0]["reason"] == "missed"


async def test_lost_owner_lease_expires(calls):
    c = calls
    id = await start(c)
    await c.calls.act(c.seller, id, c.b, "accept")
    await c.calls.act(c.buyer, id, c.a, "sync", connected=True)
    await c.calls.act(c.seller, id, c.b, "sync", connected=True)
    c.clock.value += timedelta(seconds=46)
    assert (await c.calls.act(c.seller, id, c.b, "sync"))["reason"] == "connection_lost"


async def test_block_and_exact_72_hour_gate(calls):
    c = calls
    id = await start(c)
    c.uow.session.add(
        m.BlockModel(id=uuid4(), blocker_id=c.seller, blocked_id=c.buyer, created_at=c.clock.now())
    )
    await c.uow.commit()
    assert (await c.calls.act(c.buyer, id, c.a, "sync"))["reason"] == "chat_unavailable"
    with pytest.raises(InvalidStateError):
        await start(c)


async def test_sold_grace_and_call_start_rate_limit(calls):
    c = calls
    await c.uow.session.execute(
        text("UPDATE listings SET status='SOLD' WHERE id=:id"), {"id": c.lid}
    )
    await c.uow.commit()
    life = await c.uow.session.get(m.ChatLifecycleModel, c.lid)
    c.clock.value = life.inactive_since + timedelta(hours=72, seconds=-1)
    for _ in range(5):
        id = await start(c)
        await c.calls.act(c.buyer, id, c.a, "end")
    with pytest.raises(RateLimitExceeded):
        await start(c)
    c.clock.value += timedelta(seconds=1)
    with pytest.raises(InvalidStateError):
        await start(c)


async def test_media_failure_creates_no_invitation(calls):
    c = calls
    c.c.call_media.create.side_effect = RuntimeError("Synthetic media outage")
    with pytest.raises(InvalidStateError):
        await start(c)
    assert not await c.calls.history(c.buyer, c.cid)


async def test_clear_history_only_hides_own_calls(calls):
    c = calls
    id = await start(c)
    await c.calls.act(c.buyer, id, c.a, "end")
    c.clock.value += timedelta(seconds=1)
    await c.service.clear(c.cid, c.buyer)
    assert not await c.calls.history(c.buyer, c.cid)
    assert len(await c.calls.history(c.seller, c.cid)) == 1


async def test_push_validation_encryption_and_owner(calls):
    c = calls
    b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    value = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/" + str(uuid4()),
        "keys": {"p256dh": b64(b"\x04" + b"a" * 64), "auth": b64(b"a" * 16)},
    }
    for endpoint in [
        "http://127.0.0.1/",
        "https://fcm.googleapis.com:evil/x",
        "https://fcm.googleapis.com.evil.test/x",
        "https://user:pass@fcm.googleapis.com/x",
    ]:
        with pytest.raises(ValidationError):
            valid_subscription({**value, "endpoint": endpoint})
    saved = await save_subscription(c.uow, c.c, c.buyer, value)
    row = await c.uow.session.get(m.ChatPushSubscriptionModel, UUID(saved["id"]))
    assert value["endpoint"] not in row.encrypted_subscription
    assert (await save_subscription(c.uow, c.c, c.buyer, value))["id"] == saved["id"]
    with pytest.raises(PermissionDenied):
        await save_subscription(c.uow, c.c, c.seller, value)
    with pytest.raises(EntityNotFound):
        await disable_subscription(c.uow, c.seller, row.id)
    await disable_subscription(c.uow, c.buyer, row.id)
    assert row.enabled is False
