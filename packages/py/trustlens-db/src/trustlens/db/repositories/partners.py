"""Partners repositories. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from trustlens.core.domain import entities as ent
from trustlens.core.domain import enums as e
from trustlens.db import mappers as map_
from trustlens.db import models as m
from .common import _alive


class SqlApiClientRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, client_id: UUID) -> ent.ApiClient | None:
        row = await self._s.get(m.ApiClientModel, client_id)
        return map_.to_api_client(row) if row and row.deleted_at is None else None

    async def create(self, client: ent.ApiClient) -> ent.ApiClient:
        self._s.add(
            m.ApiClientModel(
                id=client.id,
                name=client.name,
                slug=client.slug,
                marketplace_id=client.marketplace_id,
                contact_email=client.contact_email,
                contact_name=client.contact_name,
                status=client.status,
                rate_limit_tier=client.rate_limit_tier,
                monthly_quota=client.monthly_quota,
                allowed_origins=list(client.allowed_origins),
                allowed_ips=list(client.allowed_ips),
                created_at=client.created_at,
                updated_at=client.created_at,
            )
        )
        await self._s.flush()
        return client

    async def update(self, client: ent.ApiClient) -> ent.ApiClient:
        await self._s.execute(
            update(m.ApiClientModel)
            .where(m.ApiClientModel.id == client.id)
            .values(
                name=client.name,
                status=client.status,
                rate_limit_tier=client.rate_limit_tier,
                monthly_quota=client.monthly_quota,
                allowed_origins=list(client.allowed_origins),
                allowed_ips=list(client.allowed_ips),
            )
        )
        return client

    async def list_all(self) -> list[ent.ApiClient]:
        rows = await self._s.execute(
            _alive(select(m.ApiClientModel), m.ApiClientModel).order_by(
                m.ApiClientModel.created_at.desc()
            )
        )
        return [map_.to_api_client(r) for r in rows.scalars().all()]

    async def get_by_slug(self, slug: str) -> ent.ApiClient | None:
        row = (
            await self._s.execute(
                _alive(select(m.ApiClientModel), m.ApiClientModel).where(
                    m.ApiClientModel.slug == slug
                )
            )
        ).scalar_one_or_none()
        return map_.to_api_client(row) if row else None

    async def get_key_by_prefix(self, prefix: str) -> ent.ApiKey | None:
        row = (
            await self._s.execute(
                _alive(select(m.ApiKeyModel), m.ApiKeyModel).where(
                    m.ApiKeyModel.key_prefix == prefix
                )
            )
        ).scalar_one_or_none()
        return map_.to_api_key(row) if row else None

    async def get_key(self, key_id: UUID) -> ent.ApiKey | None:
        row = await self._s.get(m.ApiKeyModel, key_id)
        return map_.to_api_key(row) if row and row.deleted_at is None else None

    async def list_keys(self, client_id: UUID) -> list[ent.ApiKey]:
        rows = await self._s.execute(
            _alive(select(m.ApiKeyModel), m.ApiKeyModel)
            .where(m.ApiKeyModel.api_client_id == client_id)
            .order_by(m.ApiKeyModel.created_at.desc())
        )
        return [map_.to_api_key(r) for r in rows.scalars().all()]

    async def expire_key(self, key_id: UUID, *, at: datetime) -> None:
        """Set an expiry without revoking.

        This is what makes rotation safe: the old key keeps working for the
        overlap and dies on its own. Revoking instead would take the partner
        down for the length of their deploy, which is why nobody rotates.
        """
        await self._s.execute(
            update(m.ApiKeyModel).where(m.ApiKeyModel.id == key_id).values(expires_at=at)
        )

    async def add_key(self, key: ent.ApiKey) -> ent.ApiKey:
        self._s.add(
            m.ApiKeyModel(
                id=key.id,
                api_client_id=key.api_client_id,
                name=key.name,
                key_prefix=key.key_prefix,
                key_hash=key.key_hash,
                scopes=sorted(key.scopes),
                status=key.status,
                expires_at=key.expires_at,
                created_at=key.created_at,
                updated_at=key.created_at,
            )
        )
        await self._s.flush()
        return key

    async def revoke_key(self, key_id: UUID, *, by: UUID, at: datetime) -> None:
        await self._s.execute(
            update(m.ApiKeyModel)
            .where(m.ApiKeyModel.id == key_id)
            .values(status=e.ApiKeyStatus.REVOKED, revoked_at=at, revoked_by=by)
        )

    async def touch_key(self, key_id: UUID, *, at: datetime, ip: str | None) -> None:
        await self._s.execute(
            update(m.ApiKeyModel)
            .where(m.ApiKeyModel.id == key_id)
            .values(last_used_at=at, last_used_ip=ip)
        )

    async def log_request(self, **kwargs: Any) -> None:
        import uuid_utils

        self._s.add(m.ApiRequestLog(id=UUID(str(uuid_utils.uuid7())), **kwargs))

    async def usage_this_month(self, client_id: UUID) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.ApiRequestLog)
                    .where(
                        m.ApiRequestLog.api_client_id == client_id,
                        m.ApiRequestLog.occurred_at >= func.date_trunc("month", func.now()),
                    )
                )
            ).scalar_one()
        )
