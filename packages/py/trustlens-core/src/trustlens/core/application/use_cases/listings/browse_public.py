"""The public listing catalog (buyer-facing browse/search, feature F5b).

Mirrors the reasoning behind `GetPublicTrustScore`: this is a screen an
anonymous buyer opens directly, not an authenticated seller endpoint, so it
gets its own read path rather than a permission check bolted onto
`ListSellerListings`. Only ACTIVE listings are ever returned - ANALYSING and
DRAFT mean nobody has vetted the listing yet, FLAGGED means the scam-pattern
check failed it, and REMOVED/EXPIRED are gone. Showing any of those to a
buyer would contradict the product's whole premise.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from trustlens.core.domain.entities import PublicListingDetail, PublicListingSummary
from trustlens.core.domain.errors import EntityNotFound, ValidationError
from trustlens.core.domain.ports import UnitOfWork
from trustlens.core.domain.value_objects import validate_category

#: A search box is an injection surface even when it only ever reaches an
#: ILIKE clause - an unbounded string is still a way to make the query
#: expensive. Long enough for any real listing title, nowhere near enough to
#: matter as a cost attack.
MAX_QUERY_CHARS = 200

#: A fixed vocabulary, not a free sort expression - the repository maps each
#: one to a specific ORDER BY, so there is no column name for a client to
#: smuggle through here.
SORT_ORDERS = frozenset({"newest", "price_asc", "price_desc"})


@dataclass(frozen=True, slots=True)
class BrowsePublicListingsQuery:
    category: str | None = None
    q: str | None = None
    city: str | None = None
    area: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    sort: str = "newest"
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class PublicListingPage:
    items: tuple[PublicListingSummary, ...]
    total: int
    limit: int
    offset: int


class BrowsePublicListings:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, query: BrowsePublicListingsQuery) -> PublicListingPage:
        limit = max(1, min(query.limit, 50))
        offset = max(0, query.offset)
        category = validate_category(query.category)
        q = query.q.strip() if query.q else None
        q = q[:MAX_QUERY_CHARS] if q else None
        city = query.city.strip() if query.city else None
        area = query.area.strip() if query.area else None

        if query.sort not in SORT_ORDERS:
            raise ValidationError("Choose a valid sort order.", field="sort")
        if query.min_price is not None and query.min_price < 0:
            raise ValidationError("Minimum price cannot be negative.", field="minPrice")
        if query.max_price is not None and query.max_price < 0:
            raise ValidationError("Maximum price cannot be negative.", field="maxPrice")
        if (
            query.min_price is not None
            and query.max_price is not None
            and query.min_price > query.max_price
        ):
            raise ValidationError("Minimum price cannot exceed maximum price.", field="minPrice")

        async with self._uow:
            items = await self._uow.listings.search_public(
                category=category,
                q=q,
                city=city,
                area=area,
                min_price=query.min_price,
                max_price=query.max_price,
                sort=query.sort,
                limit=limit,
                offset=offset,
            )
            total = await self._uow.listings.count_public(
                category=category,
                q=q,
                city=city,
                area=area,
                min_price=query.min_price,
                max_price=query.max_price,
            )

        return PublicListingPage(items=tuple(items), total=total, limit=limit, offset=offset)


class GetPublicListing:
    """The "view this listing" page a catalog card opens into."""

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, listing_id: UUID) -> PublicListingDetail:
        async with self._uow:
            detail = await self._uow.listings.get_public_detail(listing_id)
        if detail is None:
            raise EntityNotFound("listing", listing_id)
        return detail


__all__ = [
    "MAX_QUERY_CHARS",
    "SORT_ORDERS",
    "BrowsePublicListings",
    "BrowsePublicListingsQuery",
    "GetPublicListing",
    "PublicListingPage",
]
