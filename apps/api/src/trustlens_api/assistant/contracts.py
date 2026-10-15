"""Bounded inputs for untrusted chat messages and model tool arguments."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from trustlens.core.domain.value_objects.listing_category import LISTING_CATEGORIES
from trustlens_api.api.v1.schemas.common import Schema


class InputModel(Schema):
    model_config = ConfigDict(allow_inf_nan=False, json_schema_serialization_defaults_required=True)


class SearchFilters(InputModel):
    category: str | None = Field(default=None, max_length=80)
    q: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=80)
    condition: Literal["NEW", "LIKE_NEW", "USED", "FOR_PARTS"] | None = None
    min_price: float | None = Field(default=None, ge=0, le=1_000_000_000)
    max_price: float | None = Field(default=None, ge=0, le=1_000_000_000)
    offset: int = Field(default=0, ge=0, le=300)

    @field_validator("category")
    @classmethod
    def valid_category(cls, value: str | None) -> str | None:
        if value is not None and value not in LISTING_CATEGORIES:
            raise ValueError("Choose a supported category")
        return value

    @model_validator(mode="after")
    def price_order(self) -> SearchFilters:
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("Minimum price exceeds maximum price")
        return self


class ChatMessage(InputModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2500)


class ChatRequest(InputModel):
    message: str = Field(min_length=1, max_length=1800)
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    current_listing_id: UUID | None = None
    market_search: bool = True
    compare_ids: list[UUID] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def conversation_size(self) -> ChatRequest:
        if sum(len(m.content) for m in self.history) > 12000:
            raise ValueError("Conversation is too long; start a new chat")
        return self


class DetailRequest(InputModel):
    listing_id: UUID


class DescriptionRequest(InputModel):
    title: str = Field(min_length=3, max_length=80)
    category: str = Field(max_length=80)
    condition: Literal["NEW", "LIKE_NEW", "USED", "FOR_PARTS"]
    facts: dict[str, str] = Field(default_factory=dict, max_length=24)
    notes: str = Field(default="", max_length=1500)
    language: Literal["en", "ur", "roman-ur"] = "en"

    @field_validator("category")
    @classmethod
    def valid_category(cls, value: str) -> str:
        if value not in LISTING_CATEGORIES:
            raise ValueError("Choose a supported category")
        return value

    @field_validator("facts")
    @classmethod
    def fact_sizes(cls, value: dict[str, str]) -> dict[str, str]:
        if any(len(k) > 60 or len(v) > 160 for k, v in value.items()):
            raise ValueError("Keep individual product details short")
        if any(
            k.casefold() in {"cnic", "selfie", "address", "address_line", "phone", "email", "password", "token", "secret", "imei", "serial"}
            for k in value
        ):
            raise ValueError("Use product facts, not private identity or contact fields")
        return value


class ProductResearchRequest(InputModel):
    product: str = Field(min_length=3, max_length=160)
    category: str | None = Field(default=None, max_length=80)
    language: Literal["en", "ur", "roman-ur"] = "en"

    @field_validator("category")
    @classmethod
    def valid_category(cls, value: str | None) -> str | None:
        if value is not None and value not in LISTING_CATEGORIES:
            raise ValueError("Choose a supported category")
        return value


class SearchPlan(InputModel):
    intent: Literal["shopping", "compare", "explain", "site"] = "explain"
    filters: SearchFilters = Field(default_factory=SearchFilters)
    web_query: str = Field(default="", max_length=200)
    needs_web: bool = False
    clarification: str = Field(default="", max_length=300)


class ListingCard(InputModel):
    id: str
    title: str
    price: float | None
    currency: str | None
    category: str | None
    condition: str | None
    city: str | None
    area: str | None
    image_url: str | None = None
    href: str
    score: int | None = None
    identity_verified: bool = False
    attributes: dict[str, str] = Field(default_factory=dict)


class ListingResults(InputModel):
    items: list[ListingCard] = Field(default_factory=list)
    total: int = 0
    next_offset: int | None = None
    filters: SearchFilters = Field(default_factory=SearchFilters)


class WebSource(InputModel):
    id: int
    title: str
    url: str
    excerpt: str
    checked_at: str


class MarketOption(InputModel):
    name: str = Field(max_length=140)
    summary: str = Field(max_length=500)
    source_ids: list[int] = Field(max_length=6)


class ChatReply(InputModel):
    answer: str
    listings: ListingResults = Field(default_factory=ListingResults)
    market_options: list[MarketOption] = Field(default_factory=list)
    sources: list[WebSource] = Field(default_factory=list)
    web_searched: bool = False
    warnings: list[str] = Field(default_factory=list)
    mode: Literal["ai", "listings-only"] = "ai"


class DescriptionReply(InputModel):
    description: str = Field(min_length=10, max_length=1000)
    missing_details: list[str] = Field(default_factory=list, max_length=8)
    mode: Literal["ai", "template"] = "ai"


class SourcedSpec(InputModel):
    key: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=160)
    source_id: int
    evidence: str = Field(min_length=4, max_length=350)


class ResearchReply(InputModel):
    summary: str
    specs: list[SourcedSpec] = Field(default_factory=list)
    sources: list[WebSource] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class Suggestion(InputModel):
    text: str
    query: str | None = None
    category: str | None = None
    kind: Literal["listing", "suggestion"] = "suggestion"


class SuggestionsReply(InputModel):
    items: list[Suggestion]
    fields: list[str]
    total: int = 0
    next_offset: int | None = None


class AssistantStatus(InputModel):
    ready: bool
    web_ready: bool
    provider: str = "Groq"
    free_plan_required: bool = True


class EnhanceRequest(DescriptionRequest):
    category_node_id: str | None = Field(default=None, max_length=240)
    condition: Literal["NEW", "LIKE_NEW", "USED", "FOR_PARTS"] | None = None
    description: str = Field(default="", max_length=8000)

    @model_validator(mode="after")
    def category_context(self):
        from trustlens.core.catalogue import category_node
        node = category_node(self.category_node_id, leaf=True)
        if node and node['legacyCategory'] != self.category:
            raise ValueError('Category and subcategory do not match')
        if (not node or node['conditionRequired']) and self.condition is None:
            raise ValueError('Supply the actual condition for this product')
        return self
    listing_id: UUID | None = None
    use_photos: bool = True


class ProductSpec(InputModel):
    key: str = Field(min_length=1, max_length=60)
    value: str = Field(min_length=1, max_length=160)


class EnhanceReply(InputModel):
    description: str = Field(min_length=10, max_length=8000)
    specs: list[ProductSpec] = Field(default_factory=list, max_length=24)
    sources: list[WebSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list, max_length=8)
    missing_details: list[str] = Field(default_factory=list, max_length=5)
    photo_hints: list[str] = Field(default_factory=list, max_length=3)
    photos_checked: int = 0
