"""Buyer saved searches (FAV-01) - a remembered browse filter, re-runnable
with one click instead of rebuilding it from scratch every visit.

Deliberately simple, in the same spirit as favorites: a saved search is a
convenience bookmark, not evidence, so there is nothing to soft-delete or
audit. It does not (yet) push a notification when a new listing matches -
that needs NOT-01's notification center to exist for real first (today it is
dead code - nothing calls `.notifications.add(...)`), so this only covers
saving/listing/deleting the filter itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from trustlens.core.domain.entities import SavedSearch
from trustlens.core.domain.errors import EntityNotFound, PermissionDenied, ValidationError
from trustlens.core.domain.ports import Clock, IdGenerator, UnitOfWork
from trustlens.core.domain.value_objects import validate_category

MAX_NAME_CHARS = 100
#: A generous cap, not a monetisation lever - just enough to stop one
#: account from accumulating an unbounded number of rows.
MAX_SAVED_SEARCHES_PER_USER = 20


@dataclass(frozen=True, slots=True)
class CreateSavedSearchCommand:
    user_id: UUID
    name: str
    category: str | None = None
    q: str | None = None
    city: str | None = None
    area: str | None = None
    min_price: float | None = None
    max_price: float | None = None


class CreateSavedSearch:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: CreateSavedSearchCommand) -> SavedSearch:
        name = cmd.name.strip()
        if not name:
            raise ValidationError("Give this search a name.", field="name")
        if len(name) > MAX_NAME_CHARS:
            raise ValidationError(f"Keep the name under {MAX_NAME_CHARS} characters.", field="name")
        category = validate_category(cmd.category)

        async with self._uow:
            if (
                await self._uow.saved_searches.count_for_user(cmd.user_id)
                >= MAX_SAVED_SEARCHES_PER_USER
            ):
                raise ValidationError(
                    f"You can save up to {MAX_SAVED_SEARCHES_PER_USER} searches. Delete one first.",
                    field="name",
                )
            search = await self._uow.saved_searches.add(
                SavedSearch(
                    id=self._ids.new(),
                    user_id=cmd.user_id,
                    name=name,
                    category=category,
                    q=(cmd.q.strip() or None) if cmd.q else None,
                    city=cmd.city,
                    area=cmd.area,
                    min_price=cmd.min_price,
                    max_price=cmd.max_price,
                    created_at=self._clock.now(),
                )
            )
            await self._uow.commit()
        return search


class ListSavedSearches:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, user_id: UUID) -> list[SavedSearch]:
        async with self._uow:
            return await self._uow.saved_searches.list_for_user(user_id)


@dataclass(frozen=True, slots=True)
class DeleteSavedSearchCommand:
    user_id: UUID
    search_id: UUID


class DeleteSavedSearch:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, cmd: DeleteSavedSearchCommand) -> None:
        async with self._uow:
            search = await self._uow.saved_searches.get(cmd.search_id)
            if search is None:
                raise EntityNotFound("saved_search", cmd.search_id)
            if search.user_id != cmd.user_id:
                raise PermissionDenied("This saved search belongs to someone else.")
            await self._uow.saved_searches.remove(user_id=cmd.user_id, search_id=cmd.search_id)
            await self._uow.commit()


__all__ = [
    "MAX_NAME_CHARS",
    "MAX_SAVED_SEARCHES_PER_USER",
    "CreateSavedSearch",
    "CreateSavedSearchCommand",
    "DeleteSavedSearch",
    "DeleteSavedSearchCommand",
    "ListSavedSearches",
]
