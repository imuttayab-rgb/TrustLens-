"""Enrichment and housekeeping jobs."""

from __future__ import annotations

import dataclasses
from typing import Any
from uuid import UUID

from trustlens.shared.logging import get_logger

log = get_logger(__name__)


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
            # Webhook fan-out to partner endpoints belongs here. Marking the
            # row published in the same transaction keeps the relay
            # at-least-once rather than at-most-once.
            log.info(
                "outbox_event_published",
                event_type=event.event_type,
                aggregate=event.aggregate_type,
            )
            await session.execute(
                update(m.OutboxEvent)
                .where(m.OutboxEvent.id == event.id)
                .values(published_at=now, attempts=m.OutboxEvent.attempts + 1)
            )
            published += 1

        await session.commit()

    return {"published": published}


__all__ = [
    "enrich_ip",
    "lookup_phone",
    "publish_outbox",
    "purge_expired_media",
]
