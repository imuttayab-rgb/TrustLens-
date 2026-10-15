"""Shopping AI uses its own flags and free-provider keys, never verification AI."""

from __future__ import annotations

from typing import Literal
import asyncio

import httpx
from fastapi import APIRouter, HTTPException, Query

from trustlens.core.domain.value_objects.listing_category import LISTING_CATEGORIES
from trustlens.core.domain.errors import EntityNotFound
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep
from trustlens_api.api.v1.schemas.common import Envelope, envelope
from trustlens_api.assistant.contracts import (
    AssistantStatus,
    ChatReply,
    ChatRequest,
    DescriptionReply,
    DescriptionRequest,
    EnhanceRequest,
    EnhanceReply,
    ListingResults,
    ProductResearchRequest,
    ResearchReply,
    SearchFilters,
    SuggestionsReply,
)
from trustlens_api.assistant.provider import AssistantConfig, AssistantUnavailable, AssistantRateLimited
from trustlens_api.assistant.enhance import enhance
from trustlens_api.assistant.service import AssistantService

router = APIRouter(prefix="/assistant", tags=["Shopping Assistant"])


async def throttle(container: ContainerDep, meta: MetaDep, *, ai: bool = False) -> None:
    limit = AssistantConfig.from_env().per_minute if ai else 60
    try:
        allowed, _, retry = await container.rate_limiter.hit(
            f"assistant:{'ai' if ai else 'read'}:{meta.ip or 'unknown'}",
            limit=limit,
            window_seconds=60,
        )
    except Exception as exc:
        raise HTTPException(
            503, "The assistant is temporarily unavailable. Ordinary listing search still works."
        ) from exc
    if not allowed:
        raise HTTPException(
            429, "Please wait a moment before trying again.", headers={"Retry-After": str(retry)}
        )


def unavailable(exc: AssistantUnavailable) -> HTTPException:
    if isinstance(exc, AssistantRateLimited):
        return HTTPException(429, str(exc), headers={"Retry-After": str(exc.retry_after)})
    return HTTPException(status_code=503, detail=str(exc))


@router.get("/status", response_model=Envelope[AssistantStatus])
async def status(container: ContainerDep, meta: MetaDep):
    await throttle(container, meta)
    config = AssistantConfig.from_env()
    return envelope(
        AssistantStatus(
            ready=config.ready, web_ready=config.ready and bool(config.search_key)
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post("/chat", response_model=Envelope[ChatReply])
async def chat(body: ChatRequest, container: ContainerDep, meta: MetaDep):
    await throttle(container, meta, ai=True)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(45, connect=10), follow_redirects=False
    ) as client:
        try:
            result = await AssistantService(container, client).chat(body)
        except AssistantUnavailable as exc:
            raise unavailable(exc) from exc
    return envelope(result.model_dump(by_alias=True), request_id=meta.request_id)


@router.post("/listings", response_model=Envelope[ListingResults])
async def listings(body: SearchFilters, container: ContainerDep, meta: MetaDep):
    await throttle(container, meta)
    async with httpx.AsyncClient() as client:
        result, _ = await AssistantService(container, client).listings(body)
    return envelope(result.model_dump(by_alias=True), request_id=meta.request_id)


@router.get("/suggestions", response_model=Envelope[SuggestionsReply])
async def suggestions(
    container: ContainerDep,
    meta: MetaDep,
    q: str = Query(default="", max_length=80),
    category: str | None = Query(default=None, max_length=80),
    city: str | None = Query(default=None, max_length=80),
    mode: Literal["buyer", "seller"] = "buyer",
    offset: int = Query(default=0, ge=0, le=5000),
    limit: int = Query(default=10, ge=1, le=20),
):
    await throttle(container, meta)
    if category and category not in LISTING_CATEGORIES:
        raise HTTPException(422, "Choose a supported category.")
    async with httpx.AsyncClient() as client:
        result = await AssistantService(container, client).suggestions(
            q.strip(), category, city, seller=mode == "seller", offset=offset, limit=limit
        )
    return envelope(result.model_dump(by_alias=True), request_id=meta.request_id)


@router.post("/description", response_model=Envelope[DescriptionReply])
async def description(
    body: DescriptionRequest, actor: ActorDep, container: ContainerDep, meta: MetaDep
):
    await throttle(container, meta, ai=True)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(45, connect=10), follow_redirects=False
    ) as client:
        try:
            result = await AssistantService(container, client).describe(body)
        except AssistantUnavailable as exc:
            raise unavailable(exc) from exc
    return envelope(result.model_dump(by_alias=True), request_id=meta.request_id)


@router.post("/research", response_model=Envelope[ResearchReply])
async def research(
    body: ProductResearchRequest, actor: ActorDep, container: ContainerDep, meta: MetaDep
):
    await throttle(container, meta, ai=True)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(45, connect=10), follow_redirects=False
    ) as client:
        try:
            result = await AssistantService(container, client).research(body)
        except AssistantUnavailable as exc:
            raise unavailable(exc) from exc
    return envelope(result.model_dump(by_alias=True), request_id=meta.request_id)


@router.post("/enhance", response_model=Envelope[EnhanceReply])
async def enhance_description(
    body: EnhanceRequest, actor: ActorDep, container: ContainerDep, meta: MetaDep
):
    # One explicit action uses one local request slot. No changes to configured limits.
    await throttle(container, meta, ai=True)
    # Do not hold a database connection during slow model/search requests.
    async with container.uow() as uow:
        seller = await uow.sellers.get_by_user(actor.user_id)
        if seller is None:
            raise EntityNotFound("seller_profile", actor.user_id)
    async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=10), follow_redirects=False) as client:
        try:
            async with asyncio.timeout(85):
                result = await enhance(AssistantService(container, client), body, seller)
        except AssistantUnavailable as exc:
            raise unavailable(exc) from exc
        except TimeoutError as exc:
            raise HTTPException(503, "AI took too long. Your text and features are unchanged. Please try again.") from exc
    return envelope(result.model_dump(by_alias=True), request_id=meta.request_id)
