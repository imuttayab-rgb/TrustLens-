"""The buyer-facing score read (P0-12).

The public seller page is the screen the whole product is judged on, and it is
read by anonymous buyers following a link in a WhatsApp or marketplace chat.
It therefore needs a door of its own.

**Why not the partner API.** `/public/v1` is the marketplace integration
surface: it requires an API key, meters usage against a monthly quota, signs
its responses, and fails closed when Redis is unavailable. Every one of those
is right for a partner and wrong here. Giving `apps/web` a partner key would
put the most visible screen in the product on the same credential path as
third parties, so revoking a leaked partner key, or exhausting a quota, would
take the buyer page down with it.

**Why not a new projection.** The payload comes from the same
`GetPublicTrustScore` use case and the same `PublicScoreResponse` model as the
partner API, so the "no PII in a public response" guarantee is inherited
rather than re-implemented. A second hand-rolled projection is exactly how a
seller's email address eventually ends up on a public page.

Three deliberate differences from the partner route:

* **Rate limited by IP, and fails OPEN.** The partner API refuses traffic when
  Redis is down because the alternative is uncontrolled cost. Here the
  alternative is a blank product page, so a Redis blip degrades the limit, not
  the page.
* **Not signed.** An HMAC signature is a guarantee for a recipient who checks
  it. A browser does not, and cannot hold the secret needed to.
* **Not written to `api_request_logs`.** That table is partner usage
  accounting and is keyed by an API key id, of which this route has none.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Any

from fastapi import APIRouter, Header, Response, status

from trustlens.core.application.use_cases.scoring import (
    GetPublicTrustScore,
    GetPublicTrustScoreCommand,
)
from trustlens.core.domain.errors import RateLimitExceeded
from trustlens.shared.logging import get_logger
from trustlens_api.api.deps import ContainerDep, MetaDep, UowDep
from trustlens_api.api.public.v1.schemas.public_score import PublicScoreResponse
from trustlens_api.api.v1.schemas.common import envelope

log = get_logger(__name__)

router = APIRouter(tags=["Public Page"])


@router.get(
    "/public/sellers/{seller_ref}/trust-score",
    summary="Buyer-facing score for the public seller page (no auth)",
    description=(
        "Powers `/seller/{handle}` on the web app. Anonymous, PII-free, and "
        "rate limited per IP.\n\n"
        "Marketplaces integrating TrustLens should use `/public/v1` instead - "
        "it is versioned independently, signed, and comes with a quota."
    ),
)
async def get_public_trust_score(
    seller_ref: str,
    response: Response,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
) -> Any:
    await _throttle(container, meta)

    use_case = GetPublicTrustScore(
        uow=uow,
        cache=container.cache,
        clock=container.clock,
        queue=container.queue,
        cache_ttl_seconds=container.settings.redis.cache_ttl_score_seconds,
    )
    # An unknown handle raises EntityNotFound, which the problem+json handler
    # turns into a 404 - and the page renders its not-found state. That is the
    # correct answer for a handle nobody has enrolled, and it is the answer the
    # product's scope depends on: TrustLens scores enrolled sellers and says
    # "no record" for everyone else.
    payload, was_cached = await use_case.execute(GetPublicTrustScoreCommand(seller_ref=seller_ref))

    ttl = container.settings.redis.cache_ttl_score_seconds
    etag = f'W/"{hashlib.sha256(payload.to_json().encode()).hexdigest()[:32]}"'
    response.headers["Cache-Control"] = f"public, max-age={ttl}"
    response.headers["ETag"] = etag
    response.headers["X-Cache"] = "HIT" if was_cached else "MISS"

    if if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=dict(response.headers))

    body = PublicScoreResponse(
        seller_ref=payload.seller_ref,
        score=payload.score,
        risk_level=payload.risk_level,
        risk_label=payload.risk_label,
        confidence=payload.confidence,
        verifications=payload.verifications,
        reasons=[
            {"code": r.code, "impact": r.impact, "category": r.category, "text": r.text}
            for r in payload.reasons
        ],
        model_version=payload.model_version,
        computed_at=payload.computed_at,
        expires_at=payload.expires_at,
        unavailable_signals=payload.unavailable_signals,
        member_since=payload.member_since,
    )
    return envelope(body.model_dump(by_alias=True), request_id=meta.request_id, cached=was_cached)


async def _throttle(container: ContainerDep, meta: MetaDep) -> None:
    """Per-IP limit, failing open.

    Unlike the partner API this does not raise when the limiter itself is
    unavailable. The score being read here is already public and already
    cached; the cost of serving it unthrottled for the length of a Redis
    outage is far lower than the cost of the product's front page returning
    an error during a demo.
    """
    limits = container.settings.rate_limit
    if not limits.enabled or meta.ip is None:
        return

    try:
        allowed, _remaining, retry_after = await container.rate_limiter.hit(
            f"anon:score:{meta.ip}", limit=limits.anon_per_minute, window_seconds=60
        )
    except Exception:
        log.warning("anon_rate_limit_unavailable_failing_open", ip=meta.ip)
        return

    if not allowed:
        raise RateLimitExceeded(
            f"Rate limit of {limits.anon_per_minute} requests per minute exceeded.",
            retry_after=retry_after,
        )


__all__ = ["router"]
