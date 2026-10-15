"""Integration tests against an isolated PostgreSQL-compatible test database.

Run with CHAT_TEST_DATABASE_URL set. Never point at an existing installation.
"""

import asyncio
import io
import os
import wave
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4, UUID
from unittest.mock import AsyncMock
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from trustlens.db import models as m
from trustlens.db.unit_of_work import SqlAlchemyUnitOfWork
from trustlens.core.domain.enums import ListingStatus, AccountStatus, VerificationStatus
from trustlens.core.domain.errors import (
    EntityNotFound,
    InvalidStateError,
    PermissionDenied,
    ValidationError,
)
from trustlens.shared.crypto import EnvelopeEncryptor
from trustlens.shared.storage import LocalObjectStorage
from trustlens_api.modules.messaging.service import ChatService, editable
from trustlens_api.modules.messaging.voice import validate_voice

pytestmark = pytest.mark.asyncio(loop_scope="module")


class Clock:
    def __init__(self):
        self.value = datetime.now(UTC)

    def now(self):
        return self.value


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def engine():
    url = os.environ.get("CHAT_TEST_DATABASE_URL")
    if not url:
        pytest.skip("CHAT_TEST_DATABASE_URL is required for isolated integration tests")
    value = create_async_engine(
        url,
        pool_size=1,
        max_overflow=0,
        connect_args={"timeout": 10, "command_timeout": 15}
        if "+asyncpg" in url
        else {"connect_timeout": 10},
    )
    yield value
    try:
        await asyncio.wait_for(value.dispose(), timeout=2)
    except TimeoutError:
        pass


@pytest_asyncio.fixture(loop_scope="module")
async def chat(tmp_path, monkeypatch, engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    clock = Clock()
    uid, seller_user, seller_id, listing_id, cid, outsider = [uuid4() for _ in range(6)]
    container = SimpleNamespace(
        clock=clock,
        ids=SimpleNamespace(new=uuid4),
        settings=SimpleNamespace(storage=SimpleNamespace(storage_bucket_documents="private")),
        storage=LocalObjectStorage(tmp_path / "objects"),
        encryptor=EnvelopeEncryptor(key=b"x" * 32, key_id="chat-test"),
    )
    async with factory() as s:
        for user in [uid, seller_user, outsider]:
            s.add(
                m.User(
                    id=user,
                    email=f"{user}@example.test",
                    full_name="Chat test",
                    status=AccountStatus.ACTIVE,
                )
            )
        await s.flush()
        s.add(
            m.SellerProfile(
                id=seller_id,
                user_id=seller_user,
                handle=f"test-{seller_id}",
                display_name="Test Seller",
                account_opened_at=clock.now(),
                identity_status=VerificationStatus.VERIFIED,
                phone_status=VerificationStatus.VERIFIED,
                email_status=VerificationStatus.VERIFIED,
            )
        )
        await s.flush()
        s.add(
            m.ListingModel(
                id=listing_id,
                seller_id=seller_id,
                title="Synthetic chat test",
                status=ListingStatus.ACTIVE,
            )
        )
        await s.flush()
        s.add(
            m.ConversationModel(
                id=cid,
                buyer_id=uid,
                seller_id=seller_id,
                listing_id=listing_id,
                created_at=clock.now(),
                last_message_at=clock.now(),
                listing_title_snapshot="Synthetic chat test",
            )
        )
        await s.commit()
    guard = AsyncMock()
    monkeypatch.setattr("trustlens_api.modules.profiles.service.require_profile", guard)
    uow = SqlAlchemyUnitOfWork(factory)
    async with uow:
        yield SimpleNamespace(
            service=ChatService(uow, container),
            uow=uow,
            c=container,
            clock=clock,
            buyer=uid,
            seller=seller_user,
            outsider=outsider,
            cid=cid,
            lid=listing_id,
            guard=guard,
        )


async def message(chat, body="Original private message", **kwargs):
    result = await chat.service.send(chat.buyer, body=body, conversation_id=chat.cid, **kwargs)
    return UUID(result["message"]["id"])


async def test_edit_retains_original_and_each_version(chat):
    mid = await message(chat)
    chat.clock.value += timedelta(seconds=20)
    await chat.service.change(mid, chat.buyer, body="First correction")
    chat.clock.value += timedelta(seconds=20)
    await chat.service.change(mid, chat.buyer, body="Second correction")
    row = await chat.uow.session.get(m.MessageModel, mid)
    assert row.body == "Original private message" and row.edited_body == "Second correction"
    versions = (
        (
            await chat.uow.session.execute(
                select(m.ChatVersionModel).where(m.ChatVersionModel.message_id == mid)
            )
        )
        .scalars()
        .all()
    )
    assert len(versions) == 2
    chat.clock.value += timedelta(seconds=20)
    with pytest.raises(PermissionDenied):
        await chat.service.change(mid, chat.buyer, delete=True)
    assert not editable(row, chat.buyer, chat.clock.now())


async def test_wrong_sender_and_outsider_denied(chat):
    mid = await message(chat)
    with pytest.raises(PermissionDenied):
        await chat.service.change(mid, chat.seller, delete=True)
    with pytest.raises(EntityNotFound):
        await chat.service.timeline(chat.cid, chat.outsider)
    with pytest.raises(EntityNotFound):
        await chat.service.audio(mid, chat.outsider)


async def test_delete_tombstone_preview_and_reply_do_not_leak(chat):
    mid = await message(chat, "Secret phone number")
    chat.clock.value += timedelta(seconds=1)
    await message(chat, "Reply", reply_to_id=mid)
    await chat.service.change(mid, chat.buyer, delete=True)
    page = await chat.service.timeline(chat.cid, chat.seller)
    assert page["items"][0]["body"] == "This message was deleted"
    assert page["items"][1]["replyTo"]["body"] == "This message was deleted"
    assert "Secret phone number" not in str(page)
    with pytest.raises(InvalidStateError):
        await message(chat, forward_id=mid)


async def test_clear_only_self_cutoff_and_undo(chat):
    mid = await message(chat)
    chat.clock.value += timedelta(seconds=1)
    result = await chat.service.clear(chat.cid, chat.buyer)
    assert not (await chat.service.timeline(chat.cid, chat.buyer))["items"]
    assert len((await chat.service.timeline(chat.cid, chat.seller))["items"]) == 1
    assert not await chat.uow.messaging._previews([chat.cid], chat.buyer)
    with pytest.raises(EntityNotFound):
        await chat.service.visible_message(mid, chat.buyer)
    await chat.service.clear(chat.cid, chat.buyer, undo=UUID(result["undoToken"]))
    assert len((await chat.service.timeline(chat.cid, chat.buyer))["items"]) == 1
    cleared = await chat.service.clear(chat.cid, chat.buyer)
    chat.clock.value += timedelta(seconds=11)
    with pytest.raises(InvalidStateError):
        await chat.service.clear(chat.cid, chat.buyer, undo=UUID(cleared["undoToken"]))
    await message(chat, "New after clear")
    page = await chat.service.timeline(chat.cid, chat.buyer)
    assert [x["body"] for x in page["items"]] == ["New after clear"]


async def test_clear_undo_token_is_user_scoped(chat):
    await message(chat)
    result = await chat.service.clear(chat.cid, chat.buyer)
    with pytest.raises(InvalidStateError):
        await chat.service.clear(chat.cid, chat.seller, undo=UUID(result["undoToken"]))


async def test_grace_status_toggle_and_exact_closure(chat):
    await chat.uow.session.execute(
        text("UPDATE listings SET status='SOLD' WHERE id=:id"), {"id": chat.lid}
    )
    await chat.uow.commit()
    state = await chat.uow.session.get(m.ChatLifecycleModel, chat.lid)
    since = state.inactive_since
    chat.clock.value = since + timedelta(hours=72) - timedelta(microseconds=1)
    await message(chat, "Just before closure")
    await chat.uow.session.execute(
        text("UPDATE listings SET status='DRAFT' WHERE id=:id"), {"id": chat.lid}
    )
    await chat.uow.commit()
    await chat.uow.session.refresh(state)
    assert state.inactive_since == since
    chat.clock.value = since + timedelta(hours=72)
    with pytest.raises(InvalidStateError):
        await message(chat, "Too late")
    assert (await chat.service.timeline(chat.cid, chat.buyer))["items"]
    result = await chat.service.report(
        chat.cid, chat.buyer, "Delivery arrived with a fault", "delivery_issue"
    )
    assert result["reportId"]
    await chat.uow.session.execute(
        text("UPDATE listings SET status='ACTIVE' WHERE id=:id"), {"id": chat.lid}
    )
    await chat.uow.commit()
    await message(chat, "Reactivated")


async def test_idempotent_retry_and_profile_gate(chat):
    cid = uuid4()
    first = await message(chat, client_id=cid)
    second = await message(chat, client_id=cid)
    assert first == second
    assert chat.guard.await_count == 2
    chat.guard.side_effect = ValidationError("Profile must be ready")
    with pytest.raises(ValidationError):
        await message(chat)


async def test_block_prevents_send(chat):
    chat.uow.session.add(
        m.BlockModel(
            id=uuid4(), blocker_id=chat.seller, blocked_id=chat.buyer, created_at=chat.clock.now()
        )
    )
    await chat.uow.commit()
    with pytest.raises(PermissionDenied):
        await message(chat)


async def test_latest_page_cursor_keeps_all_messages(chat):
    for i in range(7):
        await message(chat, f"Message {i}")
        chat.clock.value += timedelta(seconds=1)
    page = await chat.service.timeline(chat.cid, chat.buyer, limit=3)
    assert [x["body"] for x in page["items"]] == ["Message 4", "Message 5", "Message 6"]
    page2 = await chat.service.timeline(
        chat.cid, chat.buyer, limit=3, before=UUID(page["nextCursor"])
    )
    assert [x["body"] for x in page2["items"]] == ["Message 1", "Message 2", "Message 3"]


def wav(seconds=1):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * int(8000 * seconds))
    return stream.getvalue()


async def test_voice_encrypted_retained_and_played_is_separate(chat):
    raw = wav()
    result = await chat.service.send(
        chat.buyer, conversation_id=chat.cid, raw=raw, client_id=uuid4()
    )
    mid = UUID(result["message"]["id"])
    assert result["message"]["kind"] == "voice"
    row = await chat.uow.session.get(m.ChatVoiceModel, mid)
    encrypted = await chat.c.storage.get(bucket=row.bucket, object_key=row.original_key)
    assert encrypted != raw and raw not in encrypted
    assert await chat.service.audio_bytes(mid, original=True) == raw
    assert await chat.service.audio(mid, chat.seller)
    await chat.service.timeline(chat.cid, chat.seller)
    msg = await chat.uow.session.get(m.MessageModel, mid)
    assert msg.read_at and not msg.played_at
    await chat.service.played(mid, chat.buyer)
    assert not msg.played_at
    await chat.service.played(mid, chat.seller)
    assert msg.played_at
    await chat.service.change(mid, chat.buyer, delete=True)
    with pytest.raises(EntityNotFound):
        await chat.service.audio(mid, chat.seller)
    assert await chat.service.audio_bytes(mid, original=True) == raw
    assert (await chat.service.timeline(chat.cid, chat.seller))["items"][0]["voice"] is None


async def test_voice_forward_copies_with_new_encryption_context(chat):
    result = await chat.service.send(
        chat.buyer, conversation_id=chat.cid, raw=wav(), client_id=uuid4()
    )
    mid = UUID(result["message"]["id"])
    forwarded = await message(chat, forward_id=mid)
    assert await chat.service.audio_bytes(forwarded, original=True) == wav()
    await chat.service.change(mid, chat.buyer, delete=True)
    assert await chat.service.audio(forwarded, chat.seller)


async def test_invalid_and_too_long_audio_rejected():
    with pytest.raises(ValidationError):
        await validate_voice(b"<html>not audio</html>")
    with pytest.raises(ValidationError):
        await validate_voice(wav(301))
    with pytest.raises(ValidationError):
        await validate_voice(b"RIFF" + b"x" * (12 * 1024 * 1024))


async def test_database_blocks_delete_and_original_overwrite(chat):
    mid = await message(chat)
    for sql in [
        "DELETE FROM messages WHERE id=:id",
        "UPDATE messages SET body='tampered' WHERE id=:id",
    ]:
        # Catch the expected trigger exception inside PostgreSQL itself; this
        # also works with embedded PostgreSQL wire-protocol test adapters.
        command = sql.replace(":id", f"'{mid}'::uuid")
        await chat.uow.session.execute(
            text(
                "DO $$ DECLARE rejected boolean := false; BEGIN BEGIN "
                + command
                + "; EXCEPTION WHEN raise_exception THEN rejected := true; END; IF NOT rejected THEN RAISE EXCEPTION 'Retention did not reject mutation'; END IF; END $$"
            )
        )
    row = await chat.uow.session.get(m.MessageModel, mid)
    assert row.body == "Original private message"


async def test_versions_and_audit_are_immutable(chat):
    mid = await message(chat)
    await chat.service.change(mid, chat.buyer, body="Changed")
    for sql in [
        "DELETE FROM chat_versions WHERE message_id=:id",
        "UPDATE chat_versions SET body='tampered' WHERE message_id=:id",
        "DELETE FROM chat_audit WHERE message_id=:id",
    ]:
        # Catch the expected trigger exception inside PostgreSQL itself; this
        # also works with embedded PostgreSQL wire-protocol test adapters.
        command = sql.replace(":id", f"'{mid}'::uuid")
        await chat.uow.session.execute(
            text(
                "DO $$ DECLARE rejected boolean := false; BEGIN BEGIN "
                + command
                + "; EXCEPTION WHEN raise_exception THEN rejected := true; END; IF NOT rejected THEN RAISE EXCEPTION 'Retention did not reject mutation'; END IF; END $$"
            )
        )


async def test_http_permission_boundaries_and_support_redaction(chat):
    import httpx
    from fastapi import FastAPI
    from trustlens_api.api.v1.routers.messaging import router
    from trustlens_api.api.deps import (
        get_uow,
        get_container,
        get_current_actor,
        get_request_meta,
        RequestMeta,
    )
    from trustlens_api.exceptions.handlers import register_exception_handlers
    from trustlens.core.domain.entities import AuthenticatedActor

    mid = await message(chat, "Retained sensitive test text")
    case = await chat.service.report(
        chat.cid, chat.buyer, "Please review this private information", "sensitive_information", mid
    )
    actor = AuthenticatedActor(user_id=chat.buyer)
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    app.dependency_overrides[get_uow] = lambda: chat.uow
    app.dependency_overrides[get_container] = lambda: chat.c
    app.dependency_overrides[get_current_actor] = lambda: actor
    app.dependency_overrides[get_request_meta] = lambda: RequestMeta(None, None, None, None)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        path = "/admin/chat-cases/" + case["reportId"]
        assert (await client.get(path)).status_code == 403
        actor = AuthenticatedActor(user_id=chat.outsider)
        assert (await client.get(f"/me/conversations/{chat.cid}/timeline")).status_code == 404
        actor = AuthenticatedActor(
            user_id=chat.outsider, permissions=frozenset(["moderation:read"])
        )
        result = await client.get(path)
        assert result.status_code == 200
        assert result.json()["data"]["messages"][0]["original"] == "Retained sensitive test text"
        assert (
            await client.post(
                path + "/hide",
                json={"messageId": str(mid), "reason": "Verified personal information exposure"},
            )
        ).status_code == 403
        actor = AuthenticatedActor(
            user_id=chat.outsider, permissions=frozenset(["moderation:read", "moderation:resolve"])
        )
        assert (
            await client.post(
                path + "/hide",
                json={"messageId": str(mid), "reason": "Verified personal information exposure"},
            )
        ).status_code == 200
        actor = AuthenticatedActor(user_id=chat.buyer)
        result = await client.get(f"/me/conversations/{chat.cid}/timeline")
        assert "Retained sensitive test text" not in result.text
        assert result.json()["data"]["items"][0]["body"] == "Message hidden by support"


async def test_encrypted_backup_stream_roundtrip_and_truncation(monkeypatch):
    import sys
    from trustlens_api.modules.messaging.archive import stream_backup

    data = b"Synthetic database dump\x00" * 60000
    settings = SimpleNamespace(
        security=SimpleNamespace(aes_key=lambda: b"k" * 32, encryption_key_id="backup-test")
    )

    def run(mode, raw):
        source = io.TextIOWrapper(io.BytesIO(raw), encoding="utf8")
        target = io.BytesIO()
        out = io.TextIOWrapper(target, encoding="utf8")
        with monkeypatch.context() as patch:
            patch.setattr(sys, "stdin", source)
            patch.setattr(sys, "stdout", out)
            stream_backup(mode, settings)
            out.flush()
            result = target.getvalue()
        out.detach()
        return result

    encrypted = run("encrypt", data)
    assert data[:100] not in encrypted
    assert run("decrypt", encrypted) == data
    with pytest.raises(ValueError):
        run("decrypt", b"\n".join(encrypted.splitlines()[:-1]) + b"\n")
