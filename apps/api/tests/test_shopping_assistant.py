"""Offline contract tests: no vendor credentials, customer data or network required."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from trustlens_api.assistant.catalogue import explicit_budget, safe_facts, vocabulary
from trustlens_api.assistant.contracts import (
    ChatRequest,
    DescriptionRequest,
    ListingResults,
    ProductResearchRequest,
    SearchFilters,
    WebSource,
)
from trustlens_api.assistant.provider import AssistantConfig, AssistantUnavailable, GroqProvider
from trustlens_api.assistant.service import AssistantService, eligible, merge_filters


class Cache:
    def __init__(self):
        self.values = {}
        self.counts = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, **kwargs):
        self.values[key] = value

    async def incr(self, key, **kwargs):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


def detail(**changes):
    values = {
        "id": uuid4(),
        "title": "Samsung test fixture",
        "status": "ACTIVE",
        "price": 39000,
        "currency": "PKR",
        "category": "mobiles",
        "condition": "USED",
        "city": "Lahore",
        "area": None,
        "description": "Phone 03001234567; email owner@example.com",
        "images": [],
        "attributes": {"RAM": "8 GB", "CNIC": "12345-1234567-1"},
        "identity_verified": True,
        "seller_id": "private-seller",
        "latitude": 31.1,
        "longitude": 74.1,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def service(client, **config):
    container = SimpleNamespace(cache=Cache(), uow=lambda: None)
    return AssistantService(container, client, AssistantConfig(**config))


@pytest.mark.parametrize(
    ("message", "amount"),
    [
        ("bhai 40 hazar mein phone", 40000),
        ("budget 40,000", 40000),
        ("under 80k PS5", 80000),
        ("1.5 lakh washing machine", 150000),
        ("بجٹ ۴۰ ہزار", 40000),
        ("PKR 200000 car", 200000),
        ("iPhone 15 Pro Max", None),
        ("Honda Civic 2022", None),
        ("PS5 1TB", None),
    ],
)
def test_explicit_money_not_model_numbers(message, amount):
    assert explicit_budget(message) == amount


def test_followup_does_not_erase_budget_or_city():
    result = merge_filters(
        SearchFilters(max_price=40000, city="Lahore", category="mobiles"),
        SearchFilters(max_price=90000, q="Samsung"),
        "camera acha ho",
    )
    assert result.max_price == 40000
    assert result.city == "Lahore"
    assert result.category == "mobiles"
    assert merge_filters(result, SearchFilters(), "budget ab 60 hazar hai").max_price == 60000


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "SOLD"},
        {"status": "RESERVED"},
        {"price": 50000},
        {"price": None},
        {"currency": "USD"},
        {"city": "Karachi"},
        {"category": "vehicles"},
        {"condition": "NEW"},
    ],
)
def test_public_items_must_still_meet_hard_filters(changes):
    filters = SearchFilters(category="mobiles", city="Lahore", max_price=40000, condition="USED")
    assert eligible(detail(), filters)
    assert not eligible(detail(**changes), filters)


def test_model_projection_excludes_identity_and_contact_data():
    facts = AssistantService.model_facts(detail())
    value = json.dumps(facts)
    assert "03001234567" not in value and "owner@example.com" not in value
    assert not {"seller_id", "latitude", "longitude", "images"} & facts.keys()
    assert facts["attributes_seller_claim"] == {"RAM": "8 GB"}
    assert safe_facts({"email": "x@y.com", "battery health": "80%"}) == {"battery health": "80%"}


@pytest.mark.parametrize(
    "category, query",
    [
        ("mobiles", "Samsung"),
        ("vehicles", "Honda"),
        ("home-appliances", "washing"),
        ("electronics", "PS5"),
        ("furniture", "sofa"),
    ],
)
def test_category_suggestions_across_product_types(category, query):
    assert vocabulary(query, category)
    assert all(cat == category for _, cat in vocabulary(query, category))


@pytest.mark.parametrize(
    "payload",
    [
        {"maxPrice": float("inf")},
        {"category": "all-private"},
        {"offset": 999999},
        {"minPrice": 500, "maxPrice": 100},
        {"seller_handle": "private"},
    ],
)
def test_search_rejects_unsafe_or_unsupported_filters(payload):
    with pytest.raises(ValidationError):
        SearchFilters.model_validate(payload)


async def test_no_key_is_honest_listing_fallback():
    async with httpx.AsyncClient() as client:
        assistant = service(client)
        assistant.listings = AsyncMock(return_value=(ListingResults(), []))
        assistant.model = AsyncMock()
        reply = await assistant.chat(ChatRequest(message="40 hazar phone"))
        assert reply.mode == "listings-only"
        assert "not connected" in reply.answer
        assistant.model.assert_not_called()
        assert assistant.listings.call_args.args[0].max_price == 40000


async def test_deleted_or_sold_between_browse_and_details_is_not_recommended(monkeypatch):
    import trustlens_api.assistant.service as module

    active, sold = detail(), detail(status="SOLD")
    page = SimpleNamespace(
        items=[SimpleNamespace(id=x.id, score=80) for x in (active, sold)], total=2
    )
    browse = SimpleNamespace(execute=AsyncMock(return_value=page))
    get = SimpleNamespace(execute=AsyncMock(side_effect=[active, sold]))
    monkeypatch.setattr(module, "BrowsePublicListings", lambda **kwargs: browse)
    monkeypatch.setattr(module, "GetPublicListing", lambda **kwargs: get)
    async with httpx.AsyncClient() as client:
        results, facts = await service(client).listings(SearchFilters(max_price=40000))
    assert [item.id for item in results.items] == [str(active.id)]
    assert results.items[0].href == f"/listing/{active.id}"
    assert len(facts) == 1
    assert browse.execute.call_args.args[0].include_sold is False


async def test_quota_exhaustion_never_calls_provider():
    async with httpx.AsyncClient() as client:
        assistant = service(client, enabled=True, api_key="test", daily_requests=1)
        assistant.provider.complete = AsyncMock(return_value={"answer": "one"})
        await assistant.model("test", {})
        with pytest.raises(AssistantUnavailable, match="allowance"):
            await assistant.model("test", {})
        assert assistant.provider.complete.await_count == 1
        assistant.container.cache.incr = AsyncMock(side_effect=RuntimeError("redis down"))
        with pytest.raises(AssistantUnavailable, match="controls"):
            await assistant.model("test", {})
        assert assistant.provider.complete.await_count == 1


async def test_tavily_is_basic_bounded_cached_and_discards_bad_links():
    calls = []

    def transport(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "results": [
                    {"url": "javascript:alert(1)", "title": "bad", "content": "bad"},
                    {
                        "url": "https://manufacturer.example/model",
                        "title": "Model",
                        "content": "8 GB RAM",
                    },
                    {
                        "url": "https://manufacturer.example/model",
                        "title": "duplicate",
                        "content": "8 GB RAM",
                    },
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        assistant = service(
            client, enabled=True, api_key="test", search_key="search", monthly_searches=1
        )
        sources = await assistant.web("Samsung specs")
        assert await assistant.web("Samsung specs") == sources
        with pytest.raises(AssistantUnavailable, match="allowance"):
            await assistant.web("different query")
    assert len(calls) == 1 and len(sources) == 1
    body = json.loads(calls[0].content)
    assert body["search_depth"] == "basic" and body["auto_parameters"] is False
    assert body["max_results"] == 6 and body["include_raw_content"] is False


async def test_groq_contract_and_safe_quota_error():
    bodies = []

    def transport(request):
        bodies.append(json.loads(request.content))
        if len(bodies) == 2:
            return httpx.Response(429, json={"error": "private vendor diagnostic secret"})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": '{"answer":"Helpful reply"}',
                            "reasoning": "PRIVATE",
                        },
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = GroqProvider(AssistantConfig(enabled=True, api_key="test"), client)
        assert await provider.complete("system", {}) == {"answer": "Helpful reply"}
        with pytest.raises(AssistantUnavailable, match="allowance") as failure:
            await provider.complete("system", {})
    assert "secret" not in str(failure.value)
    assert bodies[0]["model"] == "openai/gpt-oss-120b"
    assert bodies[0]["response_format"] == {"type": "json_object"}


def source():
    return WebSource(
        id=1,
        title="Manufacturer model",
        url="https://manufacturer.example/model",
        excerpt="This model has 8 GB RAM and 128 GB storage.",
        checked_at="2026-10-03",
    )


async def test_specs_need_matching_quote_and_cannot_claim_unit_condition():
    async with httpx.AsyncClient() as client:
        assistant = service(client, enabled=True, api_key="test", search_key="test")
        assistant.web = AsyncMock(return_value=[source()])
        assistant.model = AsyncMock(
            return_value={
                "summary": "Check your variant",
                "specs": [
                    {"key": "RAM", "value": "8 GB", "source_id": 1, "evidence": "8 GB RAM"},
                    {
                        "key": "Storage",
                        "value": "256 GB",
                        "source_id": 1,
                        "evidence": "256 GB storage",
                    },
                    {"key": "Warranty", "value": "8 GB", "source_id": 1, "evidence": "8 GB RAM"},
                    {
                        "key": "Display",
                        "value": "120 Hz",
                        "source_id": 99,
                        "evidence": "120 Hz display",
                    },
                ],
            }
        )
        result = await assistant.research(ProductResearchRequest(product="Example exact model"))
    assert [(x.key, x.value) for x in result.specs] == [("RAM", "8 GB")]


async def test_market_cards_require_real_source_ids():
    async with httpx.AsyncClient() as client:
        assistant = service(client, enabled=True, api_key="test", search_key="test")
        assistant.listings = AsyncMock(return_value=(ListingResults(), []))
        assistant.web = AsyncMock(return_value=[source()])
        assistant.model = AsyncMock(
            side_effect=[
                {"intent": "shopping", "filters": {}},
                {
                    "answer": "Compare model fit [1]",
                    "market_options": [
                        {
                            "name": "Actual model",
                            "summary": "Check exact variant",
                            "source_ids": [1],
                        },
                        {"name": "Invented source", "summary": "unsupported", "source_ids": [99]},
                    ],
                },
            ]
        )
        result = await assistant.chat(ChatRequest(message="phone 40 hazar"))
    assert [x.name for x in result.market_options] == ["Actual model"]


async def test_description_template_uses_known_facts_without_pretending_ai():
    async with httpx.AsyncClient() as client:
        result = await service(client).describe(
            DescriptionRequest(
                title="Washing machine",
                category="home-appliances",
                condition="USED",
                facts={"Capacity": "8 kg"},
                notes="Drain hose missing",
                language="en",
            )
        )
    assert result.mode == "template"
    assert "8 kg" in result.description and "Drain hose missing" in result.description
    assert "warranty" not in result.description.lower()


def test_new_write_routes_remain_authenticated():
    from fastapi.routing import iter_route_contexts

    from trustlens_api.main import _PUBLIC_ROUTES, _assert_routes_are_guarded, create_app

    app = create_app()
    _assert_routes_are_guarded(app)
    paths = {getattr(route, "path", ""): route for route in iter_route_contexts(app.routes)}
    for name in ("description", "research"):
        path = f"/api/v1/assistant/{name}"
        assert path not in _PUBLIC_ROUTES
        assert "get_current_actor" in str(paths[path].dependant.dependencies)


async def test_comparison_uses_only_selected_items_and_supplies_product_context(monkeypatch):
    import trustlens_api.assistant.service as module

    selected = [detail(), detail(title="Other selected phone")]
    get = SimpleNamespace(execute=AsyncMock(side_effect=selected))
    monkeypatch.setattr(module, "GetPublicListing", lambda **kwargs: get)
    async with httpx.AsyncClient() as client:
        assistant = service(client, enabled=True, api_key="test")
        assistant.listings = AsyncMock()
        assistant.model = AsyncMock(
            side_effect=[
                {"intent": "explain", "filters": {}},
                {"answer": "Compare the selected items; their exact condition is a seller claim."},
            ]
        )
        result = await assistant.chat(
            ChatRequest(
                message="Compare these", compare_ids=[x.id for x in selected], market_search=False
            )
        )
    assistant.listings.assert_not_called()
    assert {x.id for x in result.listings.items} == {str(x.id) for x in selected}
    planning_data = assistant.model.call_args_list[0].args[1]
    assert [x["title"] for x in planning_data["selected_items"]] == [x.title for x in selected]
