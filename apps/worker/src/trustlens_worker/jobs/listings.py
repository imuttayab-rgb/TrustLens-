"""AI listing analysis (feature F5).

Runs BOTH the LLM and the trained classifier, stores both as evidence, and
lets the scoring engine decide the points. Two independent analysers means a
single model's mistake cannot dominate the LISTING signal.
"""

from __future__ import annotations

import dataclasses
from typing import Any
from uuid import UUID

from trustlens.core.domain.entities import ListingAnalysis, ScamLabel
from trustlens.core.domain.enums import ListingStatus
from trustlens.core.domain.errors import ExternalServiceError
from trustlens.shared.logging import get_logger

log = get_logger(__name__)


async def analyse_listing(ctx: dict[str, Any], *, listing_id: str) -> dict[str, Any]:
    uow = ctx["uow"]()
    lid = UUID(listing_id)

    async with uow:
        listing = await uow.listings.get(lid)
        if listing is None:
            return {"skipped": "listing not found"}
        median = (
            await uow.listings.category_median_price(
                listing.category, currency=listing.price.currency
            )
            if listing.category and listing.price
            else None
        )

    try:
        llm = await ctx["llm"].analyze_listing(
            title=listing.title,
            description=listing.description,
            price=listing.price.amount if listing.price else None,
            currency=listing.price.currency if listing.price else None,
            category=listing.category,
        )
    except ExternalServiceError:
        # Re-raised so ARQ retries. If every attempt fails the signal ends up
        # UNAVAILABLE, which the scoring engine EXCLUDES rather than scoring
        # as zero - our provider outage must not cost a seller points.
        log.warning("listing_llm_unavailable", listing_id=listing_id)
        raise

    classifier = await ctx["classifier"].predict(
        title=listing.title,
        description=listing.description,
        price=listing.price.amount if listing.price else None,
        category=listing.category,
    )

    price_deviation = None
    if median and listing.price and median > 0:
        price_deviation = round(((listing.price.amount - median) / median) * 100, 2)

    # Combine: take the higher risk of the two, so a scam pattern only one of
    # them recognises is not averaged away.
    combined_risk = max(llm.risk_score, classifier.scam_probability * 100)
    now = ctx["clock"].now()

    async with uow:
        analysis = await uow.listings.add_analysis(
            ListingAnalysis(
                id=ctx["ids"].new(),
                listing_id=lid,
                analyzer_type="LLM+CLASSIFIER",
                provider=llm.provider,
                model_name=llm.model_name,
                model_version=f"{llm.model_version}+{classifier.model_version}",
                prompt_version=llm.prompt_version,
                risk_score=combined_risk,
                confidence=min(llm.confidence, 0.95),
                labels=tuple(
                    ScamLabel(code=label, confidence=llm.confidence) for label in llm.labels
                ),
                findings={
                    "llm": llm.findings,
                    "llm_summary": llm.summary,
                    "classifier_probability": classifier.scam_probability,
                    "classifier_label": classifier.label,
                },
                price_deviation_pct=price_deviation,
                raw_response=llm.raw,
                input_tokens=llm.input_tokens,
                output_tokens=llm.output_tokens,
                latency_ms=llm.latency_ms,
                cost_usd=llm.cost_usd,
                analysed_at=now,
            )
        )
        await uow.listings.update(
            dataclasses.replace(
                listing,
                status=ListingStatus.FLAGGED if combined_risk >= 60 else ListingStatus.ACTIVE,
                latest_analysis=analysis,
            )
        )
        await uow.commit()

    await ctx["queue"].enqueue(
        "scoring.recompute_trust_score",
        seller_id=str(listing.seller_id),
        trigger="SIGNAL_CHANGE",
    )

    return {
        "risk_score": combined_risk,
        "labels": list(llm.labels),
        "price_deviation_pct": price_deviation,
    }


__all__ = ["analyse_listing"]
