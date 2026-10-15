"""Moderation repositories. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from trustlens.core.domain import entities as ent
from trustlens.core.domain import enums as e
from trustlens.db import mappers as map_
from trustlens.db import models as m


class SqlReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, report: ent.Report) -> ent.Report:
        self._s.add(
            m.ReportModel(
                id=report.id,
                reporter_id=report.reporter_id,
                target_type=report.target_type,
                target_id=report.target_id,
                category=report.category,
                description=report.description,
                status=report.status,
                created_at=report.created_at,
            )
        )
        await self._s.flush()
        return report

    async def get(self, report_id: UUID) -> ent.Report | None:
        row = await self._s.get(m.ReportModel, report_id)
        return map_.to_report(row) if row else None

    async def list_for_reporter(self, reporter_id: UUID, *, limit: int = 50) -> list[ent.Report]:
        stmt = (
            select(m.ReportModel)
            .where(m.ReportModel.reporter_id == reporter_id)
            .order_by(m.ReportModel.created_at.desc())
            .limit(limit)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_report(r) for r in rows]

    async def list_queue(
        self, *, status: e.ReportStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[ent.Report]:
        stmt = select(m.ReportModel).order_by(m.ReportModel.created_at.desc())
        if status is not None:
            stmt = stmt.where(m.ReportModel.status == status)
        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_report(r) for r in rows]

    async def count_queue(self, *, status: e.ReportStatus | None = None) -> int:
        stmt = select(func.count()).select_from(m.ReportModel)
        if status is not None:
            stmt = stmt.where(m.ReportModel.status == status)
        return int((await self._s.execute(stmt)).scalar_one())

    async def resolve(
        self,
        report_id: UUID,
        *,
        status: e.ReportStatus,
        resolution_note: str | None,
        resolved_by: UUID,
        resolved_at: datetime,
    ) -> ent.Report:
        await self._s.execute(
            update(m.ReportModel)
            .where(m.ReportModel.id == report_id)
            .values(
                status=status,
                resolution_note=resolution_note,
                resolved_by=resolved_by,
                resolved_at=resolved_at,
            )
        )
        row = await self._s.get(m.ReportModel, report_id)
        assert row is not None
        return map_.to_report(row)


class SqlBlockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, block: ent.Block) -> ent.Block:
        self._s.add(
            m.BlockModel(
                id=block.id,
                blocker_id=block.blocker_id,
                blocked_id=block.blocked_id,
                created_at=block.created_at,
            )
        )
        await self._s.flush()
        return block

    async def remove(self, *, blocker_id: UUID, blocked_id: UUID) -> None:
        await self._s.execute(
            delete(m.BlockModel).where(
                m.BlockModel.blocker_id == blocker_id, m.BlockModel.blocked_id == blocked_id
            )
        )

    async def exists(self, *, blocker_id: UUID, blocked_id: UUID) -> bool:
        row = (
            await self._s.execute(
                select(m.BlockModel.id).where(
                    m.BlockModel.blocker_id == blocker_id, m.BlockModel.blocked_id == blocked_id
                )
            )
        ).first()
        return row is not None

    async def is_blocked_either_way(self, user_a: UUID, user_b: UUID) -> bool:
        row = (
            await self._s.execute(
                select(m.BlockModel.id).where(
                    or_(
                        and_(m.BlockModel.blocker_id == user_a, m.BlockModel.blocked_id == user_b),
                        and_(m.BlockModel.blocker_id == user_b, m.BlockModel.blocked_id == user_a),
                    )
                )
            )
        ).first()
        return row is not None

    async def list_blocked_ids(self, blocker_id: UUID) -> frozenset[UUID]:
        rows = await self._s.execute(
            select(m.BlockModel.blocked_id).where(m.BlockModel.blocker_id == blocker_id)
        )
        return frozenset(rows.scalars().all())


class SqlAppealRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, appeal_id: UUID) -> ent.Appeal | None:
        row = (
            await self._s.execute(
                select(m.AppealModel)
                .options(selectinload(m.AppealModel.messages))
                .where(m.AppealModel.id == appeal_id, m.AppealModel.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        return map_.to_appeal(row) if row else None

    async def add(self, appeal: ent.Appeal) -> ent.Appeal:
        self._s.add(
            m.AppealModel(
                id=appeal.id,
                seller_id=appeal.seller_id,
                trust_score_id=appeal.trust_score_id,
                submitted_by=appeal.submitted_by,
                reason_category=appeal.reason_category,
                reason=appeal.reason,
                status=appeal.status,
                submitted_at=appeal.submitted_at,
                created_at=appeal.created_at,
                updated_at=appeal.created_at,
            )
        )
        await self._s.flush()
        return appeal

    async def update(self, appeal: ent.Appeal) -> ent.Appeal:
        await self._s.execute(
            update(m.AppealModel)
            .where(m.AppealModel.id == appeal.id)
            .values(
                status=appeal.status,
                assigned_to=appeal.assigned_to,
                assigned_at=appeal.assigned_at,
                resolution_note=appeal.resolution_note,
                decision=appeal.decision,
                resulting_score_id=appeal.resulting_score_id,
                resolved_at=appeal.resolved_at,
                resolved_by=appeal.resolved_by,
                version=m.AppealModel.version + 1,
            )
        )
        return appeal

    async def add_message(self, message: ent.AppealMessage) -> ent.AppealMessage:
        self._s.add(
            m.AppealMessageModel(
                id=message.id,
                appeal_id=message.appeal_id,
                sender_id=message.sender_id,
                sender_role=message.sender_role,
                body=message.body,
                is_internal=message.is_internal,
                created_at=message.created_at,
            )
        )
        await self._s.flush()
        return message

    async def list_for_seller(self, seller_id: UUID) -> list[ent.Appeal]:
        rows = await self._s.execute(
            select(m.AppealModel)
            .options(selectinload(m.AppealModel.messages))
            .where(m.AppealModel.seller_id == seller_id, m.AppealModel.deleted_at.is_(None))
            .order_by(m.AppealModel.submitted_at.desc())
        )
        return [map_.to_appeal(r) for r in rows.scalars().all()]

    async def count_open_for_seller(self, seller_id: UUID) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.AppealModel)
                    .where(
                        m.AppealModel.seller_id == seller_id,
                        m.AppealModel.status.in_(
                            [
                                e.AppealStatus.OPEN,
                                e.AppealStatus.UNDER_REVIEW,
                                e.AppealStatus.NEEDS_INFO,
                            ]
                        ),
                        m.AppealModel.deleted_at.is_(None),
                    )
                )
            ).scalar_one()
        )

    async def count_since(self, seller_id: UUID, *, since: datetime) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.AppealModel)
                    .where(
                        m.AppealModel.seller_id == seller_id,
                        m.AppealModel.submitted_at >= since,
                    )
                )
            ).scalar_one()
        )

    async def list_queue(
        self, *, status: e.AppealStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[ent.Appeal]:
        stmt = (
            select(m.AppealModel)
            .options(selectinload(m.AppealModel.messages))
            .where(m.AppealModel.deleted_at.is_(None))
            .order_by(m.AppealModel.submitted_at)
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(m.AppealModel.status == status)
        rows = await self._s.execute(stmt)
        return [map_.to_appeal(r) for r in rows.scalars().all()]


class SqlReviewCaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, case_id: UUID) -> ent.ReviewCase | None:
        row = await self._s.get(m.ReviewCaseModel, case_id)
        return map_.to_review_case(row) if row else None

    async def add(self, case: ent.ReviewCase) -> ent.ReviewCase:
        self._s.add(
            m.ReviewCaseModel(
                id=case.id,
                seller_id=case.seller_id,
                case_type=case.case_type,
                priority=case.priority,
                status=case.status,
                trigger_reason=case.trigger_reason,
                related_entity_type=case.related_entity_type,
                related_entity_id=case.related_entity_id,
                created_at=case.created_at,
                updated_at=case.created_at,
            )
        )
        await self._s.flush()
        return case

    async def update(self, case: ent.ReviewCase) -> ent.ReviewCase:
        await self._s.execute(
            update(m.ReviewCaseModel)
            .where(m.ReviewCaseModel.id == case.id)
            .values(
                status=case.status,
                assigned_to=case.assigned_to,
                assigned_at=case.assigned_at,
                decision=case.decision,
                decision_note=case.decision_note,
                resolved_at=case.resolved_at,
                resolved_by=case.resolved_by,
            )
        )
        return case

    async def list_queue(self, *, limit: int = 50, offset: int = 0) -> list[ent.ReviewCase]:
        rows = await self._s.execute(
            select(m.ReviewCaseModel)
            .where(m.ReviewCaseModel.status.in_([e.ReviewStatus.QUEUED, e.ReviewStatus.ASSIGNED]))
            .order_by(m.ReviewCaseModel.priority, m.ReviewCaseModel.created_at)
            .limit(limit)
            .offset(offset)
        )
        return [map_.to_review_case(r) for r in rows.scalars().all()]
