"""Offline regressions for marketplace autocomplete (no provider calls)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from trustlens_api.assistant.catalogue import FIELDS, normalize_search, search_terms
from trustlens_api.assistant.service import AssistantService


def labels(q, category=None):
    return [item.text for item in search_terms(q, category)]


def test_generic_laptop_discovers_brand_and_operating_system_families():
    first = labels("laptop")[:10]
    assert {"HP Laptops", "Dell Laptops", "Lenovo Laptops", "Chromebooks", "Apple MacBooks"} <= set(
        first
    )


def test_hp_has_ten_distinct_models_on_first_page_and_more():
    terms = search_terms("HP", "computers")
    assert len(terms) > 20
    assert all(term.depth == 2 and term.text.startswith("HP ") for term in terms[:10])
    assert len({term.text for term in terms[:10]}) == 10


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("iPhone 11", {"iPhone 11", "iPhone 11 Pro", "iPhone 11 Pro Max"}),
        ("iPhone 12", {"iPhone 12", "iPhone 12 mini", "iPhone 12 Pro", "iPhone 12 Pro Max"}),
        ("iPhone 13", {"iPhone 13", "iPhone 13 mini", "iPhone 13 Pro", "iPhone 13 Pro Max"}),
        ("iPhone 14", {"iPhone 14", "iPhone 14 Plus", "iPhone 14 Pro", "iPhone 14 Pro Max"}),
        ("iPhone 15", {"iPhone 15", "iPhone 15 Plus", "iPhone 15 Pro", "iPhone 15 Pro Max"}),
        (
            "iPhone 16",
            {"iPhone 16", "iPhone 16e", "iPhone 16 Plus", "iPhone 16 Pro", "iPhone 16 Pro Max"},
        ),
    ],
)
def test_real_iphone_variants_without_invented_permutations(query, expected):
    assert set(labels(query, "mobiles")) == expected


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("i phone13 pro", "iPhone 13 Pro"),
        ("mac book", "MacBook"),
        ("chrome book", "Chromebook"),
        ("techno", "Tecno"),
        ("Hewlett-Packard", "HP"),
        ("PS 5", "PlayStation 5"),
    ],
)
def test_aliases_produce_same_results(alias, canonical):
    assert labels(alias) == labels(canonical)


def test_phone_brands_are_explicit_and_category_isolated():
    terms = search_terms("", "mobiles")
    assert {"Tecno Mobile Phones", "OPPO Mobile Phones", "Samsung Mobile Phones"} <= {
        x.text for x in terms
    }
    assert all(x.category == "mobiles" and "Phones" in x.text for x in terms)
    assert search_terms("washing machine", "mobiles") == ()


def test_empty_search_suggests_categories_not_arbitrary_short_terms():
    terms = search_terms("", None)
    assert {x.category for x in terms} == set(FIELDS)
    assert all(x.depth == 0 for x in terms)
    assert not {"Cat", "Dog", "Shoes"} & {x.text for x in terms}


@pytest.mark.parametrize(
    ("category", "query", "expected"),
    [
        ("mobiles", "oppo", "OPPO Reno11 5G"),
        ("computers", "dell", "Dell Latitude 7490"),
        ("electronics", "PS5", "PS5 Slim"),
        ("vehicles", "suzuki", "Suzuki Alto"),
        ("vehicle-parts", "tyres", "Bridgestone tyres"),
        ("property-sale", "house", "5 marla house for sale"),
        ("property-rent", "flat", "2 bedroom flat for rent"),
        ("home-appliances", "washing", "Haier washing machine"),
        ("furniture", "sofa", "L shaped sofa"),
        ("fashion", "shoes", "Nike shoes"),
        ("books-hobbies", "gym", "Treadmill"),
        ("animals", "cat", "Persian cat"),
        ("services", "repair", "Washing machine repair"),
        ("other", "solar", "Solar panel"),
    ],
)
def test_each_supported_category_has_relevant_suggestions(category, query, expected):
    terms = search_terms(query, category)
    assert expected in {x.text for x in terms}
    assert all(x.category == category for x in terms)


def test_generation_numbers_do_not_leak_other_generations():
    assert all("4" not in x.text for x in search_terms("PS5", "electronics"))
    assert not labels("iPhone 130")
    assert normalize_search("Samsung S24+") == "samsung s 24 plus"


@pytest.mark.asyncio
async def test_page_boundaries_and_live_titles(monkeypatch):
    from trustlens_api.assistant import service

    execute = AsyncMock(
        return_value=SimpleNamespace(
            items=[
                SimpleNamespace(title="HP special public listing", category="computers"),
                SimpleNamespace(title="HP EliteBook 840 G3", category="computers"),
            ]
        )
    )
    monkeypatch.setattr(
        service, "BrowsePublicListings", lambda **kwargs: SimpleNamespace(execute=execute)
    )
    assistant = AssistantService.__new__(AssistantService)
    assistant.container = SimpleNamespace(uow=lambda: None)
    pages = []
    offset = 0
    while offset is not None:
        page = await assistant.suggestions("HP", "computers", "Lahore", offset=offset)
        assert len(page.items) <= 10
        pages.extend(page.items)
        offset = page.next_offset
    assert len(pages) == page.total == len({item.text for item in pages})
    assert sum(x.kind == "listing" for x in pages) == 1
    assert all(x.kind == "suggestion" for x in pages[:10])
    assert execute.call_args.args[0].city == "Lahore"
    assert not (await assistant.suggestions("HP", "computers", None, offset=5000)).items


@pytest.mark.asyncio
async def test_seller_and_empty_category_calls_do_not_query_inventory(monkeypatch):
    from trustlens_api.assistant import service

    def fail(**kwargs):
        pytest.fail("This suggestion request must not query inventory")

    monkeypatch.setattr(service, "BrowsePublicListings", fail)
    assistant = AssistantService.__new__(AssistantService)
    first = await assistant.suggestions("", "mobiles", None)
    second = await assistant.suggestions("HP", "computers", None, seller=True, offset=10)
    assert first.next_offset == 10
    assert len(second.items) == 10
    assert second.model_dump(by_alias=True)["nextOffset"] == 20
    assert first.items[2].text == "OPPO Mobile Phones"
    assert first.items[2].query == "OPPO"
