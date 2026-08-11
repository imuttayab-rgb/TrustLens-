"""Public Trust Score API (feature F8).

Separate from the internal API on purpose (docs/06 section 1): a distinct
router tree with its own schemas makes "no PII in the public API" a
*structural* property - the response model simply has no such field - rather
than a review checklist item somebody eventually forgets.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Header, Request, Response
from pydantic import BaseModel

from trustlens.core.application.use_cases.scoring import (
    GetPublicTrustScore,
    GetPublicTrustScoreCommand,
)
from trustlens.core.domain.errors import EntityNotFound, QuotaExceeded, RateLimitExceeded
from trustlens.db.unit_of_work import SqlAlchemyUnitOfWork
from trustlens_api.api.deps import (
    ApiClientDep,
    ApiClientPrincipal,
    ContainerDep,
    MetaDep,
    RequestMeta,
    UowDep,
    require_scope,
)
from trustlens_api.api.public.v1.schemas.public_score import (
    BatchLookupRequest,
    BatchLookupResponse,
    PublicScoreResponse,
    PublicStatusResponse,
)
from trustlens_api.container import Container

router = APIRouter(tags=["Public API"])

MAX_BATCH = 50


@router.get(
    "/sellers/{seller_ref}/trust-score",
    response_model=PublicScoreResponse,
    summary="Get a seller's trust score",
    description=(
        "`seller_ref` may be a TrustLens id, a handle, or "
        "`{marketplaceSlug}:{yourSellerId}` if you registered the seller "
        "through this API.\n\n"
        "Responses are cached for 5 minutes and carry an ETag. Scores change "
        "rarely, so a well-behaved client polling this endpoint costs one "
        "Redis read."
    ),
    dependencies=[Depends(require_scope("score:read"))],
)
async def get_trust_score(
    seller_ref: str,
    request: Request,
    response: Response,
    principal: ApiClientDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
) -> PublicScoreResponse | Response:
    started = time.perf_counter()
    await _enforce_quota(principal, container, uow)

    use_case = GetPublicTrustScore(
        uow=uow,
        cache=container.cache,
        clock=container.clock,
        queue=container.queue,
        cache_ttl_seconds=container.settings.redis.cache_ttl_score_seconds,
    )

    try:
        payload, was_cached = await use_case.execute(
            GetPublicTrustScoreCommand(seller_ref=seller_ref)
        )
    except EntityNotFound:
        await _log_request(request, principal, container, uow, meta, 404, started, "NOT_FOUND")
        raise

    etag = f'W/"{hashlib.sha256(payload.to_json().encode()).hexdigest()[:32]}"'
    response.headers["Cache-Control"] = (
        f"public, max-age={container.settings.redis.cache_ttl_score_seconds}"
    )
    response.headers["ETag"] = etag
    response.headers["X-Cache"] = "HIT" if was_cached else "MISS"

    await _log_request(request, principal, container, uow, meta, 200, started, None)

    if if_none_match == etag:
        return Response(status_code=304, headers=dict(response.headers))

    body = PublicScoreResponse(
        seller_ref=payload.seller_ref,
        score=payload.score,
        risk_level=payload.risk_level,
        risk_label=payload.risk_label,
        confidence=payload.confidence,
        verifications=payload.verifications,
        reasons=[{"code": r.code, "impact": r.impact, "text": r.text} for r in payload.reasons],
        model_version=payload.model_version,
        computed_at=payload.computed_at,
        expires_at=payload.expires_at,
        unavailable_signals=payload.unavailable_signals,
    )
    return _signed(body, response, container, meta)


@router.post(
    "/sellers/lookup",
    response_model=BatchLookupResponse,
    summary="Look up several sellers at once",
    description=f"Up to {MAX_BATCH} references per request.",
    dependencies=[Depends(require_scope("score:read"))],
)
async def batch_lookup(
    request: Request,
    response: Response,
    principal: ApiClientDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    body: Annotated[BatchLookupRequest, Body()],
) -> Response:
    started = time.perf_counter()
    await _enforce_quota(principal, container, uow)

    use_case = GetPublicTrustScore(
        uow=uow,
        cache=container.cache,
        clock=container.clock,
        queue=container.queue,
        cache_ttl_seconds=container.settings.redis.cache_ttl_score_seconds,
    )

    found: list[dict[str, Any]] = []
    missing: list[str] = []
    for ref in body.seller_refs[:MAX_BATCH]:
        try:
            payload, _ = await use_case.execute(GetPublicTrustScoreCommand(seller_ref=ref))
        except EntityNotFound:
            missing.append(ref)
            continue
        found.append(
            {
                "sellerRef": payload.seller_ref,
                "score": payload.score,
                "riskLevel": payload.risk_level,
                "confidence": payload.confidence,
                "computedAt": payload.computed_at,
            }
        )

    await _log_request(request, principal, container, uow, meta, 200, started, None)
    return _signed(BatchLookupResponse(results=found, not_found=missing), response, container, meta)


@router.get(
    "/status",
    response_model=PublicStatusResponse,
    summary="Service status and current scoring model",
    description="No authentication required. Useful as an integration smoke test.",
)
async def public_status(container: ContainerDep, uow: UowDep) -> PublicStatusResponse:
    model = await uow.scoring_models.get_active()
    return PublicStatusResponse(
        status="ok",
        scoring_model_version=model.version if model else "none",
        api_version="v1",
    )


# ── helpers ──────────────────────────────────────────────────────────


def _signed(
    body: BaseModel,
    response: Response,
    container: Container,
    meta: RequestMeta,
) -> Response:
    """Serialise once and sign those exact bytes (P6-04).

    A Trust Score is a claim about a person that money moves on, and a partner
    receiving one through a proxy or a cache it does not control cannot
    otherwise tell it apart from a score an attacker wrote.

    The response is built here rather than returned as a model because the
    signature has to cover the bytes actually served. Letting FastAPI
    serialise afterwards would sign one encoding and send another, and the
    partner's verification would fail for reasons nobody could reproduce.

    Unsigned when no secret is configured: an unsigned score is still a usable
    score, and refusing to serve one would make signing a boot requirement
    rather than an integrity guarantee.
    """
    payload = body.model_dump(by_alias=True, mode="json")
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()

    headers = dict(response.headers)
    signer = container.response_signer
    if signer is not None:
        timestamp = int(container.clock.now().timestamp())
        headers["X-TrustLens-Signature"] = signer.sign(raw, timestamp=timestamp)
        headers["X-TrustLens-Key-Id"] = signer.key_id
    if meta.request_id:
        headers["X-Request-Id"] = meta.request_id

    return Response(content=raw, media_type="application/json", headers=headers)


async def _enforce_quota(
    principal: ApiClientPrincipal, container: Container, uow: SqlAlchemyUnitOfWork
) -> None:
    """Per-minute rate limit and monthly quota.

    The public API fails CLOSED when Redis is unavailable: for a partner-facing
    endpoint, refusing traffic is safer than silently removing the only control
    on cost and abuse.
    """
    limits = container.settings.rate_limit
    if not limits.enabled:
        return

    per_minute = (
        limits.public_api_partner_per_minute
        if principal.rate_limit_tier == "partner"
        else limits.public_api_free_per_minute
    )

    try:
        allowed, _remaining, retry_after = await container.rate_limiter.hit(
            f"apikey:{principal.key_id}", limit=per_minute, window_seconds=60
        )
    except Exception:
        if limits.fail_mode == "closed":
            raise RateLimitExceeded(
                "Rate limiting is unavailable; requests are temporarily refused.",
                retry_after=30,
            ) from None
        return

    if not allowed:
        raise RateLimitExceeded(
            f"Rate limit of {per_minute} requests per minute exceeded.",
            retry_after=retry_after,
        )

    used = await uow.api_clients.usage_this_month(principal.client_id)
    if used >= principal.monthly_quota:
        raise QuotaExceeded(
            f"Monthly quota of {principal.monthly_quota} requests exceeded.",
            retry_after=86_400,
        )


async def _log_request(
    request: Request,
    principal: ApiClientPrincipal,
    container: Container,
    uow: SqlAlchemyUnitOfWork,
    meta: RequestMeta,
    status_code: int,
    started: float,
    error_code: str | None,
) -> None:
    """Append to `api_request_logs`.

    Never blocks the response path on a failure - usage analytics must not be
    able to take down the endpoint they measure.
    """
    try:
        await uow.api_clients.log_request(
            api_key_id=principal.key_id,
            api_client_id=principal.client_id,
            method=request.method,
            path=request.url.path[:255],
            status_code=status_code,
            latency_ms=int((time.perf_counter() - started) * 1000),
            ip=meta.ip,
            user_agent=meta.user_agent,
            request_id=meta.request_id,
            error_code=error_code,
            occurred_at=container.clock.now(),
        )
        await uow.api_clients.touch_key(principal.key_id, at=container.clock.now(), ip=meta.ip)
        await uow.commit()
    except Exception:  # noqa: S110
        pass


__all__ = ["router"]
