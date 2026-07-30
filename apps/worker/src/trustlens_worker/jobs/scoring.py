"""Scoring jobs.

`recompute_trust_score` is the ONLY writer of `trust_scores`, which makes
concurrency reasoning trivial: a per-seller lock plus a queue-level dedup key
collapses a burst of signal changes into a single computation.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from trustlens.core.application.services import SignalCollector
from trustlens.core.application.use_cases.scoring import (
    ComputeTrustScore,
    ComputeTrustScoreCommand,
)
from trustlens.core.domain.enums import ScoreTrigger
from trustlens.core.domain.policies import (
    AccountAgePolicy,
    DeviceLinkagePolicy,
    FreshnessPolicy,
)
from trustlens.shared.logging import get_logger

log = get_logger(__name__)


def _build_use_case(ctx: dict[str, Any]) -> ComputeTrustScore:
    settings = ctx["settings"]
    return ComputeTrustScore(
        uow=ctx["uow"](),
        collector=SignalCollector(
            age_policy=AccountAgePolicy(),
            device_policy=DeviceLinkagePolicy(),
            face_review_lower=settings.ai.face_match_review_lower,
        ),
        cache=ctx["cache"],
        clock=ctx["clock"],
        ids=ctx["ids"],
        freshness=FreshnessPolicy(validity_days=settings.scoring.score_validity_days),
        min_evidence_weight=settings.scoring.score_min_evidence_weight,
    )


async def recompute_trust_score(
    ctx: dict[str, Any],
    *,
    seller_id: str,
    trigger: str = "SIGNAL_CHANGE",
    skip_if_fresh: bool = False,
) -> dict[str, Any]:
    result = await _build_use_case(ctx).execute(
        ComputeTrustScoreCommand(
            seller_id=UUID(seller_id),
            trigger=ScoreTrigger(trigger),
            skip_if_fresh=skip_if_fresh,
        )
    )
    score = result.trust_score
    log.info(
        "trust_score_computed",
        seller_id=seller_id,
        score=int(score.score),
        risk_level=score.risk_level.value,
        previous=result.previous_score,
        recomputed=result.recomputed,
        cap_applied=score.cap_applied,
    )
    return {
        "score": int(score.score),
        "risk_level": score.risk_level.value,
        "recomputed": result.recomputed,
        "cap_applied": score.cap_applied,
    }


async def bulk_recompute_for_model(
    ctx: dict[str, Any], *, model_version: str, limit: int = 500
) -> dict[str, Any]:
    """Re-score everyone after a scoring model is activated.

    Rate-limited by fanning out one job per seller rather than looping here,
    so a bulk recompute cannot starve interactive verification jobs.
    """
    uow = ctx["uow"]()
    async with uow:
        seller_ids = await uow.sellers.list_stale_scores(before=ctx["clock"].now(), limit=limit)

    for seller_id in seller_ids:
        await ctx["queue"].enqueue(
            "scoring.recompute_trust_score",
            seller_id=str(seller_id),
            trigger=ScoreTrigger.MODEL_CHANGE.value,
        )

    log.info("bulk_recompute_queued", model_version=model_version, count=len(seller_ids))
    return {"queued": len(seller_ids), "model_version": model_version}


async def rescore_stale_sellers(ctx: dict[str, Any]) -> dict[str, Any]:
    """Nightly sweep over sellers whose score has expired (assumption A14)."""
    uow = ctx["uow"]()
    async with uow:
        seller_ids = await uow.sellers.list_stale_scores(before=ctx["clock"].now(), limit=1000)

    for seller_id in seller_ids:
        await ctx["queue"].enqueue(
            "scoring.recompute_trust_score",
            seller_id=str(seller_id),
            trigger=ScoreTrigger.SCHEDULED.value,
            skip_if_fresh=True,
        )

    log.info("stale_rescore_queued", count=len(seller_ids))
    return {"queued": len(seller_ids)}


__all__ = ["bulk_recompute_for_model", "recompute_trust_score", "rescore_stale_sellers"]
