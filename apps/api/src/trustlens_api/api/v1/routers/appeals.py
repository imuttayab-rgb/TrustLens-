"""Appeal endpoints (feature F8).

Two audiences share this router, and the split matters:

* A **seller** submits, tracks, replies to and withdraws their own appeals.
  Every route resolves the seller from the authenticated actor rather than
  trusting an id in the path, so one seller can never address another's appeal.
* A **reviewer or admin** works the queue. Those routes are permission-gated
  individually - a reviewer may resolve, but only an admin may override a
  score, and that separation is enforced in the use case as well as here.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field

from trustlens.core.application.use_cases.appeals import (
    DECISION_OVERRIDE,
    DECISION_RECOMPUTE,
    DECISION_REJECT,
    MAX_REASON_CHARS,
    MIN_REASON_CHARS,
    AddAppealMessage,
    AddAppealMessageCommand,
    ClaimAppeal,
    ClaimAppealCommand,
    ListAppealQueue,
    ListSellerAppeals,
    ListSellerAppealsQuery,
    ResolveAppeal,
    ResolveAppealCommand,
    SubmitAppeal,
    SubmitAppealCommand,
    WithdrawAppeal,
    WithdrawAppealCommand,
)
from trustlens.core.domain.entities import Appeal, AuthenticatedActor
from trustlens.core.domain.enums import AppealStatus, UserRole
from trustlens.core.domain.errors import EntityNotFound, PermissionDenied
from trustlens_api.api.deps import (
    ActorDep,
    ContainerDep,
    MetaDep,
    PageDep,
    UowDep,
    require_permissions,
)
from trustlens_api.api.v1.schemas.common import envelope

router = APIRouter(tags=["appeals"])

_REASON_CATEGORIES = (
    "IDENTITY_INCORRECT",
    "PHONE_INCORRECT",
    "LISTING_MISJUDGED",
    "DEVICE_INCORRECT",
    "OTHER",
)


class AppealMessageModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    sender_id: UUID = Field(serialization_alias="senderId")
    sender_role: str = Field(serialization_alias="senderRole")
    body: str
    created_at: Any = Field(serialization_alias="createdAt")
    is_internal: bool = Field(serialization_alias="isInternal")


class AppealModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    seller_id: UUID = Field(serialization_alias="sellerId")
    trust_score_id: UUID = Field(serialization_alias="trustScoreId")
    reason_category: str = Field(serialization_alias="reasonCategory")
    reason: str
    status: str
    submitted_at: Any = Field(serialization_alias="submittedAt")
    assigned_to: UUID | None = Field(default=None, serialization_alias="assignedTo")
    decision: str | None = None
    resolution_note: str | None = Field(default=None, serialization_alias="resolutionNote")
    resolved_at: Any = Field(default=None, serialization_alias="resolvedAt")
    messages: list[AppealMessageModel] = Field(default_factory=list)


class SubmitAppealRequest(BaseModel):
    trust_score_id: UUID = Field(
        alias="trustScoreId",
        description=(
            "The specific computation being appealed. Required: a score is "
            "recomputed on every signal change, so 'my score is wrong' is not "
            "reviewable by the time a human reads it."
        ),
    )
    reason_category: str = Field(alias="reasonCategory")
    reason: str = Field(min_length=MIN_REASON_CHARS, max_length=MAX_REASON_CHARS)

    model_config = ConfigDict(populate_by_name=True)


class AppealMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4_000)
    is_internal: bool = Field(
        default=False,
        alias="isInternal",
        description="Reviewer-only note. Rejected for seller accounts.",
    )

    model_config = ConfigDict(populate_by_name=True)


class ResolveAppealRequest(BaseModel):
    decision: str = Field(
        description=(
            f"{DECISION_RECOMPUTE} corrects the evidence and re-runs scoring; "
            f"{DECISION_OVERRIDE} is admin-only and expires; "
            f"{DECISION_REJECT} closes it with an explanation."
        )
    )
    note: str = Field(min_length=MIN_REASON_CHARS, max_length=4_000)
    override_score: int | None = Field(default=None, alias="overrideScore", ge=0, le=100)

    model_config = ConfigDict(populate_by_name=True)


def _actor_user_id(actor: AuthenticatedActor) -> UUID:
    """An appeal must be attributable to a person, not an API key."""
    if actor.user_id is None:
        raise PermissionDenied("appeal:create")
    return actor.user_id


def _actor_role(actor: AuthenticatedActor) -> UserRole:
    """The highest staff role held, defaulting to seller.

    Used only to decide whether an override is permitted. `ResolveAppeal`
    re-checks the same rule, so a wrong answer here cannot widen a grant -
    it can only produce a redundant refusal.
    """
    if UserRole.ADMIN in actor.roles:
        return UserRole.ADMIN
    if UserRole.REVIEWER in actor.roles:
        return UserRole.REVIEWER
    return UserRole.SELLER


async def _own_seller_id(actor: AuthenticatedActor, uow: UowDep) -> UUID:
    """Resolve the caller's own seller profile.

    Deliberately not a path parameter: taking the seller id from the URL would
    let any authenticated user appeal on another seller's behalf.
    """
    user_id = _actor_user_id(actor)
    seller = await uow.sellers.get_by_user(user_id)
    if seller is None:
        raise EntityNotFound("seller_profile", user_id)
    return UUID(str(seller.id))


def _to_model(appeal: Appeal) -> AppealModel:
    return AppealModel(
        id=appeal.id,
        seller_id=appeal.seller_id,
        trust_score_id=appeal.trust_score_id,
        reason_category=appeal.reason_category,
        reason=appeal.reason,
        status=appeal.status.value,
        submitted_at=appeal.submitted_at,
        assigned_to=appeal.assigned_to,
        decision=appeal.decision,
        resolution_note=appeal.resolution_note,
        resolved_at=appeal.resolved_at,
        messages=[
            AppealMessageModel(
                id=m.id,
                sender_id=m.sender_id,
                sender_role=m.sender_role.value,
                body=m.body,
                created_at=m.created_at,
                is_internal=m.is_internal,
            )
            for m in appeal.messages
        ],
    )


# ── Seller routes ────────────────────────────────────────────────────


@router.post(
    "/appeals",
    status_code=status.HTTP_201_CREATED,
    summary="Appeal a trust score",
    dependencies=[Depends(require_permissions("appeal:create"))],
)
async def submit_appeal(
    body: SubmitAppealRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    seller_id = await _own_seller_id(actor, uow)
    appeal = await SubmitAppeal(uow=uow, clock=container.clock, ids=container.ids).execute(
        SubmitAppealCommand(
            seller_id=seller_id,
            trust_score_id=body.trust_score_id,
            submitted_by=_actor_user_id(actor),
            reason_category=body.reason_category,
            reason=body.reason,
        )
    )
    return envelope(_to_model(appeal).model_dump(by_alias=True), request_id=meta.request_id)


@router.get(
    "/appeals",
    summary="Own appeals",
    description="Reviewer-only internal notes are never included.",
    dependencies=[Depends(require_permissions("appeal:read:self"))],
)
async def list_own_appeals(actor: ActorDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    seller_id = await _own_seller_id(actor, uow)
    appeals = await ListSellerAppeals(uow=uow).execute(ListSellerAppealsQuery(seller_id=seller_id))
    return envelope(
        [_to_model(a).model_dump(by_alias=True) for a in appeals], request_id=meta.request_id
    )


@router.post(
    "/appeals/{appeal_id}/withdraw",
    summary="Withdraw an appeal",
    description=(
        "Without this the one-open-appeal limit becomes a trap: a seller who "
        "appeals in haste could not appeal properly until a reviewer got to it."
    ),
    dependencies=[Depends(require_permissions("appeal:create"))],
)
async def withdraw_appeal(
    appeal_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    seller_id = await _own_seller_id(actor, uow)
    appeal = await WithdrawAppeal(uow=uow, clock=container.clock, ids=container.ids).execute(
        WithdrawAppealCommand(
            appeal_id=appeal_id, seller_id=seller_id, actor_id=_actor_user_id(actor)
        )
    )
    return envelope(_to_model(appeal).model_dump(by_alias=True), request_id=meta.request_id)


@router.post(
    "/appeals/{appeal_id}/messages",
    status_code=status.HTTP_201_CREATED,
    summary="Reply on an appeal",
    dependencies=[Depends(require_permissions("appeal:read:self"))],
)
async def add_own_message(
    appeal_id: UUID,
    body: AppealMessageRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    seller_id = await _own_seller_id(actor, uow)
    message = await AddAppealMessage(uow=uow, clock=container.clock, ids=container.ids).execute(
        AddAppealMessageCommand(
            appeal_id=appeal_id,
            sender_id=_actor_user_id(actor),
            sender_role=UserRole.SELLER,
            body=body.body,
            # A seller writing an "internal" note would hide it from
            # themselves and mislead the reviewer; the use case refuses it.
            is_internal=body.is_internal,
            seller_id=seller_id,
        )
    )
    return envelope(
        AppealMessageModel(
            id=message.id,
            sender_id=message.sender_id,
            sender_role=message.sender_role.value,
            body=message.body,
            created_at=message.created_at,
            is_internal=message.is_internal,
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


# ── Reviewer routes ──────────────────────────────────────────────────


@router.get(
    "/admin/appeals",
    summary="The appeal queue",
    dependencies=[Depends(require_permissions("appeal:read:any"))],
)
async def list_appeal_queue(
    uow: UowDep,
    page: PageDep,
    meta: MetaDep,
    appeal_status: str | None = Query(default=None, alias="status"),
    include_resolved: bool = Query(
        default=False,
        alias="includeResolved",
        description="Include withdrawn and decided appeals. Off by default: a queue is work.",
    ),
) -> dict[str, Any]:
    parsed = AppealStatus(appeal_status) if appeal_status else None
    result = await ListAppealQueue(uow=uow).execute(
        status=parsed,
        include_resolved=include_resolved,
        limit=page.per_page,
        offset=page.offset,
    )
    return envelope(
        [_to_model(a).model_dump(by_alias=True) for a in result.items],
        request_id=meta.request_id,
    )


@router.post(
    "/admin/appeals/{appeal_id}/claim",
    summary="Claim an appeal before working on it",
    dependencies=[Depends(require_permissions("appeal:assign"))],
)
async def claim_appeal(
    appeal_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    appeal = await ClaimAppeal(uow=uow, clock=container.clock, ids=container.ids).execute(
        ClaimAppealCommand(appeal_id=appeal_id, reviewer_id=_actor_user_id(actor))
    )
    return envelope(_to_model(appeal).model_dump(by_alias=True), request_id=meta.request_id)


@router.post(
    "/admin/appeals/{appeal_id}/messages",
    status_code=status.HTTP_201_CREATED,
    summary="Reply or add an internal note",
    dependencies=[Depends(require_permissions("appeal:read:any"))],
)
async def add_reviewer_message(
    appeal_id: UUID,
    body: AppealMessageRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    message = await AddAppealMessage(uow=uow, clock=container.clock, ids=container.ids).execute(
        AddAppealMessageCommand(
            appeal_id=appeal_id,
            sender_id=_actor_user_id(actor),
            sender_role=_actor_role(actor),
            body=body.body,
            is_internal=body.is_internal,
        )
    )
    return envelope(
        AppealMessageModel(
            id=message.id,
            sender_id=message.sender_id,
            sender_role=message.sender_role.value,
            body=message.body,
            created_at=message.created_at,
            is_internal=message.is_internal,
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post(
    "/admin/appeals/{appeal_id}/resolve",
    summary="Resolve an appeal",
    description=(
        "Approving corrects the evidence and enqueues a rescore; it never "
        "writes a score directly (ADR-0002). An override is admin-only, needs "
        "a written reason, and is recorded in the audit log."
    ),
    dependencies=[Depends(require_permissions("appeal:resolve"))],
)
async def resolve_appeal(
    appeal_id: UUID,
    body: ResolveAppealRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    result = await ResolveAppeal(
        uow=uow, queue=container.queue, clock=container.clock, ids=container.ids
    ).execute(
        ResolveAppealCommand(
            appeal_id=appeal_id,
            reviewer_id=_actor_user_id(actor),
            reviewer_role=_actor_role(actor),
            decision=body.decision,
            note=body.note,
            override_score=body.override_score,
        )
    )
    return envelope(
        {
            "appeal": _to_model(result.appeal).model_dump(by_alias=True),
            "rescoreQueued": result.rescore_queued,
        },
        request_id=meta.request_id,
    )


__all__ = ["router"]
