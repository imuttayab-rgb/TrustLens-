"""Reports and blocks (feature MOD-01).

Separate from the appeals/review-case queues (`use_cases/admin/review_queue.py`,
`use_cases/appeals/`): those are about disputing or triaging a *score
decision*. A report is a buyer or seller flagging a listing, seller, or
message for staff attention - content/conduct moderation, not scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from trustlens.core.domain.entities import AuditLogEntry, Block, Report
from trustlens.core.domain.enums import ReportCategory, ReportStatus, ReportTargetType
from trustlens.core.domain.errors import EntityNotFound, InvalidStateError, ValidationError
from trustlens.core.domain.ports import Clock, IdGenerator, UnitOfWork

MIN_REPORT_DESCRIPTION_CHARS = 10
MAX_REPORT_DESCRIPTION_CHARS = 2_000

#: The only two terminal states a resolution can land on - RESOLVED (acted
#: on) and DISMISSED (looked at, no action needed). OPEN/UNDER_REVIEW are
#: queue states, not resolutions.
_RESOLUTION_STATES = frozenset({ReportStatus.RESOLVED, ReportStatus.DISMISSED})


def _clean_description(description: str) -> str:
    text = description.strip()
    if len(text) < MIN_REPORT_DESCRIPTION_CHARS:
        raise ValidationError(
            f"Describe what happened in at least {MIN_REPORT_DESCRIPTION_CHARS} characters.",
            field="description",
        )
    if len(text) > MAX_REPORT_DESCRIPTION_CHARS:
        raise ValidationError(
            f"Keep the description under {MAX_REPORT_DESCRIPTION_CHARS} characters.",
            field="description",
        )
    return text


@dataclass(frozen=True, slots=True)
class CreateReportCommand:
    reporter_id: UUID
    target_type: ReportTargetType
    target_id: UUID
    category: ReportCategory
    description: str


class CreateReport:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: CreateReportCommand) -> Report:
        description = _clean_description(cmd.description)
        now = self._clock.now()

        async with self._uow:
            report = await self._uow.reports.add(
                Report(
                    id=self._ids.new(),
                    reporter_id=cmd.reporter_id,
                    target_type=cmd.target_type,
                    target_id=cmd.target_id,
                    category=cmd.category,
                    description=description,
                    status=ReportStatus.OPEN,
                    created_at=now,
                )
            )
            await self._uow.commit()
        return report


class ListMyReports:
    """A reporter's own submission history - status only, never the
    reviewer's identity or internal notes."""

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, reporter_id: UUID, *, limit: int = 50) -> list[Report]:
        bounded = max(1, min(limit, 100))
        async with self._uow:
            return await self._uow.reports.list_for_reporter(reporter_id, limit=bounded)


@dataclass(frozen=True, slots=True)
class BlockUserCommand:
    blocker_id: UUID
    blocked_id: UUID


class BlockUser:
    """Idempotent, same shape as AddFavorite - a repeated block request is
    not an error, it is the same intent expressed twice."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: BlockUserCommand) -> None:
        if cmd.blocker_id == cmd.blocked_id:
            raise ValidationError("You cannot block yourself.", field="blockedUserId")

        async with self._uow:
            if await self._uow.blocks.exists(blocker_id=cmd.blocker_id, blocked_id=cmd.blocked_id):
                return
            await self._uow.blocks.add(
                Block(
                    id=self._ids.new(),
                    blocker_id=cmd.blocker_id,
                    blocked_id=cmd.blocked_id,
                    created_at=self._clock.now(),
                )
            )
            await self._uow.commit()


@dataclass(frozen=True, slots=True)
class UnblockUserCommand:
    blocker_id: UUID
    blocked_id: UUID


class UnblockUser:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, cmd: UnblockUserCommand) -> None:
        async with self._uow:
            await self._uow.blocks.remove(blocker_id=cmd.blocker_id, blocked_id=cmd.blocked_id)
            await self._uow.commit()


class ListBlockedUsers:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, blocker_id: UUID) -> frozenset[UUID]:
        async with self._uow:
            return await self._uow.blocks.list_blocked_ids(blocker_id)


# ── Admin ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ReportQueuePage:
    items: tuple[Report, ...]
    total: int
    limit: int
    offset: int


class ListReportQueue:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self, *, status: ReportStatus | None = None, limit: int = 50, offset: int = 0
    ) -> ReportQueuePage:
        bounded = max(1, min(limit, 100))
        start = max(0, offset)
        async with self._uow:
            items = await self._uow.reports.list_queue(status=status, limit=bounded, offset=start)
            total = await self._uow.reports.count_queue(status=status)
        return ReportQueuePage(items=tuple(items), total=total, limit=bounded, offset=start)


@dataclass(frozen=True, slots=True)
class ResolveReportCommand:
    report_id: UUID
    resolver_id: UUID
    status: ReportStatus
    resolution_note: str | None = None


class ResolveReport:
    """A staff verdict on one report. Attributable the same way a review-case
    decision is: actor, before/after and reason land in the audit log in the
    same transaction as the state change."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: ResolveReportCommand) -> Report:
        if cmd.status not in _RESOLUTION_STATES:
            raise ValidationError(
                "A report can only be resolved as RESOLVED or DISMISSED.", field="status"
            )

        now = self._clock.now()
        async with self._uow:
            report = await self._uow.reports.get(cmd.report_id)
            if report is None:
                raise EntityNotFound("report", cmd.report_id)
            if not report.is_open:
                raise InvalidStateError("This report has already been resolved.")

            resolved = await self._uow.reports.resolve(
                report.id,
                status=cmd.status,
                resolution_note=cmd.resolution_note,
                resolved_by=cmd.resolver_id,
                resolved_at=now,
            )
            await self._uow.audit_logs.record(
                AuditLogEntry(
                    id=self._ids.new(),
                    action="report.resolved",
                    entity_type="reports",
                    entity_id=report.id,
                    actor_id=cmd.resolver_id,
                    occurred_at=now,
                    before={"status": report.status.value},
                    after={"status": cmd.status.value, "note": cmd.resolution_note},
                )
            )
            await self._uow.commit()
        return resolved


__all__ = [
    "MAX_REPORT_DESCRIPTION_CHARS",
    "MIN_REPORT_DESCRIPTION_CHARS",
    "BlockUser",
    "BlockUserCommand",
    "CreateReport",
    "CreateReportCommand",
    "ListBlockedUsers",
    "ListMyReports",
    "ListReportQueue",
    "ReportQueuePage",
    "ResolveReport",
    "ResolveReportCommand",
    "UnblockUser",
    "UnblockUserCommand",
]
