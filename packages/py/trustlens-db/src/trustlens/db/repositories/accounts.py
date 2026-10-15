"""Accounts repositories. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from typing import Any, cast
from uuid import UUID
from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from trustlens.core.domain import entities as ent
from trustlens.core.domain import enums as e
from trustlens.core.domain.value_objects import Email
from trustlens.core.domain.errors import TokenUsed
from trustlens.db import mappers as map_
from trustlens.db import models as m
from .common import _alive


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    def _with_roles(self, stmt: Select[Any]) -> Select[Any]:
        return stmt.options(
            selectinload(m.User.roles)
            .selectinload(m.UserRoleLink.role)
            .selectinload(m.Role.permissions)
            .selectinload(m.RolePermission.permission)
        )

    async def get(self, user_id: UUID) -> ent.User | None:
        stmt = self._with_roles(_alive(select(m.User), m.User).where(m.User.id == user_id))
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_user(row) if row else None

    async def get_by_email(self, email: Email) -> ent.User | None:
        stmt = self._with_roles(_alive(select(m.User), m.User).where(m.User.email == email.value))
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_user(row) if row else None

    async def get_password_hash(self, user_id: UUID) -> str | None:
        return (
            await self._s.execute(select(m.User.password_hash).where(m.User.id == user_id))
        ).scalar_one_or_none()

    async def create(self, *, user: ent.User, password_hash: str | None) -> ent.User:
        row = m.User(
            id=user.id,
            email=user.email.value,
            full_name=user.full_name,
            status=user.status,
            primary_role=user.primary_role,
            password_hash=password_hash,
            created_at=user.created_at,
            updated_at=user.created_at,
        )
        self._s.add(row)
        await self._s.flush()
        for role_key in user.roles or {user.primary_role}:
            await self.assign_role(user.id, role_key.value, granted_by=None)
        return user

    async def update(self, user: ent.User) -> ent.User:
        await self._s.execute(
            update(m.User)
            .where(m.User.id == user.id)
            .values(
                full_name=user.full_name,
                status=user.status,
                primary_role=user.primary_role,
                mfa_enabled=user.mfa_enabled,
                version=m.User.version + 1,
            )
        )
        return user

    async def session_allowed(self, user_id: UUID) -> bool:
        return (
            await self._s.execute(
                select(m.User.id).where(
                    m.User.id == user_id,
                    m.User.deleted_at.is_(None),
                    m.User.status.in_([e.AccountStatus.ACTIVE, e.AccountStatus.PENDING]),
                )
            )
        ).scalar_one_or_none() is not None

    async def request_deletion(self, user_id: UUID, *, at: datetime) -> None:
        await self._s.execute(
            update(m.User)
            .where(m.User.id == user_id)
            .values(status=e.AccountStatus.DELETED, deleted_at=at, version=m.User.version + 1)
        )
        await self._s.execute(
            update(m.SellerProfile).where(m.SellerProfile.user_id == user_id).values(deleted_at=at)
        )
        self._s.add(
            m.AccountDeletionRequestModel(user_id=user_id, status="PENDING_REVIEW", requested_at=at)
        )
        await self._s.flush()

    async def set_password_hash(self, user_id: UUID, password_hash: str) -> None:
        await self._s.execute(
            update(m.User)
            .where(m.User.id == user_id)
            .values(password_hash=password_hash, password_changed_at=func.now())
        )

    async def get_mfa_secret(self, user_id: UUID) -> bytes | None:
        return (
            await self._s.execute(select(m.User.mfa_secret_encrypted).where(m.User.id == user_id))
        ).scalar_one_or_none()

    async def set_mfa_secret(self, user_id: UUID, secret_encrypted: bytes | None) -> None:
        await self._s.execute(
            update(m.User).where(m.User.id == user_id).values(mfa_secret_encrypted=secret_encrypted)
        )

    async def record_failed_login(self, user_id: UUID, *, locked_until: datetime | None) -> None:
        await self._s.execute(
            update(m.User)
            .where(m.User.id == user_id)
            .values(
                failed_login_count=m.User.failed_login_count + 1,
                locked_until=locked_until,
            )
        )

    async def record_successful_login(self, user_id: UUID, *, at: datetime) -> None:
        await self._s.execute(
            update(m.User)
            .where(m.User.id == user_id)
            .values(failed_login_count=0, locked_until=None, last_login_at=at)
        )

    async def mark_email_verified(self, user_id: UUID, *, at: datetime) -> None:
        await self._s.execute(
            update(m.User)
            .where(m.User.id == user_id)
            .values(email_verified_at=at, status=e.AccountStatus.ACTIVE)
        )

    async def assign_role(self, user_id: UUID, role_key: str, *, granted_by: UUID | None) -> None:
        role_id = (
            await self._s.execute(select(m.Role.id).where(m.Role.key == role_key))
        ).scalar_one_or_none()
        if role_id is None:
            return
        exists = (
            await self._s.execute(
                select(m.UserRoleLink).where(
                    m.UserRoleLink.user_id == user_id, m.UserRoleLink.role_id == role_id
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            self._s.add(m.UserRoleLink(user_id=user_id, role_id=role_id, granted_by=granted_by))

    async def list_permissions(self, user_id: UUID) -> frozenset[str]:
        rows = await self._s.execute(
            select(m.Permission.key)
            .join(m.RolePermission, m.RolePermission.permission_id == m.Permission.id)
            .join(m.UserRoleLink, m.UserRoleLink.role_id == m.RolePermission.role_id)
            .where(m.UserRoleLink.user_id == user_id)
        )
        return frozenset(rows.scalars().all())


class SqlRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _lock_user(self, user_id: UUID) -> None:
        # One common lock order (user, then token) serializes rotation against
        # logout/reset. Otherwise logout can miss a concurrently inserted child.
        await self._s.execute(select(m.User.id).where(m.User.id == user_id).with_for_update())

    async def get_by_hash(self, token_hash: bytes) -> ent.RefreshToken | None:
        owner = await self._s.scalar(
            select(m.RefreshToken.user_id).where(m.RefreshToken.token_hash == token_hash)
        )
        if owner is not None:
            await self._lock_user(owner)
        row = (
            await self._s.execute(
                select(m.RefreshToken)
                .where(m.RefreshToken.token_hash == token_hash)
                # FOR UPDATE: rotation and reuse detection must not interleave,
                # or two concurrent refreshes could both succeed.
                .with_for_update()
            )
        ).scalar_one_or_none()
        return map_.to_refresh_token(row) if row else None

    async def add(self, token: ent.RefreshToken) -> ent.RefreshToken:
        self._s.add(
            m.RefreshToken(
                id=token.id,
                user_id=token.user_id,
                token_hash=token.token_hash,
                family_id=token.family_id,
                parent_id=token.parent_id,
                device_id=token.device_id,
                ip_address=token.ip_address,
                user_agent=token.user_agent,
                expires_at=token.expires_at,
                created_at=token.created_at,
            )
        )
        await self._s.flush()
        return token

    async def revoke(self, token_id: UUID, *, at: datetime, reason: str) -> None:
        await self._s.execute(
            update(m.RefreshToken)
            .where(m.RefreshToken.id == token_id, m.RefreshToken.revoked_at.is_(None))
            .values(revoked_at=at, revoked_reason=reason)
        )

    async def revoke_family(self, family_id: UUID, *, at: datetime, reason: str) -> int:
        owner = await self._s.scalar(
            select(m.RefreshToken.user_id).where(m.RefreshToken.family_id == family_id).limit(1)
        )
        if owner is not None:
            await self._lock_user(owner)
        result = await self._s.execute(
            update(m.RefreshToken)
            .where(m.RefreshToken.family_id == family_id, m.RefreshToken.revoked_at.is_(None))
            .values(revoked_at=at, revoked_reason=reason)
        )
        # A DML statement always yields a CursorResult; only that subclass
        # carries rowcount, and execute() is typed as the general Result.
        return int(cast("CursorResult[Any]", result).rowcount or 0)

    async def revoke_all_for_user(
        self, user_id: UUID, *, at: datetime, reason: str, except_id: UUID | None = None
    ) -> int:
        await self._lock_user(user_id)
        stmt = (
            update(m.RefreshToken)
            .where(m.RefreshToken.user_id == user_id, m.RefreshToken.revoked_at.is_(None))
            .values(revoked_at=at, revoked_reason=reason)
        )
        if except_id is not None:
            stmt = stmt.where(m.RefreshToken.id != except_id)
        result = await self._s.execute(stmt)
        # A DML statement always yields a CursorResult; only that subclass
        # carries rowcount, and execute() is typed as the general Result.
        return int(cast("CursorResult[Any]", result).rowcount or 0)

    async def family_is_active(
        self, user_id: UUID, family_id: UUID, *, at: datetime, idle_days: int
    ) -> bool:
        """DB authority for access sessions: rotation preserves a family; revocation kills it.

        Never cache this result across requests: logout/password reset must take effect
        on the next request even while the signed access token has time remaining.
        """
        from datetime import timedelta

        row = await self._s.scalar(
            select(m.RefreshToken.id)
            .where(
                m.RefreshToken.user_id == user_id,
                m.RefreshToken.family_id == family_id,
                m.RefreshToken.revoked_at.is_(None),
                m.RefreshToken.expires_at > at,
                m.RefreshToken.created_at > at - timedelta(days=idle_days),
            )
            .limit(1)
        )
        return row is not None

    async def list_active_for_user(self, user_id: UUID) -> list[ent.RefreshToken]:
        rows = await self._s.execute(
            select(m.RefreshToken).where(
                m.RefreshToken.user_id == user_id, m.RefreshToken.revoked_at.is_(None)
            )
        )
        return [map_.to_refresh_token(r) for r in rows.scalars().all()]

    async def delete_expired(self, *, before: datetime) -> int:
        result = await self._s.execute(
            delete(m.RefreshToken).where(m.RefreshToken.expires_at < before)
        )
        # A DML statement always yields a CursorResult; only that subclass
        # carries rowcount, and execute() is typed as the general Result.
        return int(cast("CursorResult[Any]", result).rowcount or 0)


class SqlVerificationTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_hash(
        self, token_hash: bytes, *, purpose: e.TokenPurpose
    ) -> ent.VerificationToken | None:
        row = (
            await self._s.execute(
                select(m.VerificationTokenModel)
                .where(
                    m.VerificationTokenModel.token_hash == token_hash,
                    m.VerificationTokenModel.purpose == purpose,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        return map_.to_verification_token(row) if row else None

    async def add(self, token: ent.VerificationToken) -> ent.VerificationToken:
        self._s.add(
            m.VerificationTokenModel(
                id=token.id,
                user_id=token.user_id,
                purpose=token.purpose,
                token_hash=token.token_hash,
                target=token.target,
                expires_at=token.expires_at,
                created_at=token.created_at,
            )
        )
        await self._s.flush()
        return token

    async def consume(self, token_id: UUID, *, at: datetime) -> None:
        result = await self._s.execute(
            update(m.VerificationTokenModel)
            .where(
                m.VerificationTokenModel.id == token_id,
                m.VerificationTokenModel.consumed_at.is_(None),
                m.VerificationTokenModel.expires_at > at,
            )
            .values(consumed_at=at)
            .returning(m.VerificationTokenModel.id)
        )
        if result.scalar_one_or_none() is None:
            raise TokenUsed("This verification token is no longer available.")

    async def invalidate_for_user(self, user_id: UUID, *, purpose: e.TokenPurpose) -> int:
        result = await self._s.execute(
            update(m.VerificationTokenModel)
            .where(
                m.VerificationTokenModel.user_id == user_id,
                m.VerificationTokenModel.purpose == purpose,
                m.VerificationTokenModel.consumed_at.is_(None),
            )
            .values(consumed_at=func.now())
        )
        # A DML statement always yields a CursorResult; only that subclass
        # carries rowcount, and execute() is typed as the general Result.
        return int(cast("CursorResult[Any]", result).rowcount or 0)


class SqlMfaRecoveryCodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def replace_all(
        self, user_id: UUID, code_hashes: list[bytes], *, created_at: datetime
    ) -> None:
        import uuid_utils

        await self._s.execute(
            delete(m.MfaRecoveryCodeModel).where(m.MfaRecoveryCodeModel.user_id == user_id)
        )
        for code_hash in code_hashes:
            self._s.add(
                m.MfaRecoveryCodeModel(
                    id=UUID(str(uuid_utils.uuid7())),
                    user_id=user_id,
                    code_hash=code_hash,
                    created_at=created_at,
                )
            )
        await self._s.flush()

    async def get_unused_by_hash(self, user_id: UUID, code_hash: bytes) -> UUID | None:
        return (
            await self._s.execute(
                select(m.MfaRecoveryCodeModel.id).where(
                    m.MfaRecoveryCodeModel.user_id == user_id,
                    m.MfaRecoveryCodeModel.code_hash == code_hash,
                    m.MfaRecoveryCodeModel.used_at.is_(None),
                )
            )
        ).scalar_one_or_none()

    async def consume(self, code_id: UUID, *, at: datetime) -> None:
        result = await self._s.execute(
            update(m.MfaRecoveryCodeModel)
            .where(m.MfaRecoveryCodeModel.id == code_id, m.MfaRecoveryCodeModel.used_at.is_(None))
            .values(used_at=at)
            .returning(m.MfaRecoveryCodeModel.id)
        )
        if result.scalar_one_or_none() is None:
            raise TokenUsed("This recovery code has already been used.")

    async def count_unused(self, user_id: UUID) -> int:
        result = await self._s.execute(
            select(func.count(m.MfaRecoveryCodeModel.id)).where(
                m.MfaRecoveryCodeModel.user_id == user_id,
                m.MfaRecoveryCodeModel.used_at.is_(None),
            )
        )
        return int(result.scalar_one())


class SqlOtpRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_active(self, user_id: UUID, *, purpose: e.OtpPurpose) -> ent.OtpCode | None:
        row = (
            await self._s.execute(
                select(m.OtpCodeModel)
                .where(
                    m.OtpCodeModel.user_id == user_id,
                    m.OtpCodeModel.purpose == purpose,
                    m.OtpCodeModel.consumed_at.is_(None),
                )
                .order_by(m.OtpCodeModel.created_at.desc())
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
        return map_.to_otp(row) if row else None

    async def add(self, otp: ent.OtpCode) -> ent.OtpCode:
        self._s.add(
            m.OtpCodeModel(
                id=otp.id,
                user_id=otp.user_id,
                phone_number_id=otp.phone_number_id,
                purpose=otp.purpose,
                code_hash=otp.code_hash,
                max_attempts=otp.max_attempts,
                expires_at=otp.expires_at,
                sent_at=otp.sent_at,
                created_at=otp.created_at,
            )
        )
        await self._s.flush()
        return otp

    async def increment_attempts(self, otp_id: UUID) -> int:
        """Atomic increment.

        A read-modify-write here would let concurrent requests brute-force past
        the attempt cap, which is the entire protection on a 6-digit code.
        """
        result = await self._s.execute(
            update(m.OtpCodeModel)
            .where(m.OtpCodeModel.id == otp_id)
            .values(attempts=m.OtpCodeModel.attempts + 1)
            .returning(m.OtpCodeModel.attempts)
        )
        return int(result.scalar_one())

    async def consume(self, otp_id: UUID, *, at: datetime) -> None:
        result = await self._s.execute(
            update(m.OtpCodeModel)
            .where(
                m.OtpCodeModel.id == otp_id,
                m.OtpCodeModel.consumed_at.is_(None),
                m.OtpCodeModel.expires_at > at,
            )
            .values(consumed_at=at)
            .returning(m.OtpCodeModel.id)
        )
        if result.scalar_one_or_none() is None:
            raise TokenUsed("This code is no longer available.")

    async def count_sent_since(self, user_id: UUID, *, since: datetime) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.OtpCodeModel)
                    .where(
                        m.OtpCodeModel.user_id == user_id,
                        m.OtpCodeModel.sent_at >= since,
                    )
                )
            ).scalar_one()
        )


class SqlConsentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def has_granted(self, user_id: UUID, *, consent_type: str) -> bool:
        count = (
            await self._s.execute(
                select(func.count())
                .select_from(m.ConsentModel)
                .where(
                    m.ConsentModel.user_id == user_id,
                    m.ConsentModel.consent_type == consent_type,
                    m.ConsentModel.granted.is_(True),
                    m.ConsentModel.revoked_at.is_(None),
                )
            )
        ).scalar_one()
        return bool(count)

    async def record(self, consent: ent.Consent) -> ent.Consent:
        self._s.add(
            m.ConsentModel(
                id=consent.id,
                user_id=consent.user_id,
                consent_type=consent.consent_type,
                version=consent.version,
                granted=consent.granted,
                granted_at=consent.granted_at,
                ip=consent.ip,
                user_agent=consent.user_agent,
            )
        )
        await self._s.flush()
        return consent

    async def list_for_user(self, user_id: UUID) -> list[ent.Consent]:
        rows = await self._s.execute(
            select(m.ConsentModel).where(m.ConsentModel.user_id == user_id)
        )
        return [
            ent.Consent(
                id=r.id,
                user_id=r.user_id,
                consent_type=r.consent_type,
                version=r.version,
                granted=r.granted,
                granted_at=r.granted_at,
                ip=str(r.ip) if r.ip else None,
                user_agent=r.user_agent,
                revoked_at=r.revoked_at,
            )
            for r in rows.scalars().all()
        ]
