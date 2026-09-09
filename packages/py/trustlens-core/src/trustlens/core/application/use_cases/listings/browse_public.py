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

from trustlens.core.domain.entities import PublicListingSummary
from trustlens.core.domain.ports import UnitOfWork
from trustlens.core.domain.value_objects import validate_category

#: A search box is an injection surface even when it only ever reaches an
#: ILIKE clause - an unbounded string is still a way to make the query
#: expensive. Long enough for any real listing title, nowhere near enough to
#: matter as a cost attack.
MAX_QUERY_CHARS = 200


@dataclass(frozen=True, slots=True)
class BrowsePublicListingsQuery:
    category: str | None = None
    q: str | None = None
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

        async with self._uow:
            items = await self._uow.listings.search_public(
                category=category, q=q, limit=limit, offset=offset
            )
            total = await self._uow.listings.count_public(category=category, q=q)

        return PublicListingPage(items=tuple(items), total=total, limit=limit, offset=offset)


__all__ = [
    "MAX_QUERY_CHARS",
    "BrowsePublicListings",
    "BrowsePublicListingsQuery",
    "PublicListingPage",
]
