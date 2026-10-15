"""Application orchestration: live public inventory, bounded research, drafting."""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import ValidationError

from trustlens.core.application.use_cases.listings import (
    BrowsePublicListings,
    BrowsePublicListingsQuery,
    GetPublicListing,
)
from trustlens.core.domain.errors import EntityNotFound
from trustlens.core.domain.value_objects.listing_category import LISTING_CATEGORIES
from trustlens_api.api.v1.routers._public_listing_presentation import thumbnail_url

from . import prompts
from .catalogue import (
    FIELDS,
    PRIVATE_KEYS,
    explicit_budget,
    public_text,
    safe_facts,
    safe_url,
    search_terms,
)
from .contracts import (
    ChatReply,
    ChatRequest,
    DescriptionReply,
    DescriptionRequest,
    ListingCard,
    ListingResults,
    MarketOption,
    ProductResearchRequest,
    ResearchReply,
    SearchFilters,
    SearchPlan,
    SourcedSpec,
    Suggestion,
    SuggestionsReply,
    WebSource,
)
from .provider import AssistantConfig, AssistantUnavailable, GroqProvider, request_json


def merge_filters(previous: SearchFilters, planned: SearchFilters, message: str) -> SearchFilters:
    values = planned.model_dump()
    for key in ("category", "city", "condition", "q"):
        if values[key] is None:
            values[key] = getattr(previous, key)
    if previous.category and values["category"] != previous.category:
        values["q"] = planned.q
    # Monetary bounds survive model errors and preference follow-ups.
    budget = explicit_budget(message)
    if budget is not None:
        values["max_price"] = budget
    elif previous.max_price is not None:
        values["max_price"] = previous.max_price
    if previous.min_price is not None:
        values["min_price"] = previous.min_price
    if (
        values["min_price"] is not None
        and values["max_price"] is not None
        and values["min_price"] > values["max_price"]
    ):
        values["min_price"] = None
    values["offset"] = 0
    return SearchFilters.model_validate(values)


def basic_filters(message: str, previous: SearchFilters) -> SearchFilters:
    """Useful catalog navigation when no model is available; never pretends to be AI."""
    data = previous.model_dump()
    q = message.casefold()
    groups = [
        ("mobiles", ("phone", "mobile", "iphone", "samsung", "موبائل")),
        ("home-appliances", ("washing", "fridge", "refrigerator", "machine", "واشنگ")),
        ("electronics", ("ps5", "playstation", "xbox", "camera", "console", "television")),
        ("computers", ("laptop", "computer", "macbook", "gaming pc")),
        ("vehicles", ("car", "gari", "bike", "motorcycle", "civic", "corolla", "گاڑی")),
        ("furniture", ("sofa", "furniture", "wardrobe", "bed")),
        ("property-rent", ("rent", "kiraya", "کرایہ")),
        ("property-sale", ("property", "plot", "house", "مکان")),
    ]
    for category, words in groups:
        if any(w in q for w in words):
            data.update(category=category, q=None)
            break
    for city in (
        "Lahore",
        "Karachi",
        "Islamabad",
        "Rawalpindi",
        "Multan",
        "Faisalabad",
        "Peshawar",
        "Quetta",
    ):
        if city.casefold() in q:
            data["city"] = city
    if "washing" in q:
        data["q"] = "washing"
    if "iphone" in q:
        data["q"] = "iPhone"
    if "samsung" in q:
        data["q"] = "Samsung"
    if "ps5" in q:
        data["q"] = "PS5"
    if re.search(r"\bused\b", q):
        data["condition"] = "USED"
    return merge_filters(previous, SearchFilters.model_validate(data), message)


def eligible(detail: Any, filters: SearchFilters) -> bool:
    if detail.status != "ACTIVE":
        return False
    if filters.category and detail.category != filters.category:
        return False
    if filters.condition and detail.condition != filters.condition:
        return False
    if filters.city and (detail.city or "").casefold() != filters.city.casefold():
        return False
    if filters.min_price is not None or filters.max_price is not None:
        if detail.price is None or detail.currency != "PKR":
            return False
        if filters.min_price is not None and detail.price < filters.min_price:
            return False
        if filters.max_price is not None and detail.price > filters.max_price:
            return False
    return True


class AssistantService:
    def __init__(
        self, container: Any, client: httpx.AsyncClient, config: AssistantConfig | None = None
    ) -> None:
        self.container = container
        self.config = config or AssistantConfig.from_env()
        self.client = client
        self.provider = GroqProvider(self.config, client)

    async def model(
        self, prompt: str, data: dict[str, Any], *, tokens: int = 1800
    ) -> dict[str, Any]:
        if not self.config.ready:
            raise AssistantUnavailable("AI is not connected yet. You can still search listings.")
        await self.allowance(
            "model", self.config.daily_requests, datetime.now(UTC).strftime("%Y-%m-%d"), 172800
        )
        return await self.provider.complete(prompt, data, tokens=tokens)

    async def allowance(self, kind: str, limit: int, period: str, ttl: int) -> None:
        try:
            count = await self.container.cache.incr(
                f"assistant:v1:{kind}:{period}", ttl_seconds=ttl
            )
        except Exception as exc:
            raise AssistantUnavailable(
                "AI usage controls are temporarily unavailable. Please try later."
            ) from exc
        if count > limit:
            raise AssistantUnavailable(
                "The free AI or search allowance has been reached. Listing search is "
                "still available."
            )

    async def listings(
        self, filters: SearchFilters, *, size: int = 3
    ) -> tuple[ListingResults, list[dict[str, Any]]]:
        # No seller_handle/include_sold option is exposed to either users or the model.
        page = await BrowsePublicListings(uow=self.container.uow()).execute(
            BrowsePublicListingsQuery(**filters.model_dump(), limit=size, sort="newest")
        )
        cards: list[ListingCard] = []
        facts: list[dict[str, Any]] = []
        for item in page.items:
            try:
                detail = await GetPublicListing(uow=self.container.uow()).execute(item.id)
            except EntityNotFound:
                continue
            # Recheck after browse: a just-sold/deleted item must never be recommended.
            if not eligible(detail, filters):
                continue
            card = await self.card(detail, score=item.score)
            cards.append(card)
            facts.append(self.model_facts(detail))
        next_offset = filters.offset + len(page.items)
        return ListingResults(
            items=cards,
            total=page.total,
            next_offset=next_offset if next_offset < page.total and next_offset <= 300 else None,
            filters=filters,
        ), facts

    async def card(self, detail: Any, *, score: int | None = None) -> ListingCard:
        image = next((x for x in detail.images if x.is_primary), next(iter(detail.images), None))
        url = None
        if image:
            try:
                async with self.container.uow() as uow:
                    url = await thumbnail_url(
                        self.container, uow, image.file_id, image.thumbnail_object_key
                    )
            except Exception:
                # An unavailable image never prevents a valid listing recommendation.
                url = None
        return ListingCard(
            id=str(detail.id),
            title=public_text(detail.title, 80),
            price=detail.price,
            currency=detail.currency,
            category=detail.category,
            condition=detail.condition,
            city=detail.city,
            area=detail.area,
            image_url=url,
            href=f"/listing/{detail.id}",
            score=score,
            identity_verified=detail.identity_verified,
            attributes=safe_facts(detail.attributes),
        )

    @staticmethod
    def model_facts(detail: Any) -> dict[str, Any]:
        # Explicit allowlist. Never serialize the entity (seller ID, coordinates, media, etc.).
        return {
            "id": str(detail.id),
            "title": public_text(detail.title, 80),
            "price": detail.price,
            "currency": detail.currency,
            "category": detail.category,
            "condition_seller_claim": detail.condition,
            "city": detail.city,
            "description_seller_claim": public_text(detail.description, 650),
            "attributes_seller_claim": safe_facts(detail.attributes),
        }

    async def web(self, query: str) -> list[WebSource]:
        if not self.config.ready or not self.config.search_key:
            raise AssistantUnavailable(
                "Live web research is not connected. Current market facts could not be checked."
            )
        query = public_text(query, 200)
        digest = hashlib.sha256(query.casefold().encode()).hexdigest()
        cache_key = f"assistant:v1:web:{digest}"
        try:
            cached = await self.container.cache.get(cache_key)
            if cached:
                return [WebSource.model_validate(x) for x in json.loads(cached)]
        except (ValueError, ValidationError):
            pass
        except Exception as exc:
            raise AssistantUnavailable("Web research is temporarily unavailable.") from exc
        await self.allowance(
            "web", self.config.monthly_searches, datetime.now(UTC).strftime("%Y-%m"), 2678400
        )
        data = await request_json(
            self.client,
            "https://api.tavily.com/search",
            self.config.search_key,
            {
                "query": query,
                "search_depth": "basic",
                "auto_parameters": False,
                "topic": "general",
                "max_results": 6,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
                "include_usage": True,
            },
        )
        sources: list[WebSource] = []
        seen: set[str] = set()
        rows = data.get("results", [])
        for item in rows[:6] if isinstance(rows, list) else []:
            if not isinstance(item, dict):
                continue
            url = safe_url(item.get("url"))
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append(
                WebSource(
                    id=len(sources) + 1,
                    title=public_text(item.get("title"), 160),
                    url=url,
                    excerpt=public_text(item.get("content"), 900),
                    checked_at=datetime.now(UTC).isoformat(),
                )
            )
        # Short cache: avoids stale inventory/price answers masquerading as a fresh lookup.
        with suppress(Exception):
            await self.container.cache.set(
                cache_key, json.dumps([s.model_dump() for s in sources]), ttl_seconds=1800
            )
        return sources

    async def suggestions(
        self,
        query: str,
        category: str | None,
        city: str | None,
        *,
        seller: bool = False,
        offset: int = 0,
        limit: int = 10,
    ) -> SuggestionsReply:
        suggestions = [
            Suggestion(text=term.text, query=term.query, category=term.category)
            for term in search_terms(query, category)
        ]
        seen = {(item.text.casefold(), item.category) for item in suggestions}
        # Curated terms never imply stock. Eligible live titles supplement them, including
        # models that are not in the maintained vocabulary. No LLM or web-search call here.
        if not seller and query:
            page = await BrowsePublicListings(uow=self.container.uow()).execute(
                BrowsePublicListingsQuery(q=query, category=category, city=city, limit=5)
            )
            for item in page.items:
                title = public_text(item.title, 80)
                key = (title.casefold(), item.category)
                if key not in seen:
                    seen.add(key)
                    suggestions.append(
                        Suggestion(text=title, query=title, category=item.category, kind="listing")
                    )
        total = len(suggestions)
        return SuggestionsReply(
            items=suggestions[offset : offset + limit],
            total=total,
            next_offset=offset + limit if offset + limit < total else None,
            fields=FIELDS.get(category or "other", FIELDS["other"]),
        )

    async def chat(self, request: ChatRequest) -> ChatReply:
        history = [
            {"role": x.role, "content": public_text(x.content, 1200)} for x in request.history[-6:]
        ]
        user = public_text(request.message, 1800)
        filters = basic_filters(user, request.filters)
        warnings: list[str] = []
        if not self.config.ready:
            results, _ = await self.listings(filters)
            return ChatReply(
                answer=(
                    "AI abhi connect nahi hai. Yeh aap ke filters ki live listings hain. / AI "
                    "is not connected yet; you can still browse matching listings."
                ),
                listings=results,
                mode="listings-only",
            )
        context_ids = list(
            dict.fromkeys(
                [
                    *request.compare_ids,
                    *([request.current_listing_id] if request.current_listing_id else []),
                ]
            )
        )[:3]
        context_details: dict[Any, Any] = {}
        for listing_id in context_ids:
            try:
                context_details[listing_id] = await GetPublicListing(
                    uow=self.container.uow()
                ).execute(listing_id)
            except EntityNotFound:
                warnings.append("One selected listing is no longer publicly available.")
        planning_items = [
            {"title": public_text(item.title, 80), "category": item.category}
            for item in context_details.values()
            if item.status == "ACTIVE"
        ]
        try:
            raw_plan = await self.model(
                prompts.PLAN,
                {
                    "message": user,
                    "history": history,
                    "previous_filters": request.filters.model_dump(),
                    "allowed_categories": sorted(LISTING_CATEGORIES),
                    "selected_items": planning_items,
                },
                tokens=1000,
            )
            plan = SearchPlan.model_validate(raw_plan)
            if request.compare_ids:
                plan.intent = "compare"
            filters = merge_filters(request.filters, plan.filters, user)
        except (ValidationError, AssistantUnavailable) as exc:
            results, _ = await self.listings(filters)
            message = (
                str(exc)
                if isinstance(exc, AssistantUnavailable)
                else "AI could not understand the filters. Try naming a product, city and budget."
            )
            return ChatReply(answer=message, listings=results, mode="listings-only")
        results = ListingResults(filters=filters)
        facts: list[dict[str, Any]] = []
        if plan.intent in {"shopping", "compare"} and not request.compare_ids:
            results, facts = await self.listings(filters)
        for listing_id, detail in context_details.items():
            if str(listing_id) in {str(x["id"]) for x in facts}:
                continue
            if not eligible(detail, filters):
                warnings.append(
                    "One selected listing is unavailable or outside your current filters."
                )
                continue
            facts.append(self.model_facts(detail))
            if plan.intent == "compare":
                results.items.append(await self.card(detail))
        sources: list[WebSource] = []
        needs_web = plan.needs_web or plan.intent in {"shopping", "compare"}
        if needs_web and request.market_search:
            try:
                sources = await self.web(
                    plan.web_query
                    or f"{filters.q or filters.category or user} Pakistan buying guide"
                )
                if not sources:
                    warnings.append(
                        "No usable web sources were found. Current market facts could not be "
                        "checked."
                    )
            except AssistantUnavailable as exc:
                warnings.append(str(exc))
        elif needs_web:
            warnings.append("Web research is off. Current market facts could not be checked.")
        data = {
            "message": user,
            "history": history,
            "filters": filters.model_dump(),
            "listing_facts": facts,
            "web_sources": [s.model_dump() for s in sources],
            "warnings": warnings,
            "intent": plan.intent,
            "clarification": plan.clarification,
            "today": datetime.now(UTC).date().isoformat(),
        }
        try:
            raw = await self.model(prompts.ANSWER, data, tokens=2800)
            answer = raw.get("answer")
            if not isinstance(answer, str) or not answer.strip():
                raise AssistantUnavailable(
                    "AI could not finish this reply. The matching listings are shown below."
                )
        except AssistantUnavailable as exc:
            return ChatReply(
                answer=str(exc),
                listings=results,
                sources=sources,
                web_searched=bool(sources),
                warnings=warnings,
                mode="listings-only",
            )
        options: list[MarketOption] = []
        ids = {s.id for s in sources}
        seen: set[str] = set()
        raw_options = (
            raw.get("market_options", raw.get("marketOptions", []))
            if plan.intent in {"shopping", "compare"}
            else []
        )
        for item in raw_options[:6] if isinstance(raw_options, list) else []:
            try:
                option = MarketOption.model_validate(item)
            except ValidationError:
                continue
            option.source_ids = list(dict.fromkeys(i for i in option.source_ids if i in ids))
            if option.source_ids and option.name.casefold() not in seen:
                seen.add(option.name.casefold())
                options.append(option)
        return ChatReply(
            answer=public_text(answer, 6500),
            listings=results,
            market_options=options,
            sources=sources,
            web_searched=bool(sources),
            warnings=warnings,
        )

    async def describe(self, request: DescriptionRequest) -> DescriptionReply:
        facts = safe_facts(request.facts)
        hints = FIELDS.get(request.category, FIELDS["other"])
        if not self.config.ready:
            labels = {
                "en": ("Condition", "Details", "Please inspect the item before buying."),
                "ur": ("حالت", "تفصیلات", "خریدنے سے پہلے چیز کا معائنہ کر لیں۔"),  # noqa: RUF001
                "roman-ur": ("Haalat", "Details", "Kharidne se pehle item khud check kar lein."),
            }
            condition, _details, note = labels[request.language]
            text = "\n".join(
                [
                    public_text(request.title, 80),
                    f"{condition}: {request.condition.replace('_', ' ')}",
                    *[f"{k}: {v}" for k, v in facts.items()],
                    public_text(request.notes, 400),
                    note,
                ]
            )
            return DescriptionReply(
                description=text[:1000], missing_details=hints[:5], mode="template"
            )
        data = request.model_dump()
        data.update(
            title=public_text(request.title, 80),
            facts=facts,
            notes=public_text(request.notes, 1000),
            category_hints=hints,
        )
        raw = await self.model(prompts.DESCRIPTION, data, tokens=1600)
        try:
            result = DescriptionReply.model_validate(raw)
            result.description = public_text(result.description, 1000)
            return result
        except ValidationError as exc:
            raise AssistantUnavailable(
                "AI could not create a valid draft. Your existing description is unchanged."
            ) from exc

    async def research(self, request: ProductResearchRequest) -> ResearchReply:
        if request.category in {"property-sale", "property-rent", "services", "animals"}:
            return ResearchReply(
                summary=(
                    "These details depend on the actual item or service. Please confirm them "
                    "with the seller."
                ),
                questions=FIELDS[request.category],
            )
        sources = await self.web(
            f"{public_text(request.product, 140)} official specifications exact variant"
        )
        if not sources:
            return ResearchReply(
                summary=(
                    "No reliable specification excerpts were found. "
                    "Enter the exact model and variant or fill the details manually."
                )
            )
        raw = await self.model(
            prompts.RESEARCH,
            {
                "product": public_text(request.product, 160),
                "category": request.category,
                "language": request.language,
                "sources": [s.model_dump() for s in sources],
            },
            tokens=2200,
        )
        specs: list[SourcedSpec] = []
        indexed = {s.id: s for s in sources}
        seen: set[str] = set()
        rows = raw.get("specs", [])
        for item in rows[:8] if isinstance(rows, list) else []:
            try:
                spec = SourcedSpec.model_validate(item)
            except ValidationError:
                continue
            source = indexed.get(spec.source_id)
            if not source or PRIVATE_KEYS.search(spec.key):
                continue
            if re.search(
                r"pta|warranty|fault|repair|battery health|condition|registration|price|ownership",
                spec.key,
                re.I,
            ):
                continue

            def normal(value: str) -> str:
                return re.sub(r"\s+", "", value).casefold()

            if normal(spec.evidence) not in normal(source.excerpt):
                continue
            if normal(spec.value) not in normal(spec.evidence):
                continue
            if spec.key.casefold() in seen:
                continue
            seen.add(spec.key.casefold())
            specs.append(spec)
        questions = raw.get("questions", [])
        return ResearchReply(
            summary=public_text(raw.get("summary"), 1000),
            specs=specs,
            sources=sources,
            questions=[public_text(x, 200) for x in questions[:5] if isinstance(x, str)]
            if isinstance(questions, list)
            else [],
        )
