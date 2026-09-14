"""Auction close-out sweep (feature AUC-01)."""

from __future__ import annotations

from typing import Any

from trustlens.core.application.use_cases.commerce import CloseAuction
from trustlens.shared.logging import get_logger

log = get_logger(__name__)


async def close_ended_auctions(ctx: dict[str, Any]) -> dict[str, Any]:
    """Every few minutes, close any auction whose `ends_at` has passed.

    `CloseAuction` itself is idempotent (a second call on an already-closed
    auction is a no-op), so a worker restart mid-sweep or two overlapping
    runs can't double-settle one.
    """
    now = ctx["clock"].now()
    uow = ctx["uow"]()
    async with uow:
        ended = await uow.auctions.list_ending_before(now, limit=200)

    closed = 0
    for auction in ended:
        try:
            await CloseAuction(uow=uow, clock=ctx["clock"], ids=ctx["ids"]).execute(auction.id)
            closed += 1
        except Exception as exc:
            log.warning("auction_close_failed", auction_id=str(auction.id), error=str(exc))
            continue

    if closed:
        log.info("auctions_closed", count=closed)
    return {"closed": closed}


__all__ = ["close_ended_auctions"]
