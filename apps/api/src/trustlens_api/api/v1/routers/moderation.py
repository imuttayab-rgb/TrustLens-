"""Reports and blocks endpoints (feature MOD-01).

Everything lives under /me/..., the same convention /me/favorites and
/me/conversations use: any signed-in user (buyer or seller) may report
something or block someone, no role check needed. The admin queue lives in
admin.py alongside the identity-review/appeal queues it's a sibling of.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, status

from trustlens.core.application.use_cases.moderation import (
    BlockUser,
    BlockUserCommand,
    CreateReport,
    CreateReportCommand,
    ListBlockedUsers,
    ListMyReports,
    UnblockUser,
    UnblockUserCommand,
)
from trustlens.core.domain.enums import ReportCategory, ReportTargetType
from trustlens.core.domain.errors import ValidationError
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.common import envelope
from trustlens_api.api.v1.schemas.moderation import (
    BlockUserRequest,
    CreateReportRequest,
    ReportResponse,
)

router = APIRouter(tags=["Moderation"])


def _to_report_response(report: Any) -> ReportResponse:
    return ReportResponse(
        id=report.id,
        target_type=report.target_type.value,
        target_id=report.target_id,
        category=report.category.value,
        description=report.description,
        status=report.status.value,
        created_at=report.created_at,
        resolved_at=report.resolved_at,
        resolution_note=report.resolution_note,
    )


@router.post(
    "/me/reports",
    status_code=status.HTTP_201_CREATED,
    summary="Report a listing, seller, message, or something else",
)
async def create_report(
    body: CreateReportRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    try:
        target_type = ReportTargetType(body.target_type)
        category = ReportCategory(body.category)
    except ValueError as exc:
        raise ValidationError(f"Invalid report target_type or category: {exc}") from exc

    report = await CreateReport(uow=uow, clock=container.clock, ids=container.ids).execute(
        CreateReportCommand(
            reporter_id=actor.user_id,
            target_type=target_type,
            target_id=body.target_id,
            category=category,
            description=body.description,
        )
    )
    return envelope(
        _to_report_response(report).model_dump(by_alias=True), request_id=meta.request_id
    )


@router.get("/me/reports", summary="My own report submissions")
async def list_my_reports(actor: ActorDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    assert actor.user_id is not None
    reports = await ListMyReports(uow=uow).execute(actor.user_id)
    return envelope(
        [_to_report_response(r).model_dump(by_alias=True) for r in reports],
        request_id=meta.request_id,
    )


@router.post(
    "/me/blocks",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Block a user - idempotent, safe to call repeatedly",
)
async def block_user(
    body: BlockUserRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
) -> None:
    assert actor.user_id is not None
    await BlockUser(uow=uow, clock=container.clock, ids=container.ids).execute(
        BlockUserCommand(blocker_id=actor.user_id, blocked_id=body.blocked_user_id)
    )


@router.delete(
    "/me/blocks/{blocked_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unblock a user",
)
async def unblock_user(blocked_user_id: UUID, actor: ActorDep, uow: UowDep) -> None:
    assert actor.user_id is not None
    await UnblockUser(uow=uow).execute(
        UnblockUserCommand(blocker_id=actor.user_id, blocked_id=blocked_user_id)
    )


@router.get("/me/blocks", summary="Users I've blocked")
async def list_my_blocks(actor: ActorDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    assert actor.user_id is not None
    blocked = await ListBlockedUsers(uow=uow).execute(actor.user_id)
    return envelope([str(user_id) for user_id in blocked], request_id=meta.request_id)


__all__ = ["router"]
