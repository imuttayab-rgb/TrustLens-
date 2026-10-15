"""Enrichment and housekeeping jobs."""

from __future__ import annotations

import dataclasses
from typing import Any
from uuid import UUID

from trustlens.core.domain.enums import WebhookEvent
from trustlens.shared.logging import get_logger

log = get_logger(__name__)

#: Domain event name -> the public webhook event partners subscribe to.
#: See `_fan_out_to_webhooks` for why this is a map and not a conversion.
_WEBHOOK_EVENTS: dict[str, WebhookEvent] = {
    "trust_score.computed": WebhookEvent.SCORE_UPDATED,
    "trust_score.overridden": WebhookEvent.SCORE_UPDATED,
    "identity.verified": WebhookEvent.SELLER_VERIFIED,
    "seller.flagged": WebhookEvent.SELLER_FLAGGED,
    "appeal.resolved": WebhookEvent.APPEAL_RESOLVED,
}


async def enrich_ip(ctx: dict[str, Any], *, ip: str) -> dict[str, Any]:
    """Look up an IP's reputation and cache it.

    Cached for a day: the lookup is metered, and an IP's reputation does not
    change minute to minute.
    """
    cache_key = f"ipintel:{ip}"
    if await ctx["cache"].exists(cache_key):
        return {"cached": True}

    reputation = await ctx["ip_intel"].lookup(ip)
    uow = ctx["uow"]()
    async with uow:
        await uow.devices.upsert_ip_reputation(reputation)
        await uow.commit()

    await ctx["cache"].set(
        cache_key, "1", ttl_seconds=ctx["settings"].ip_intel.ip_intel_cache_ttl_seconds
    )
    return {
        "is_vpn": reputation.is_vpn,
        "country": reputation.country_code,
        "provider": reputation.provider,
    }


async def lookup_phone(ctx: dict[str, Any], *, phone_number_id: str) -> dict[str, Any]:
    """Carrier / line-type lookup - the VOIP half of the PHONE signal.

    Separate from OTP verification so the seller sees their number confirmed
    immediately rather than waiting on a third-party call.
    """
    uow = ctx["uow"]()
    async with uow:
        phone = await uow.phone_numbers.get(UUID(phone_number_id))
        if phone is None:
            return {"skipped": "phone not found"}

        provider = ctx["settings"].ip_intel.phone_lookup_provider
        if provider == "none":
            # No provider configured. Leave line_type UNKNOWN so the collector
            # reports UNAVAILABLE rather than inventing a verdict.
            return {"skipped": "no phone lookup provider configured"}

        await uow.phone_numbers.update(dataclasses.replace(phone, lookup_at=ctx["clock"].now()))
        await uow.commit()

    return {"looked_up": True}


async def purge_expired_media(ctx: dict[str, Any]) -> dict[str, Any]:
    """Delete identity images past their retention window.

    Derived data - the CNIC blind index, the face similarity, the score
    breakdown - is deliberately NOT deleted, so an old score stays explainable
    after the raw documents are gone (docs/02 section 7).
    """
    now = ctx["clock"].now()
    uow = ctx["uow"]()
    purged = 0

    async with uow:
        expired = await uow.files.list_expired(before=now, limit=500)

    for file in expired:
        try:
            await ctx["storage"].delete(bucket=file.bucket, object_key=file.object_key)
        except Exception as exc:
            log.warning("purge_object_failed", file_id=str(file.id), error=str(exc))
            continue
        async with uow:
            await uow.files.mark_deleted(file.id, at=now)
            await uow.commit()
        purged += 1

    if purged:
        log.info("media_purged", count=purged)
    return {"purged": purged}


async def purge_account(ctx: dict[str, Any], *, user_id: str) -> dict[str, Any]:
    """Legacy jobs must not report an erasure that was never performed."""
    log.info("account_erasure_requires_review", user_id=user_id)
    return {"purged": False, "status": "REQUIRES_REVIEW"}


async def publish_outbox(ctx: dict[str, Any], *, batch: int = 100) -> dict[str, Any]:
    """Relay the transactional outbox.

    Events were written in the same transaction as the state change, so this
    poller can safely assume every row it sees corresponds to a committed
    change - which is exactly the guarantee an at-least-once publisher needs.
    """
    from sqlalchemy import select, update

    from trustlens.db import models as m

    now = ctx["clock"].now()
    published = 0
    queued: list[UUID] = []

    async with ctx["session_factory"]() as session:
        rows = (
            (
                await session.execute(
                    select(m.OutboxEvent)
                    .where(m.OutboxEvent.published_at.is_(None))
                    .order_by(m.OutboxEvent.occurred_at)
                    .limit(batch)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )

        for event in rows:
            deliveries = await _fan_out_to_webhooks(session, event, ctx)
            queued.extend(deliveries)
            log.info(
                "outbox_event_published",
                event_type=event.event_type,
                aggregate=event.aggregate_type,
                webhook_deliveries=len(deliveries),
            )
            # Marked published in the SAME transaction as the delivery rows,
            # so the relay is at-least-once rather than at-most-once: a crash
            # here replays the event, it does not lose it.
            await session.execute(
                update(m.OutboxEvent)
                .where(m.OutboxEvent.id == event.id)
                .values(published_at=now, attempts=m.OutboxEvent.attempts + 1)
            )
            published += 1

        await session.commit()

    # Enqueued only after the commit. A delivery job that started before the
    # row it references was visible would look up nothing and drop the event.
    for delivery_id in queued:
        await ctx["queue"].enqueue("webhooks.deliver", delivery_id=str(delivery_id))

    return {"published": published, "webhooks_queued": len(queued)}


async def _fan_out_to_webhooks(session: Any, event: Any, ctx: dict[str, Any]) -> list[UUID]:
    """Create a delivery row per subscribed endpoint. Returns their ids.

    Rows are written inside the caller's transaction, alongside the outbox row
    being marked published, so "the event was published but nobody was told"
    cannot happen. Actually sending them is a separate job.
    """
    from sqlalchemy import func, literal, select

    from trustlens.db import models as m

    # Internal event name -> the public event a partner subscribes to. The two
    # vocabularies are deliberately separate: `trust_score.computed` is what
    # the domain calls it, `SCORE_UPDATED` is what a marketplace integrates
    # against, and renaming a domain event must not silently break partners.
    #
    # Anything absent from this map is internal-only and fans out to nobody,
    # which is why it is an explicit mapping rather than a name conversion -
    # a conversion would have matched nothing at all and failed silently.
    webhook_event = _WEBHOOK_EVENTS.get(event.event_type)
    if webhook_event is None:
        return []

    endpoints = (
        (
            await session.execute(
                select(m.WebhookEndpointModel).where(
                    m.WebhookEndpointModel.is_active.is_(True),
                    m.WebhookEndpointModel.deleted_at.is_(None),
                    # `events` is mapped as the generic ARRAY, whose
                    # `.contains()` raises NotImplementedError - the operator
                    # belongs to the postgresql dialect type. Comparing against
                    # an explicit text[] literal keeps the containment check in
                    # the database (so an index can serve it) without depending
                    # on how the column happens to be mapped.
                    literal(webhook_event.value) == func.any(m.WebhookEndpointModel.events),
                )
            )
        )
        .scalars()
        .all()
    )

    created: list[UUID] = []
    for endpoint in endpoints:
        delivery_id = ctx["ids"].new()
        session.add(
            m.WebhookDeliveryModel(
                id=delivery_id,
                webhook_endpoint_id=endpoint.id,
                event_type=webhook_event,
                payload=event.payload,
            )
        )
        created.append(delivery_id)

    if created:
        await session.flush()
    return created


async def expire_lapsed_identities(ctx: dict[str, Any]) -> dict[str, Any]:
    """Daily: a VERIFIED seller whose card (real OCR) has expired -> EXPIRED.

    Their live listings go back to private drafts until they re-verify with
    a renewed card. Fake/demo OCR dates are never used. Logs counts only -
    never a date, CNIC number or name.
    """
    from trustlens.core.application.use_cases.verification.identity_expiry import (
        ExpireLapsedIdentities,
    )

    result = await ExpireLapsedIdentities(
        uow=ctx["uow"](), queue=ctx["queue"], clock=ctx["clock"], ids=ctx["ids"]
    ).execute()
    log.info(
        "identity_expiry_sweep",
        checked=result.checked,
        expired=result.expired,
        listings_withheld=result.listings_withheld,
    )
    return {
        "checked": result.checked,
        "expired": result.expired,
        "listings_withheld": result.listings_withheld,
    }


__all__ = [
    "enrich_ip",
    "expire_lapsed_identities",
    "lookup_phone",
    "publish_outbox",
    "purge_account",
    "purge_expired_media",
]
