"""Admin review queue endpoints (feature F7).

Every route here is permission-gated, not merely role-gated. A reviewer works
the queue but deliberately cannot override a score; that separation exists in
the seeded permissions and is enforced per route rather than per router, so
adding a route cannot silently inherit a wider grant than it needs.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from trustlens.core.application.use_cases.admin import (
    MIN_DECISION_NOTE_CHARS,
    ClaimReviewCase,
    ClaimReviewCaseCommand,
    DecideReviewCase,
    DecideReviewCaseCommand,
    ListReviewQueue,
)
from trustlens.core.domain.entities import AuthenticatedActor, ReviewCase
from trustlens.core.domain.errors import PermissionDenied
from trustlens_api.api.deps import (
    ActorDep,
    ContainerDep,
    MetaDep,
    PageDep,
    UowDep,
    require_permissions,
)
from trustlens_api.api.v1.schemas.common import envelope

router = APIRouter(prefix="/admin", tags=["admin"])


class ReviewCaseModel(BaseModel):
    id: UUID
    seller_id: UUID
    case_type: str
    status: str
    priority: int
    created_at: Any
    trigger_reason: str | None = None
    related_entity_type: str | None = None
    related_entity_id: UUID | None = None
    assigned_to: UUID | None = None
    decision: str | None = None
    decision_note: str | None = None


class DecideReviewRequest(BaseModel):
    approve: bool
    note: str = Field(
        min_length=MIN_DECISION_NOTE_CHARS,
        max_length=2_000,
        description=(
            "Why this decision was made. Mandatory because a human verdict "
            "changes someone's Trust Score and must stay explainable to them."
        ),
    )


def _reviewer_id(actor: AuthenticatedActor) -> UUID:
    """A review decision must be attributable to a person.

    `user_id` is optional because an API client and a system job are also
    principals, and neither may decide a case: the audit trail would name
    nobody, and the seller could not be told who judged them.
    """
    if actor.user_id is None:
        raise PermissionDenied("review_case:decide")
    return actor.user_id


def _to_model(case: ReviewCase) -> ReviewCaseModel:
    return ReviewCaseModel(
        id=case.id,
        seller_id=case.seller_id,
        case_type=case.case_type.value,
        status=case.status.value,
        priority=case.priority,
        created_at=case.created_at,
        trigger_reason=case.trigger_reason,
        related_entity_type=case.related_entity_type,
        related_entity_id=case.related_entity_id,
        assigned_to=case.assigned_to,
        decision=case.decision,
        decision_note=case.decision_note,
    )


@router.get(
    "/review-cases",
    summary="The review queue",
    dependencies=[Depends(require_permissions("review_case:read"))],
)
async def list_review_cases(uow: UowDep, page: PageDep, meta: MetaDep) -> dict[str, Any]:
    result = await ListReviewQueue(uow=uow).execute(limit=page.per_page, offset=page.offset)
    return envelope(
        [_to_model(case).model_dump(by_alias=True) for case in result.items],
        request_id=meta.request_id,
    )


@router.post(
    "/review-cases/{case_id}/claim",
    summary="Claim a case before working on it",
    description=(
        "Claiming is what stops two reviewers deciding the same case "
        "differently. A case already assigned to someone else is refused."
    ),
    dependencies=[Depends(require_permissions("review_case:decide"))],
)
async def claim_review_case(
    case_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    case = await ClaimReviewCase(uow=uow, clock=container.clock, ids=container.ids).execute(
        ClaimReviewCaseCommand(case_id=case_id, reviewer_id=_reviewer_id(actor))
    )
    return envelope(_to_model(case).model_dump(by_alias=True), request_id=meta.request_id)


@router.post(
    "/review-cases/{case_id}/decide",
    summary="Record a decision on a case",
    description=(
        "Records a verdict and enqueues a rescore. It never writes a score "
        "directly - the scoring policy stays the only thing that produces a "
        "number (ADR-0002). The decision and its reason are audit-logged in "
        "the same transaction."
    ),
    dependencies=[Depends(require_permissions("review_case:decide"))],
)
async def decide_review_case(
    case_id: UUID,
    body: DecideReviewRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    result = await DecideReviewCase(
        uow=uow, queue=container.queue, clock=container.clock, ids=container.ids
    ).execute(
        DecideReviewCaseCommand(
            case_id=case_id,
            reviewer_id=_reviewer_id(actor),
            approve=body.approve,
            note=body.note,
        )
    )
    return envelope(
        {
            "case": _to_model(result.case).model_dump(by_alias=True),
            "identityUpdated": result.identity_updated,
        },
        request_id=meta.request_id,
    )


__all__ = ["router"]
