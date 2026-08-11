"""Webhook delivery to partner marketplaces (P6-05).

A marketplace that has to poll every seller to notice a score change will
either poll too often (and burn its quota) or too rarely (and act on a stale
score). Webhooks are how a partner finds out that a seller they care about
became high-risk twenty seconds ago.

Two things make this safe to run unattended:

* **Every payload is signed** with the endpoint's own secret, using the same
  `t=<ts>,v1=<hmac>` scheme as the public API responses - so a partner writes
  one verification routine, and an attacker cannot forge a "score: 95" POST
  to an endpoint they discovered.
* **Failures back off and eventually stop.** The retry schedule and the
  decision of *what is worth retrying* live in `domain/policies/webhooks.py`,
  not here, because those are the rules a retry storm turns into an outage.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select, update

from trustlens.core.domain.enums import DeliveryStatus
from trustlens.core.domain.policies import (
    DELIVERY_TIMEOUT_SECONDS,
    RetryPolicy,
    is_success,
    should_retry,
)
from trustlens.db import models as m
from trustlens.shared.crypto import sign_webhook_payload, stable_json
from trustlens.shared.logging import get_logger

log = get_logger(__name__)

_RETRY = RetryPolicy()


async def deliver_webhook(ctx: dict[str, Any], *, delivery_id: str) -> dict[str, Any]:
    """Attempt one delivery, then schedule the next attempt or give up.

    One attempt per job run rather than a retry loop inside the job: a job
    that sleeps between retries holds a worker slot for the whole backoff
    window, and five partners having a bad afternoon would stall the queue.
    """
    now = ctx["clock"].now()
    session_factory = ctx["session_factory"]

    async with session_factory() as session:
        delivery = await session.get(m.WebhookDeliveryModel, UUID(delivery_id))
        if delivery is None:
            return {"delivered": False, "reason": "unknown_delivery"}
        if delivery.status is DeliveryStatus.DELIVERED:
            # Already done. The outbox relay is at-least-once, so a duplicate
            # job for a delivered row is expected rather than exceptional.
            return {"delivered": True, "reason": "already_delivered"}

        endpoint = await session.get(m.WebhookEndpointModel, delivery.webhook_endpoint_id)
        if endpoint is None or not endpoint.is_active:
            await session.execute(
                update(m.WebhookDeliveryModel)
                .where(m.WebhookDeliveryModel.id == delivery.id)
                .values(status=DeliveryStatus.FAILED, next_retry_at=None)
            )
            await session.commit()
            return {"delivered": False, "reason": "endpoint_inactive"}

        body = stable_json(delivery.payload).encode()
        timestamp = int(now.timestamp())

        secret = b""
        if endpoint.secret_encrypted:
            # Decrypted only here, only for the moment it is needed.
            secret = ctx["encryptor"].decrypt(endpoint.secret_encrypted.decode()).encode()

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "TrustLens-Webhook/1",
            "X-TrustLens-Event": delivery.event_type.value,
            "X-TrustLens-Delivery": str(delivery.id),
        }
        if secret:
            headers["X-TrustLens-Signature"] = sign_webhook_payload(secret, body, timestamp)

        status_code: int | None = None
        try:
            async with httpx.AsyncClient(timeout=DELIVERY_TIMEOUT_SECONDS) as client:
                response = await client.post(endpoint.url, content=body, headers=headers)
            status_code = response.status_code
        except Exception as exc:
            # No status at all: a timeout, DNS failure or refused connection.
            # The most retryable case there is, so it is recorded as such
            # rather than swallowed.
            log.warning(
                "webhook_transport_failed",
                delivery_id=str(delivery.id),
                url=endpoint.url,
                error=type(exc).__name__,
            )

        attempts = delivery.attempt_count + 1

        if is_success(status_code):
            await session.execute(
                update(m.WebhookDeliveryModel)
                .where(m.WebhookDeliveryModel.id == delivery.id)
                .values(
                    status=DeliveryStatus.DELIVERED,
                    attempt_count=attempts,
                    response_status=status_code,
                    next_retry_at=None,
                )
            )
            await session.commit()
            return {"delivered": True, "status": status_code, "attempts": attempts}

        retryable = should_retry(status_code)
        next_at = _RETRY.next_retry_at(attempt=attempts, now=now) if retryable else None

        if next_at is None:
            # EXHAUSTED rather than FAILED when the attempts ran out: an
            # operator needs to tell "this partner is refusing us" apart from
            # "we stopped trying", and only one of those is worth chasing.
            final = DeliveryStatus.EXHAUSTED if retryable else DeliveryStatus.FAILED
            await session.execute(
                update(m.WebhookDeliveryModel)
                .where(m.WebhookDeliveryModel.id == delivery.id)
                .values(
                    status=final,
                    attempt_count=attempts,
                    response_status=status_code,
                    next_retry_at=None,
                )
            )
            await session.commit()
            log.warning(
                "webhook_giving_up",
                delivery_id=str(delivery.id),
                status=final.value,
                response_status=status_code,
                attempts=attempts,
            )
            return {"delivered": False, "status": status_code, "final": final.value}

        await session.execute(
            update(m.WebhookDeliveryModel)
            .where(m.WebhookDeliveryModel.id == delivery.id)
            .values(
                status=DeliveryStatus.PENDING,
                attempt_count=attempts,
                response_status=status_code,
                next_retry_at=next_at,
            )
        )
        await session.commit()

    # Enqueued after the commit: a retry that runs before this transaction
    # lands would read the previous attempt count and back off wrongly.
    await ctx["queue"].enqueue(
        "webhooks.deliver", delivery_id=str(delivery_id), _defer_until=next_at
    )
    return {"delivered": False, "status": status_code, "retry_at": next_at.isoformat()}


async def retry_pending_webhooks(ctx: dict[str, Any], *, batch: int = 100) -> dict[str, Any]:
    """Sweep deliveries whose retry time has come.

    A safety net, not the primary path: `deliver_webhook` schedules its own
    next attempt. This catches the ones whose follow-up job was lost - a
    worker killed mid-flight, a Redis restart - which is exactly when a
    partner most needs the event.
    """
    now = ctx["clock"].now()
    requeued = 0

    async with ctx["session_factory"]() as session:
        rows = (
            (
                await session.execute(
                    select(m.WebhookDeliveryModel)
                    .where(
                        m.WebhookDeliveryModel.status == DeliveryStatus.PENDING,
                        m.WebhookDeliveryModel.next_retry_at.is_not(None),
                        m.WebhookDeliveryModel.next_retry_at <= now,
                    )
                    .order_by(m.WebhookDeliveryModel.next_retry_at)
                    .limit(batch)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )

        for delivery in rows:
            await ctx["queue"].enqueue("webhooks.deliver", delivery_id=str(delivery.id))
            requeued += 1

        await session.commit()

    return {"requeued": requeued}


__all__ = ["deliver_webhook", "retry_pending_webhooks"]
