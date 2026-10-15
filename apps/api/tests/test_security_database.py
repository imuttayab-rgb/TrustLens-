"""Real repository checks on an isolated PostgreSQL-compatible database.

Use CHAT_TEST_DATABASE_URL on a disposable database only. Embedded PostgreSQL
validates SQL/state transitions; native multi-connection race tests are separate.
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from trustlens.db import models as m
from trustlens.db.repositories.accounts import (
    SqlRefreshTokenRepository,
    SqlVerificationTokenRepository,
    SqlOtpRepository,
    SqlMfaRecoveryCodeRepository,
)
from trustlens.db.repositories.verification import SqlFileRepository
from trustlens.core.domain.enums import AccountStatus, TokenPurpose, OtpPurpose, FilePurpose
from trustlens.core.domain.errors import TokenUsed, RateLimitExceeded

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def sessions():
    url = os.environ.get("CHAT_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires an isolated CHAT_TEST_DATABASE_URL")
    engine = create_async_engine(url, pool_size=1, max_overflow=0)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await asyncio.wait_for(engine.dispose(), timeout=5)


@pytest_asyncio.fixture(loop_scope="module")
async def account(sessions):
    uid = uuid4()
    async with sessions() as session:
        session.add(
            m.User(
                id=uid,
                email=f"{uid}@example.test",
                full_name="Security test",
                status=AccountStatus.ACTIVE,
            )
        )
        await session.commit()
    return uid


async def test_session_rotation_revocation_is_scoped_to_family(sessions, account):
    now = datetime.now(UTC)
    family, second = uuid4(), uuid4()
    parent, child = uuid4(), uuid4()
    async with sessions() as s:
        s.add(
            m.RefreshToken(
                id=parent,
                user_id=account,
                family_id=family,
                token_hash=uuid4().bytes,
                expires_at=now + timedelta(days=30),
                created_at=now,
                revoked_at=now,
                revoked_reason="ROTATED",
            )
        )
        await s.flush()
        s.add_all(
            [
                m.RefreshToken(
                    id=child,
                    user_id=account,
                    family_id=family,
                    parent_id=parent,
                    token_hash=uuid4().bytes,
                    expires_at=now + timedelta(days=30),
                    created_at=now,
                ),
                m.RefreshToken(
                    id=uuid4(),
                    user_id=account,
                    family_id=second,
                    token_hash=uuid4().bytes,
                    expires_at=now + timedelta(days=30),
                    created_at=now,
                ),
            ]
        )
        await s.commit()
    async with sessions() as s:
        repo = SqlRefreshTokenRepository(s)
        assert await repo.family_is_active(account, family, at=now, idle_days=7)
        assert not await repo.family_is_active(uuid4(), family, at=now, idle_days=7)
        await repo.revoke_family(family, at=now, reason="LOGOUT")
        await s.commit()
    async with sessions() as s:
        repo = SqlRefreshTokenRepository(s)
        assert not await repo.family_is_active(account, family, at=now, idle_days=7)
        assert await repo.family_is_active(account, second, at=now, idle_days=7)
        await repo.revoke_all_for_user(account, at=now, reason="PASSWORD_RESET")
        await s.commit()
    async with sessions() as s:
        assert not await SqlRefreshTokenRepository(s).family_is_active(
            account, second, at=now, idle_days=7
        )


@pytest.mark.parametrize("kind", ["reset", "otp", "recovery"])
async def test_atomic_consumption_refuses_replay(sessions, account, kind):
    now = datetime.now(UTC)
    tid = uuid4()
    async with sessions() as s:
        if kind == "reset":
            row = m.VerificationTokenModel(
                id=tid,
                user_id=account,
                purpose=TokenPurpose.PASSWORD_RESET,
                token_hash=uuid4().bytes,
                target="synthetic@example.test",
                expires_at=now + timedelta(minutes=15),
            )
        elif kind == "otp":
            row = m.OtpCodeModel(
                id=tid,
                user_id=account,
                purpose=OtpPurpose.PHONE_VERIFICATION,
                code_hash=uuid4().bytes,
                expires_at=now + timedelta(minutes=5),
            )
        else:
            row = m.MfaRecoveryCodeModel(id=tid, user_id=account, code_hash=uuid4().bytes)
        s.add(row)
        await s.commit()
    factory = {
        "reset": SqlVerificationTokenRepository,
        "otp": SqlOtpRepository,
        "recovery": SqlMfaRecoveryCodeRepository,
    }[kind]
    async with sessions() as s:
        await factory(s).consume(tid, at=now)
        await s.commit()
    async with sessions() as s:
        with pytest.raises(TokenUsed):
            await factory(s).consume(tid, at=now)
        await s.rollback()


async def test_expired_token_cannot_be_consumed_directly(sessions, account):
    now = datetime.now(UTC)
    tid = uuid4()
    async with sessions() as s:
        s.add(
            m.VerificationTokenModel(
                id=tid,
                user_id=account,
                purpose=TokenPurpose.PASSWORD_RESET,
                token_hash=uuid4().bytes,
                target="synthetic@example.test",
                expires_at=now - timedelta(seconds=1),
            )
        )
        await s.commit()
    async with sessions() as s:
        with pytest.raises(TokenUsed):
            await SqlVerificationTokenRepository(s).consume(tid, at=now)


async def test_upload_budget_counts_pending_intents_and_is_account_scoped(sessions, account):
    async with sessions() as s:
        repo = SqlFileRepository(s)
        await repo.check_upload_budget(account, requested_bytes=90, max_bytes=100, max_files=2)
        s.add(
            m.StoredFileModel(
                id=uuid4(),
                owner_user_id=account,
                purpose=FilePurpose.LISTING_IMAGE,
                bucket="synthetic",
                object_key=str(uuid4()),
                mime_type="image/jpeg",
                size_bytes=90,
                sha256=b"",
            )
        )
        await s.commit()
    async with sessions() as s:
        repo = SqlFileRepository(s)
        await repo.check_upload_budget(account, requested_bytes=10, max_bytes=100, max_files=2)
        with pytest.raises(RateLimitExceeded):
            await repo.check_upload_budget(account, requested_bytes=11, max_bytes=100, max_files=2)
        with pytest.raises(RateLimitExceeded):
            await repo.check_upload_budget(account, requested_bytes=1, max_bytes=100, max_files=1)
