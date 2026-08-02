"""Listing management (feature F5, seller side).

These use cases own the listing lifecycle. They never analyse anything
themselves: creating or meaningfully editing a listing enqueues
`listings.analyse_listing`, and the worker produces evidence that the scoring
policy prices (ADR-0002, ADR-0003).

One rule shapes the whole module: **listing text is attacker-controlled.** A
seller writes the title and description, and that text is handed to an LLM. So
nothing here trusts it, nothing interpolates it into a prompt, and the AI's
verdict can only ever move one signal worth a bounded number of points.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from uuid import UUID

from trustlens.core.domain.entities import Listing
from trustlens.core.domain.enums import ListingSource, ListingStatus
from trustlens.core.domain.errors import EntityNotFound, PermissionDenied, ValidationError
from trustlens.core.domain.events import ListingCreated
from trustlens.core.domain.ports import Clock, IdGenerator, JobQueue, UnitOfWork
from trustlens.core.domain.value_objects import Money

#: Beyond this a listing is not a listing; it is an attempt to exhaust the LLM
#: context or the token budget.
MAX_TITLE_CHARS = 250
MAX_DESCRIPTION_CHARS = 8_000

#: Statuses a seller may not edit out of - a removed listing stays removed.
_LOCKED_STATUSES = frozenset({ListingStatus.REMOVED})


@dataclass(frozen=True, slots=True)
class ListingInput:
    title: str
    description: str
    price: float | None = None
    currency: str | None = None
    category: str | None = None
    condition: str | None = None
    city: str | None = None
    country_code: str | None = None

    def money(self) -> Money | None:
        if self.price is None:
            return None
        if not self.currency:
            raise ValidationError("A currency is required when a price is given.", field="currency")
        return Money(amount=self.price, currency=self.currency)


def _clean(value: str, *, field: str, maximum: int) -> str:
    text = value.strip()
    if not text:
        raise ValidationError("This field cannot be empty.", field=field)
    if len(text) > maximum:
        raise ValidationError(f"Keep this under {maximum} characters.", field=field)
    return text


@dataclass(frozen=True, slots=True)
class CreateListingCommand:
    seller_id: UUID
    data: ListingInput


@dataclass(frozen=True, slots=True)
class ListingResult:
    listing: Listing
    job_id: str | None


class CreateListing:
    """Create a listing and queue it for analysis."""

    def __init__(self, *, uow: UnitOfWork, queue: JobQueue, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._queue = queue
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: CreateListingCommand) -> ListingResult:
        now = self._clock.now()
        title = _clean(cmd.data.title, field="title", maximum=MAX_TITLE_CHARS)
        description = _clean(
            cmd.data.description, field="description", maximum=MAX_DESCRIPTION_CHARS
        )

        async with self._uow:
            seller = await self._uow.sellers.get(cmd.seller_id)
            if seller is None:
                raise EntityNotFound("seller", cmd.seller_id)

            listing = await self._uow.listings.add(
                Listing(
                    id=self._ids.new(),
                    seller_id=cmd.seller_id,
                    title=title,
                    description=description,
                    # ANALYSING, not ACTIVE: a listing that has not been looked
                    # at yet must not be presented as one that passed.
                    status=ListingStatus.ANALYSING,
                    source=ListingSource.MANUAL,
                    created_at=now,
                    price=cmd.data.money(),
                    category=cmd.data.category,
                    condition=cmd.data.condition,
                    city=cmd.data.city,
                    country_code=cmd.data.country_code,
                )
            )
            await self._uow.publish(
                ListingCreated(
                    aggregate_id=listing.id,
                    occurred_at=now,
                    payload={"seller_id": str(cmd.seller_id)},
                )
            )
            await self._uow.commit()

        job_id = await self._queue.enqueue("listings.analyse_listing", listing_id=str(listing.id))
        return ListingResult(listing=listing, job_id=job_id)


@dataclass(frozen=True, slots=True)
class UpdateListingCommand:
    seller_id: UUID
    listing_id: UUID
    data: ListingInput


class UpdateListing:
    """Edit a listing, re-analysing only when the text actually changed.

    Re-analysis costs an LLM call, so a seller correcting a typo in the city
    field must not trigger one. Title and description are what the analyser
    reads, so only those force a re-run.
    """

    def __init__(self, *, uow: UnitOfWork, queue: JobQueue, clock: Clock) -> None:
        self._uow = uow
        self._queue = queue
        self._clock = clock

    async def execute(self, cmd: UpdateListingCommand) -> ListingResult:
        now = self._clock.now()
        title = _clean(cmd.data.title, field="title", maximum=MAX_TITLE_CHARS)
        description = _clean(
            cmd.data.description, field="description", maximum=MAX_DESCRIPTION_CHARS
        )

        async with self._uow:
            listing = await self._require_own_listing(cmd.listing_id, cmd.seller_id)
            if listing.status in _LOCKED_STATUSES:
                raise ValidationError("This listing has been removed and cannot be edited.")

            text_changed = title != listing.title or description != listing.description
            updated = await self._uow.listings.update(
                dataclasses.replace(
                    listing,
                    title=title,
                    description=description,
                    price=cmd.data.money(),
                    category=cmd.data.category,
                    condition=cmd.data.condition,
                    city=cmd.data.city,
                    country_code=cmd.data.country_code,
                    status=ListingStatus.ANALYSING if text_changed else listing.status,
                    updated_at=now,
                )
            )
            await self._uow.commit()

        job_id = None
        if text_changed:
            job_id = await self._queue.enqueue(
                "listings.analyse_listing", listing_id=str(updated.id)
            )
        return ListingResult(listing=updated, job_id=job_id)

    async def _require_own_listing(self, listing_id: UUID, seller_id: UUID) -> Listing:
        listing: Listing | None = await self._uow.listings.get(listing_id)
        # Same response whether the listing is missing or belongs to someone
        # else: distinguishing them turns this into an enumeration oracle.
        if listing is None or listing.seller_id != seller_id:
            raise EntityNotFound("listing", listing_id)
        return listing


@dataclass(frozen=True, slots=True)
class DeleteListingCommand:
    seller_id: UUID
    listing_id: UUID


class DeleteListing:
    """Soft-delete a listing.

    Soft, because a hard delete would let a seller erase the evidence behind
    an already-published Trust Score - and any appeal against that score would
    then be unanswerable.
    """

    def __init__(self, *, uow: UnitOfWork, queue: JobQueue, clock: Clock) -> None:
        self._uow = uow
        self._queue = queue
        self._clock = clock

    async def execute(self, cmd: DeleteListingCommand) -> None:
        now = self._clock.now()
        async with self._uow:
            listing = await self._uow.listings.get(cmd.listing_id)
            if listing is None or listing.seller_id != cmd.seller_id:
                raise EntityNotFound("listing", cmd.listing_id)

            await self._uow.listings.update(
                dataclasses.replace(
                    listing,
                    status=ListingStatus.REMOVED,
                    deleted_at=now,
                    updated_at=now,
                )
            )
            await self._uow.commit()

        # The LISTING signal is computed from a seller's live listings, so
        # removing one changes the score.
        await self._queue.enqueue(
            "scoring.recompute_trust_score",
            seller_id=str(cmd.seller_id),
            trigger="SIGNAL_CHANGE",
        )


@dataclass(frozen=True, slots=True)
class ListSellerListingsQuery:
    seller_id: UUID
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class ListingPage:
    items: tuple[Listing, ...]
    total: int
    limit: int
    offset: int


class ListSellerListings:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, query: ListSellerListingsQuery) -> ListingPage:
        limit = max(1, min(query.limit, 100))
        offset = max(0, query.offset)
        async with self._uow:
            items = await self._uow.listings.list_for_seller(
                query.seller_id, limit=limit, offset=offset
            )
            total = await self._uow.listings.count_for_seller(query.seller_id)
        return ListingPage(items=tuple(items), total=total, limit=limit, offset=offset)


class GetListing:
    """Read one listing, enforcing ownership."""

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, listing_id: UUID, seller_id: UUID) -> Listing:
        listing: Listing | None
        async with self._uow:
            listing = await self._uow.listings.get(listing_id)
        if listing is None or listing.seller_id != seller_id:
            raise EntityNotFound("listing", listing_id)
        return listing


class RequestListingAnalysis:
    """Re-run the analysers on a listing the seller already owns."""

    def __init__(self, *, uow: UnitOfWork, queue: JobQueue) -> None:
        self._uow = uow
        self._queue = queue

    async def execute(self, *, listing_id: UUID, seller_id: UUID) -> str:
        async with self._uow:
            listing = await self._uow.listings.get(listing_id)
            if listing is None:
                raise EntityNotFound("listing", listing_id)
            if listing.seller_id != seller_id:
                raise PermissionDenied("This listing belongs to another account.")
        return await self._queue.enqueue("listings.analyse_listing", listing_id=str(listing_id))


__all__ = [
    "MAX_DESCRIPTION_CHARS",
    "MAX_TITLE_CHARS",
    "CreateListing",
    "CreateListingCommand",
    "DeleteListing",
    "DeleteListingCommand",
    "GetListing",
    "ListSellerListings",
    "ListSellerListingsQuery",
    "ListingInput",
    "ListingPage",
    "ListingResult",
    "RequestListingAnalysis",
    "UpdateListing",
    "UpdateListingCommand",
]
