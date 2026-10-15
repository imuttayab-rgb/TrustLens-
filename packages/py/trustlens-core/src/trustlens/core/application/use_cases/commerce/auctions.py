"""Auctions and bidding (feature AUC-01).

A distinct mechanism from OFF-01's offers, not a reuse of them: bidding is
public and time-boxed, an offer is one buyer negotiating privately. Once an
auction closes with a qualifying bid, though, everything downstream *is* a
reuse - the winning bid becomes a Conversation, an ACCEPTED `Offer` and a
`Transaction`, the exact shapes OFF-01 already produces from an accepted
offer. That is deliberate: a winning bidder gets the same handover QR,
dispute path and installment option a negotiated deal gets, for free,
instead of a second, parallel "what happens after you win" system.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from trustlens.core.application.notifications import notify
from trustlens.core.application.services.listing_publication import seller_can_publish
from trustlens.core.domain.entities import (
    Auction,
    Bid,
    Conversation,
    Listing,
    Message,
    Offer,
    Transaction,
)
from trustlens.core.domain.enums import (
    AuctionStatus,
    ListingStatus,
    OfferStatus,
    TransactionStatus,
)
from trustlens.core.domain.errors import (
    EntityNotFound,
    InvalidStateError,
    PermissionDenied,
    ValidationError,
)
from trustlens.core.domain.ports import Clock, IdGenerator, UnitOfWork

MIN_DURATION_HOURS = 1
MAX_DURATION_HOURS = 24 * 14  # two weeks


@dataclass(frozen=True, slots=True)
class CreateAuctionCommand:
    listing_id: UUID
    seller_id: UUID
    starting_price: float
    currency: str
    duration_hours: int
    reserve_price: float | None = None


class CreateAuction:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: CreateAuctionCommand) -> Auction:
        if cmd.starting_price <= 0:
            raise ValidationError(
                "The starting price must be greater than zero.", field="startingPrice"
            )
        if not (MIN_DURATION_HOURS <= cmd.duration_hours <= MAX_DURATION_HOURS):
            raise ValidationError(
                f"Choose a duration between {MIN_DURATION_HOURS} and {MAX_DURATION_HOURS} hours.",
                field="durationHours",
            )
        if cmd.reserve_price is not None and cmd.reserve_price < cmd.starting_price:
            raise ValidationError(
                "The reserve price can't be below the starting price.", field="reservePrice"
            )

        now = self._clock.now()
        async with self._uow:
            listing = await self._uow.listings.get(cmd.listing_id)
            if listing is None:
                raise EntityNotFound("listing", cmd.listing_id)
            seller = await self._uow.sellers.get(listing.seller_id)
            if seller is None or seller.user_id != cmd.seller_id:
                raise PermissionDenied("This listing belongs to someone else.")
            if listing.status != ListingStatus.ACTIVE:
                raise InvalidStateError("This listing isn't open for an auction right now.")
            if not seller_can_publish(seller):
                raise InvalidStateError("Complete seller verification before starting an auction.")

            existing = await self._uow.auctions.get_for_listing(listing.id)
            if existing is not None and existing.is_open:
                raise InvalidStateError("This listing already has an active auction.")

            auction = await self._uow.auctions.add(
                Auction(
                    id=self._ids.new(),
                    listing_id=listing.id,
                    seller_id=cmd.seller_id,
                    starting_price=cmd.starting_price,
                    currency=cmd.currency,
                    ends_at=now + timedelta(hours=cmd.duration_hours),
                    status=AuctionStatus.ACTIVE,
                    created_at=now,
                    reserve_price=cmd.reserve_price,
                )
            )
            await self._uow.commit()
        return auction


@dataclass(frozen=True, slots=True)
class PlaceBidCommand:
    auction_id: UUID
    bidder_id: UUID
    amount: float


class PlaceBid:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: PlaceBidCommand) -> Bid:
        now = self._clock.now()
        async with self._uow:
            auction = await self._uow.auctions.get(cmd.auction_id)
            if auction is None:
                raise EntityNotFound("auction", cmd.auction_id)
            if not auction.is_open or now >= auction.ends_at:
                raise InvalidStateError("This auction has ended.")
            if cmd.bidder_id == auction.seller_id:
                raise PermissionDenied("You cannot bid on your own listing.")
            listing = await self._uow.listings.get(auction.listing_id)
            seller = await self._uow.sellers.get_by_user(auction.seller_id)
            if (
                listing is None
                or listing.status != ListingStatus.ACTIVE
                or seller is None
                or not seller_can_publish(seller)
            ):
                raise InvalidStateError(
                    "The seller must be verified and the listing public to bid."
                )

            highest = await self._uow.auctions.get_highest_bid(auction.id)
            if highest is None:
                if cmd.amount < auction.starting_price:
                    raise ValidationError(
                        f"Bid at least {auction.starting_price:,.2f} {auction.currency}.",
                        field="amount",
                    )
            elif cmd.amount <= highest.amount:
                raise ValidationError(
                    f"Bid more than the current highest "
                    f"({highest.amount:,.2f} {auction.currency}).",
                    field="amount",
                )

            bid = await self._uow.auctions.add_bid(
                Bid(
                    id=self._ids.new(),
                    auction_id=auction.id,
                    bidder_id=cmd.bidder_id,
                    amount=cmd.amount,
                    created_at=now,
                )
            )

            await notify(
                self._uow,
                self._ids,
                self._clock,
                user_id=auction.seller_id,
                type="AUCTION_BID_PLACED",
                title="New bid",
                body=f"{cmd.amount:,.2f} {auction.currency}",
                data={"auctionId": str(auction.id), "listingId": str(auction.listing_id)},
            )
            if highest is not None and highest.bidder_id != cmd.bidder_id:
                await notify(
                    self._uow,
                    self._ids,
                    self._clock,
                    user_id=highest.bidder_id,
                    type="AUCTION_OUTBID",
                    title="You've been outbid",
                    body=(
                        f"Someone bid {cmd.amount:,.2f} {auction.currency}. "
                        "You can bid again before it ends."
                    ),
                    data={"auctionId": str(auction.id), "listingId": str(auction.listing_id)},
                )

            await self._uow.commit()
        return bid


class CloseAuction:
    """Closes one ended auction - called by the worker sweep (`cron`, every
    few minutes), or harmlessly a second time if the same one is already
    closed (idempotent no-op). A qualifying winner (a highest bid meeting
    the reserve, if any) gets a Conversation, an ACCEPTED Offer and an
    INITIATED Transaction - the same shapes OFF-01 produces from an
    accepted offer, so handover/dispute/installments all work unchanged
    from here on."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, auction_id: UUID) -> Auction:
        now = self._clock.now()
        async with self._uow:
            auction = await self._uow.auctions.get(auction_id)
            if auction is None:
                raise EntityNotFound("auction", auction_id)
            if not auction.is_open:
                return auction
            if now < auction.ends_at:
                raise InvalidStateError("This auction hasn't ended yet.")

            highest = await self._uow.auctions.get_highest_bid(auction.id)
            listing = await self._uow.listings.get(auction.listing_id)
            seller = await self._uow.sellers.get_by_user(auction.seller_id)
            still_public = (
                listing is not None
                and listing.status == ListingStatus.ACTIVE
                and seller is not None
                and seller_can_publish(seller)
            )
            winning_bid = (
                highest
                if still_public and highest is not None
                and (auction.reserve_price is None or highest.amount >= auction.reserve_price)
                else None
            )

            closed = await self._uow.auctions.update(
                dataclasses.replace(
                    auction,
                    status=AuctionStatus.ENDED,
                    ended_at=now,
                    winning_bid_id=winning_bid.id if winning_bid else None,
                )
            )

            if winning_bid is not None and listing is not None:
                await self._settle(auction, winning_bid, listing, now)
            else:
                if highest is not None and not still_public:
                    await notify(
                        self._uow, self._ids, self._clock,
                        user_id=highest.bidder_id,
                        type="AUCTION_ENDED_NO_WINNER",
                        title="Auction closed without a sale",
                        body="The listing is no longer public or the seller needs verification.",
                        data={"auctionId": str(auction.id), "listingId": str(auction.listing_id)},
                    )
                await notify(
                    self._uow,
                    self._ids,
                    self._clock,
                    user_id=auction.seller_id,
                    type="AUCTION_ENDED_NO_WINNER",
                    title="Auction ended with no winner",
                    body=(
                        "Seller verification or listing publication is no longer valid."
                        if not still_public
                        else "No bid met your reserve price."
                        if highest is not None
                        else "Nobody placed a bid before it ended."
                    ),
                    data={"auctionId": str(auction.id), "listingId": str(auction.listing_id)},
                )

            await self._uow.commit()
        return closed

    async def _settle(
        self, auction: Auction, winning_bid: Bid, listing: Listing, now: datetime
    ) -> None:
        listing_id = auction.listing_id
        seller_profile_id = listing.seller_id

        conversation = await self._uow.messaging.find_conversation(
            buyer_id=winning_bid.bidder_id, seller_id=seller_profile_id, listing_id=listing_id
        )
        if conversation is None:
            conversation = await self._uow.messaging.create_conversation(
                Conversation(
                    id=self._ids.new(),
                    seller_id=seller_profile_id,
                    buyer_id=winning_bid.bidder_id,
                    created_at=now,
                    last_message_at=now,
                    listing_id=listing_id,
                    listing_title=listing.title,
                    listing_price=winning_bid.amount,
                    listing_currency=auction.currency,
                )
            )
        await self._uow.messaging.add_message(
            Message(
                id=self._ids.new(),
                conversation_id=conversation.id,
                sender_id=auction.seller_id,
                body=(
                    f"Auction won! Winning bid: {winning_bid.amount:,.2f} {auction.currency}. "
                    "Arrange handover here."
                ),
                created_at=now,
            )
        )
        await self._uow.messaging.touch_conversation(conversation.id, at=now)

        offer = await self._uow.offers.add(
            Offer(
                id=self._ids.new(),
                conversation_id=conversation.id,
                listing_id=listing_id,
                buyer_id=winning_bid.bidder_id,
                seller_id=auction.seller_id,
                offered_by=winning_bid.bidder_id,
                amount=winning_bid.amount,
                currency=auction.currency,
                status=OfferStatus.ACCEPTED,
                created_at=now,
                expires_at=now,
                responded_at=now,
            )
        )

        await self._uow.listings.update(
            dataclasses.replace(listing, status=ListingStatus.RESERVED, updated_at=now)
        )

        await self._uow.transactions.add(
            Transaction(
                id=self._ids.new(),
                listing_id=listing_id,
                buyer_id=winning_bid.bidder_id,
                seller_id=auction.seller_id,
                offer_id=offer.id,
                amount=winning_bid.amount,
                currency=auction.currency,
                status=TransactionStatus.INITIATED,
                created_at=now,
            )
        )

        winners = (
            (winning_bid.bidder_id, "AUCTION_WON"),
            (auction.seller_id, "AUCTION_ENDED_SOLD"),
        )
        for user_id, kind in winners:
            await notify(
                self._uow,
                self._ids,
                self._clock,
                user_id=user_id,
                type=kind,
                title="You won the auction!" if kind == "AUCTION_WON" else "Auction sold",
                body=f"Winning bid: {winning_bid.amount:,.2f} {auction.currency}.",
                data={"auctionId": str(auction.id), "listingId": str(listing_id)},
            )


class GetAuction:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, auction_id: UUID) -> Auction:
        async with self._uow:
            auction = await self._uow.auctions.get(auction_id)
        if auction is None:
            raise EntityNotFound("auction", auction_id)
        return auction


class GetAuctionForListing:
    """The most recent auction for a listing, whatever its status - lets a
    seller's dashboard or the public listing page find an auction without
    already knowing its id."""

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, listing_id: UUID) -> Auction | None:
        async with self._uow:
            return await self._uow.auctions.get_for_listing(listing_id)


class ListBidsForAuction:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, auction_id: UUID) -> list[Bid]:
        async with self._uow:
            return await self._uow.auctions.list_bids(auction_id)


__all__ = [
    "MAX_DURATION_HOURS",
    "MIN_DURATION_HOURS",
    "CloseAuction",
    "CreateAuction",
    "CreateAuctionCommand",
    "GetAuction",
    "GetAuctionForListing",
    "ListBidsForAuction",
    "PlaceBid",
    "PlaceBidCommand",
]
