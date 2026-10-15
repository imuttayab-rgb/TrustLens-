"""Operations repositories. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from typing import Any, cast
from uuid import UUID
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from trustlens.core.domain import entities as ent
from trustlens.core.domain import enums as e
from trustlens.db import mappers as map_
from trustlens.db import models as m


class SqlAuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def record(self, entry: ent.AuditLogEntry) -> None:
        self._s.add(
            m.AuditLogModel(
                id=entry.id,
                actor_id=entry.actor_id,
                actor_type=e.ActorType(entry.actor_type),
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                before=entry.before,
                after=entry.after,
                ip=entry.ip,
                user_agent=entry.user_agent,
                request_id=entry.request_id,
                occurred_at=entry.occurred_at,
            )
        )

    async def list_for_entity(
        self, *, entity_type: str, entity_id: UUID, limit: int = 50
    ) -> list[ent.AuditLogEntry]:
        rows = await self._s.execute(
            select(m.AuditLogModel)
            .where(
                m.AuditLogModel.entity_type == entity_type,
                m.AuditLogModel.entity_id == entity_id,
            )
            .order_by(m.AuditLogModel.occurred_at.desc())
            .limit(limit)
        )
        return [_to_audit(r) for r in rows.scalars().all()]

    async def search(self, **filters: Any) -> list[ent.AuditLogEntry]:
        stmt = select(m.AuditLogModel).order_by(m.AuditLogModel.occurred_at.desc())
        if actor_id := filters.get("actor_id"):
            stmt = stmt.where(m.AuditLogModel.actor_id == actor_id)
        if action := filters.get("action"):
            stmt = stmt.where(m.AuditLogModel.action == action)
        if entity_type := filters.get("entity_type"):
            stmt = stmt.where(m.AuditLogModel.entity_type == entity_type)
        stmt = stmt.limit(int(filters.get("limit", 100)))
        rows = await self._s.execute(stmt)
        return [_to_audit(r) for r in rows.scalars().all()]


def _to_audit(row: m.AuditLogModel) -> ent.AuditLogEntry:
    return ent.AuditLogEntry(
        id=row.id,
        action=row.action,
        entity_type=row.entity_type,
        occurred_at=row.occurred_at,
        actor_id=row.actor_id,
        actor_type=row.actor_type.value,
        entity_id=row.entity_id,
        before=row.before,
        after=row.after,
        ip=str(row.ip) if row.ip else None,
        user_agent=row.user_agent,
        request_id=row.request_id,
    )


class SqlJobRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, job_id: UUID) -> ent.JobRun | None:
        row = await self._s.get(m.JobRunModel, job_id)
        return map_.to_job_run(row) if row else None

    async def get_by_key(self, job_key: str) -> ent.JobRun | None:
        row = (
            await self._s.execute(select(m.JobRunModel).where(m.JobRunModel.job_key == job_key))
        ).scalar_one_or_none()
        return map_.to_job_run(row) if row else None

    async def add(self, job: ent.JobRun) -> ent.JobRun:
        self._s.add(
            m.JobRunModel(
                id=job.id,
                job_name=job.job_name,
                job_key=job.job_key,
                status=e.JobStatus(job.status),
                related_entity_type=job.related_entity_type,
                related_entity_id=job.related_entity_id,
                attempt=job.attempt,
                max_attempts=job.max_attempts,
                payload=job.payload,
                request_id=job.request_id,
                queued_at=job.queued_at,
            )
        )
        await self._s.flush()
        return job

    async def update(self, job: ent.JobRun) -> ent.JobRun:
        await self._s.execute(
            update(m.JobRunModel)
            .where(m.JobRunModel.id == job.id)
            .values(
                status=e.JobStatus(job.status),
                attempt=job.attempt,
                result=job.result,
                error_message=job.error_message,
                error_type=job.error_type,
                started_at=job.started_at,
                finished_at=job.finished_at,
                duration_ms=job.duration_ms,
            )
        )
        return job

    async def list_dead_letters(self, *, limit: int = 50) -> list[ent.JobRun]:
        """Exhausted jobs. Surfaced in the admin panel - silent job loss is
        unacceptable when the outcome affects a seller's score."""
        rows = await self._s.execute(
            select(m.JobRunModel)
            .where(m.JobRunModel.status == e.JobStatus.DEAD)
            .order_by(m.JobRunModel.queued_at.desc())
            .limit(limit)
        )
        return [map_.to_job_run(r) for r in rows.scalars().all()]


class SqlNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, notification: ent.Notification) -> ent.Notification:
        self._s.add(
            m.NotificationModel(
                id=notification.id,
                user_id=notification.user_id,
                type=notification.type,
                title=notification.title,
                body=notification.body,
                data=dict(notification.data),
                channel=notification.channel,
                created_at=notification.created_at,
            )
        )
        await self._s.flush()
        return notification

    async def list_for_user(
        self, user_id: UUID, *, unread_only: bool = False, limit: int = 50
    ) -> list[ent.Notification]:
        stmt = (
            select(m.NotificationModel)
            .where(m.NotificationModel.user_id == user_id)
            .order_by(m.NotificationModel.created_at.desc())
            .limit(limit)
        )
        if unread_only:
            stmt = stmt.where(m.NotificationModel.read_at.is_(None))
        rows = await self._s.execute(stmt)
        return [map_.to_notification(r) for r in rows.scalars().all()]

    async def count_unread(self, user_id: UUID) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.NotificationModel)
                    .where(
                        m.NotificationModel.user_id == user_id,
                        m.NotificationModel.read_at.is_(None),
                    )
                )
            ).scalar_one()
        )

    async def mark_read(self, notification_id: UUID, *, user_id: UUID, at: datetime) -> None:
        await self._s.execute(
            update(m.NotificationModel)
            .where(
                m.NotificationModel.id == notification_id, m.NotificationModel.user_id == user_id
            )
            .values(read_at=at)
        )

    async def mark_all_read(self, user_id: UUID, *, at: datetime) -> int:
        result = await self._s.execute(
            update(m.NotificationModel)
            .where(m.NotificationModel.user_id == user_id, m.NotificationModel.read_at.is_(None))
            .values(read_at=at)
        )
        # A DML statement always yields a CursorResult; only that subclass
        # carries rowcount, and execute() is typed as the general Result.
        return int(cast("CursorResult[Any]", result).rowcount or 0)
