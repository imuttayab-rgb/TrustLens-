"""Buyer favorites - saving a listing for later, not scoring anything.

Deliberately the simplest use-case module in the codebase: a favorite is a
bookmark, not evidence, so there is no signal to recompute and no soft
delete to preserve an audit trail for. Add and remove are both idempotent -
a heart button that errors on a double-click is a worse experience than one
that just confirms the end state.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from trustlens.core.domain.entities import Favorite, PublicListingSummary
from trustlens.core.domain.errors import EntityNotFound
from trustlens.core.domain.ports import Clock, IdGenerator, UnitOfWork


@dataclass(frozen=True, slots=True)
class AddFavoriteCommand:
    user_id: UUID
    listing_id: UUID


class AddFavorite:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: AddFavoriteCommand) -> None:
        async with self._uow:
            listing = await self._uow.listings.get(cmd.listing_id)
            if listing is None:
                raise EntityNotFound("listing", cmd.listing_id)

            if await self._uow.favorites.exists(user_id=cmd.user_id, listing_id=cmd.listing_id):
                return

            await self._uow.favorites.add(
                Favorite(
                    id=self._ids.new(),
                    user_id=cmd.user_id,
                    listing_id=cmd.listing_id,
                    created_at=self._clock.now(),
                )
            )
            await self._uow.commit()


@dataclass(frozen=True, slots=True)
class RemoveFavoriteCommand:
    user_id: UUID
    listing_id: UUID


class RemoveFavorite:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, cmd: RemoveFavoriteCommand) -> None:
        async with self._uow:
            await self._uow.favorites.remove(user_id=cmd.user_id, listing_id=cmd.listing_id)
            await self._uow.commit()


@dataclass(frozen=True, slots=True)
class ListFavoritesQuery:
    user_id: UUID
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class FavoritesPage:
    items: tuple[PublicListingSummary, ...]
    total: int
    limit: int
    offset: int


class ListFavorites:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, query: ListFavoritesQuery) -> FavoritesPage:
        limit = max(1, min(query.limit, 50))
        offset = max(0, query.offset)
        async with self._uow:
            items = await self._uow.favorites.list_favorite_listings(
                query.user_id, limit=limit, offset=offset
            )
            total = await self._uow.favorites.count_for_user(query.user_id)
        return FavoritesPage(items=tuple(items), total=total, limit=limit, offset=offset)


class ListFavoriteIds:
    """Every listing id a user has favorited, for hydrating heart buttons on
    a page of catalog cards without checking one at a time."""

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, user_id: UUID) -> frozenset[UUID]:
        async with self._uow:
            return await self._uow.favorites.list_ids_for_user(user_id)


__all__ = [
    "AddFavorite",
    "AddFavoriteCommand",
    "FavoritesPage",
    "ListFavoriteIds",
    "ListFavorites",
    "ListFavoritesQuery",
    "RemoveFavorite",
    "RemoveFavoriteCommand",
]
