"""Trust score endpoints.

These are read paths. The API performs no scoring logic of its own - every
number returned here comes straight from `trust_score_signals`, frozen at
computation time (ADR-0002).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from trustlens.core.application.use_cases.scoring import (
    GetTrustScore,
    GetTrustScoreCommand,
    summarise,
)
from trustlens.core.domain.entities import TrustScore
from trustlens.core.domain.enums import ScoreTrigger
from trustlens.core.domain.errors import EntityNotFound
from trustlens.core.domain.policies import band_label
from trustlens_api.api.deps import (
    ActorDep,
    ContainerDep,
    MetaDep,
    UowDep,
    assert_owns_seller,
    require_permissions,
)
from trustlens_api.api.v1.schemas.common import JobAccepted, envelope
from trustlens_api.api.v1.schemas.trust_score import (
    CategoryRollup,
    ImprovementItem,
    OverrideScoreRequest,
    SignalBreakdown,
    TrustScoreHistoryItem,
    TrustScoreResponse,
)

router = APIRouter(tags=["Trust Score"])


@router.get(
    "/sellers/{seller_id}/trust-score",
    summary="Get the current trust score with its full breakdown",
    description=(
        "Returns the score, the risk band, and one entry per evaluated signal "
        "with its status, points, machine reason code and human explanation. "
        "This is the explainability contract: nothing is recomputed to answer "
        "this call."
    ),
)
async def get_trust_score(
    seller_id: UUID,
    actor: ActorDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    # Object-level check, separate from the route permission. Without it this
    # endpoint is an IDOR: any seller could read any other seller's breakdown.
    await assert_owns_seller(seller_id, actor, uow)

    detail = await GetTrustScore(uow=uow).execute(
        GetTrustScoreCommand(seller_id=seller_id, include_improvements=False)
    )
    return envelope(
        trust_score_to_response(detail.score).model_dump(by_alias=True), request_id=meta.request_id
    )


@router.get(
    "/sellers/{seller_id}/trust-score/improvements",
    summary="Ranked list of what would raise this score",
    description=(
        "The unearned points, ordered by how many are recoverable, each with "
        "the concrete action that would earn them."
    ),
)
async def get_improvements(
    seller_id: UUID,
    actor: ActorDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    await assert_owns_seller(seller_id, actor, uow)

    detail = await GetTrustScore(uow=uow).execute(
        GetTrustScoreCommand(seller_id=seller_id, include_improvements=True)
    )
    return envelope(
        [
            ImprovementItem(
                signal_code=item.signal_code,
                points_available=item.points_available,
                action=item.action,
            ).model_dump(by_alias=True)
            for item in detail.improvements
        ],
        request_id=meta.request_id,
    )


@router.get(
    "/sellers/{seller_id}/trust-score/history",
    summary="Score history",
    description=(
        "Scores are append-only, so history is a first-class read rather than a reconstruction."
    ),
)
async def get_history(
    seller_id: UUID,
    actor: ActorDep,
    uow: UowDep,
    meta: MetaDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    await assert_owns_seller(seller_id, actor, uow)

    history = await uow.trust_scores.list_history(seller_id, limit=limit)
    return envelope(
        [
            TrustScoreHistoryItem(
                id=score.id,
                score=int(score.score),
                risk_level=score.risk_level.value,
                model_version=score.scoring_model_version,
                trigger=score.trigger.value,
                computed_at=score.computed_at,
                is_manual_override=score.is_manual_override,
            ).model_dump(by_alias=True)
            for score in history
        ],
        request_id=meta.request_id,
    )


@router.post(
    "/sellers/{seller_id}/trust-score/recompute",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a recomputation",
    description=(
        "Enqueues a scoring job. Rate-limited and debounced: a burst of "
        "requests collapses into a single computation."
    ),
    dependencies=[Depends(require_permissions("trust_score:recompute"))],
)
async def recompute(
    seller_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    await assert_owns_seller(seller_id, actor, uow)

    job_id = await container.queue.enqueue(
        "scoring.recompute_trust_score",
        seller_id=str(seller_id),
        trigger=ScoreTrigger.MANUAL.value,
        # A stable job id within the debounce window is what collapses a
        # burst of signal changes into one computation.
        job_id=f"score:{seller_id}:{int(container.clock.now().timestamp()) // 10}",
    )
    return envelope(
        JobAccepted(job_id=job_id, poll_url=f"/api/v1/jobs/{job_id}").model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post(
    "/admin/sellers/{seller_id}/trust-score/override",
    summary="Override a computed score (ADMIN only)",
    description=(
        "Writes a NEW score row marked as a manual override. The computed "
        "score it replaces stays in history, a written reason is mandatory "
        "(enforced by a database CHECK), and the action is audit-logged."
    ),
    dependencies=[Depends(require_permissions("trust_score:override"))],
)
async def override_score(
    seller_id: UUID,
    body: OverrideScoreRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    import dataclasses

    from trustlens.core.domain.entities import AuditLogEntry, TrustScore
    from trustlens.core.domain.policies import FreshnessPolicy, band_for
    from trustlens.core.domain.value_objects import Score

    seller = await uow.sellers.get(seller_id)
    if seller is None:
        raise EntityNotFound("seller", seller_id)

    previous = await uow.trust_scores.get_current(seller_id)
    if previous is None:
        raise EntityNotFound("trust_score", seller_id)

    now = container.clock.now()
    new_score = Score(body.score)
    overridden = TrustScore(
        id=container.ids.new(),
        seller_id=seller_id,
        scoring_model_id=previous.scoring_model_id,
        scoring_model_version=previous.scoring_model_version,
        score=new_score,
        risk_level=band_for(body.score),
        raw_score=float(body.score),
        available_weight=previous.available_weight,
        confidence=previous.confidence,
        trigger=ScoreTrigger.MANUAL,
        computed_at=now,
        # Overrides expire, so a one-off human decision cannot silently become
        # permanent (docs/08 section 8).
        valid_until=FreshnessPolicy(validity_days=90).valid_until(now),
        signals=previous.signals,
        is_current=True,
        is_manual_override=True,
        override_reason=body.reason,
        overridden_by=actor.user_id,
    )
    saved = await uow.trust_scores.replace_current(overridden)
    await uow.sellers.update(
        dataclasses.replace(seller, current_trust_score_id=saved.id, updated_at=now)
    )
    await uow.audit_logs.record(
        AuditLogEntry(
            id=container.ids.new(),
            action="trust_score.override",
            entity_type="seller_profiles",
            entity_id=seller_id,
            occurred_at=now,
            actor_id=actor.user_id,
            before={"score": int(previous.score), "risk_level": previous.risk_level.value},
            after={"score": body.score, "reason": body.reason},
            ip=meta.ip,
            request_id=meta.request_id,
        )
    )
    await uow.commit()
    await container.cache.delete_pattern(f"score:{seller_id}:*")

    return envelope(
        trust_score_to_response(saved).model_dump(by_alias=True), request_id=meta.request_id
    )


def trust_score_to_response(score: TrustScore) -> TrustScoreResponse:
    rollup = score.category_breakdown
    return TrustScoreResponse(
        id=score.id,
        seller_id=score.seller_id,
        score=int(score.score),
        risk_level=score.risk_level.value,
        risk_label=band_label(score.risk_level),
        confidence=float(score.confidence),
        model_version=score.scoring_model_version,
        computed_at=score.computed_at,
        valid_until=score.valid_until,
        cap_applied=score.cap_applied,
        is_manual_override=score.is_manual_override,
        categories=[
            CategoryRollup(
                category=category.value,
                points_awarded=float(values["points_awarded"]),
                points_possible=float(values["points_possible"]),
                status=str(values["status"]),
            )
            for category, values in rollup.items()
        ],
        signals=[
            SignalBreakdown(
                code=signal.signal_code.value,
                category=signal.category.value,
                status=signal.status.value,
                points_awarded=signal.points_awarded,
                points_possible=signal.points_possible,
                confidence=signal.confidence,
                reason_code=signal.reason_code.value,
                reason_text=signal.reason_text,
                evidence=signal.evidence,
            )
            for signal in score.signals
        ],
        unavailable_signals=[code.value for code in score.unavailable_signal_codes],
        summary=summarise(score),
    )


__all__ = ["router", "trust_score_to_response"]
