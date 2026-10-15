"""AI listing analysis (feature F5).

Runs BOTH the LLM and the trained classifier, stores both as evidence, and
lets the scoring engine decide the points. Two independent analysers means a
single model's mistake cannot dominate the LISTING signal.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from trustlens.core.application.services.listing_publication import (
    SAFE_LISTING_RISK_LIMIT,
    listing_media_missing,
    seller_can_publish,
)
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
        # A seller can save and analyse a draft, but analysis alone is never
        # permission to publish. Re-read both rows inside the write transaction
        # so a verification decision arriving during analysis is respected.
        current = await uow.listings.get(lid)
        if current is None or current.status in {
            ListingStatus.REMOVED, ListingStatus.EXPIRED, ListingStatus.SOLD
        }:
            return {"skipped": "listing is no longer publishable"}
        if (current.title, current.description, current.price, current.category_node_id, current.category_data, current.attributes, current.condition, current.video_file_id) != (
            listing.title, listing.description, listing.price, listing.category_node_id, listing.category_data, listing.attributes, listing.condition, listing.video_file_id
        ):
            return {"skipped": "listing changed during analysis"}
        seller = await uow.sellers.get(current.seller_id)
        # Becoming ACTIVE needs BOTH a verified seller and a complete ad
        # (photo + video + map location). Anything else stays a private draft.
        media_missing = listing_media_missing(
            current, await uow.listings.count_images(current.id)
        )
        permitted = seller is not None and seller_can_publish(seller) and not media_missing
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
        target = (
            ListingStatus.FLAGGED
            if combined_risk >= SAFE_LISTING_RISK_LIMIT
            else ListingStatus.RESERVED
            if current.status == ListingStatus.RESERVED
            else ListingStatus.ACTIVE if permitted else ListingStatus.DRAFT
        )
        changed = await uow.listings.set_publication_status_if_current(
            current.id,
            from_status=current.status,
            to_status=target,
            expected_version=current.version,
            expected_analysis_id=analysis.id,
            at=now,
        )
        if not changed:
            # add_analysis repointed latest_analysis_id inside this transaction.
            # Discard it rather than saving a verdict for a newer seller edit.
            await uow.rollback()
            return {"skipped": "listing changed during analysis"}
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
