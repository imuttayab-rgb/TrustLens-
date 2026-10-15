"""Offers, counter-offers and transactions (feature OFF-01).

An offer lives inside a conversation about one listing. At most one offer
is ever open on a listing at a time (enforced at the database level too,
`uq_offers_listing_open`) - a new offer while one is open closes the old one
out as COUNTERED and chains to it, so "make an offer, get countered, offer
again" reads as one negotiation thread, not three unrelated rows.

Accepting an offer reserves the listing (ListingStatus.RESERVED) and opens
a Transaction. Completing or cancelling that transaction is what finally
moves the listing to SOLD or back to ACTIVE.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from trustlens.core.application.notifications import notify
from trustlens.core.application.services.listing_publication import seller_can_publish
from trustlens.core.application.use_cases.moderation import clean_report_description
from trustlens.core.domain.entities import Offer, Report, Transaction
from trustlens.core.domain.enums import (
    ListingStatus,
    OfferStatus,
    ReportCategory,
    ReportStatus,
    ReportTargetType,
    TransactionStatus,
)
from trustlens.core.domain.errors import (
    EntityNotFound,
    InvalidStateError,
    PermissionDenied,
    ValidationError,
)
from trustlens.core.domain.ports import Clock, IdGenerator, UnitOfWork

DEFAULT_OFFER_TTL_HOURS = 48


@dataclass(frozen=True, slots=True)
class CreateOfferCommand:
    conversation_id: UUID
    offered_by: UUID
    amount: float
    currency: str = "PKR"
    message: str | None = None
    ttl_hours: int = DEFAULT_OFFER_TTL_HOURS


class CreateOffer:
    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: CreateOfferCommand) -> Offer:
        if cmd.amount <= 0:
            raise ValidationError("Offer amount must be greater than zero.", field="amount")

        now = self._clock.now()
        async with self._uow:
            conversation = await self._uow.messaging.get_conversation(cmd.conversation_id)
            if conversation is None:
                raise EntityNotFound("conversation", cmd.conversation_id)
            if conversation.listing_id is None:
                raise ValidationError(
                    "This conversation isn't about a specific listing.",
                    field="conversationId",
                )

            participants = await self._uow.messaging.get_participants(conversation.id)
            if participants is None or cmd.offered_by not in participants:
                raise PermissionDenied("This conversation belongs to someone else.")
            buyer_id, seller_id = participants

            listing = await self._uow.listings.get(conversation.listing_id)
            if listing is None:
                raise EntityNotFound("listing", conversation.listing_id)
            if listing.status != ListingStatus.ACTIVE:
                raise InvalidStateError("This listing isn't open for offers right now.")
            seller = await self._uow.sellers.get(listing.seller_id)
            if seller is None or not seller_can_publish(seller):
                raise InvalidStateError(
                    "The seller must finish verification before receiving offers."
                )
            auction = await self._uow.auctions.get_for_listing(listing.id)
            if auction is not None and auction.is_open:
                raise InvalidStateError(
                    "This listing is being sold by auction. Place a bid instead."
                )

            existing_open = await self._uow.offers.get_open_for_listing(listing.id)
            parent_offer_id = None
            if existing_open is not None:
                await self._uow.offers.close(
                    existing_open.id, status=OfferStatus.COUNTERED, responded_at=now
                )
                parent_offer_id = existing_open.id

            offer = await self._uow.offers.add(
                Offer(
                    id=self._ids.new(),
                    conversation_id=conversation.id,
                    listing_id=listing.id,
                    buyer_id=buyer_id,
                    seller_id=seller_id,
                    offered_by=cmd.offered_by,
                    amount=cmd.amount,
                    currency=cmd.currency,
                    status=OfferStatus.PENDING,
                    created_at=now,
                    expires_at=now + timedelta(hours=cmd.ttl_hours),
                    message=cmd.message,
                    parent_offer_id=parent_offer_id,
                )
            )
            recipient = seller_id if cmd.offered_by == buyer_id else buyer_id
            await notify(
                self._uow,
                self._ids,
                self._clock,
                user_id=recipient,
                type="OFFER_RECEIVED",
                title="New offer",
                body=f"{cmd.amount:,.2f} {cmd.currency}",
                data={"conversationId": str(conversation.id), "offerId": str(offer.id)},
            )
            await self._uow.commit()
        return offer


class ListOffersForConversation:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, conversation_id: UUID, requester_id: UUID) -> list[Offer]:
        async with self._uow:
            participants = await self._uow.messaging.get_participants(conversation_id)
            if participants is None or requester_id not in participants:
                raise PermissionDenied("This conversation belongs to someone else.")
            return await self._uow.offers.list_for_conversation(conversation_id)


@dataclass(frozen=True, slots=True)
class RespondToOfferCommand:
    offer_id: UUID
    responder_id: UUID
    accept: bool


@dataclass(frozen=True, slots=True)
class RespondToOfferResult:
    offer: Offer
    transaction: Transaction | None


class RespondToOffer:
    """Accept or reject one open offer. Accepting reserves the listing and
    opens a Transaction in the same commit - a reservation without a
    transaction record behind it would have no way to ever complete."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: RespondToOfferCommand) -> RespondToOfferResult:
        now = self._clock.now()
        async with self._uow:
            offer = await self._uow.offers.get(cmd.offer_id)
            if offer is None:
                raise EntityNotFound("offer", cmd.offer_id)
            if not offer.is_open:
                raise InvalidStateError("This offer is no longer open.")
            if cmd.responder_id == offer.offered_by:
                raise PermissionDenied("You cannot respond to your own offer.")
            if cmd.responder_id not in (offer.buyer_id, offer.seller_id):
                raise PermissionDenied("This offer belongs to someone else.")

            if not cmd.accept:
                closed = await self._uow.offers.close(
                    offer.id, status=OfferStatus.REJECTED, responded_at=now
                )
                await notify(
                    self._uow,
                    self._ids,
                    self._clock,
                    user_id=offer.offered_by,
                    type="OFFER_REJECTED",
                    title="Offer declined",
                    body=f"Your offer of {offer.amount:,.2f} {offer.currency} was declined.",
                    data={"conversationId": str(offer.conversation_id), "offerId": str(offer.id)},
                )
                await self._uow.commit()
                return RespondToOfferResult(offer=closed, transaction=None)

            listing = await self._uow.listings.get(offer.listing_id)
            if listing is None:
                raise EntityNotFound("listing", offer.listing_id)
            if listing.status != ListingStatus.ACTIVE:
                raise InvalidStateError("This listing is no longer available.")
            seller = await self._uow.sellers.get(listing.seller_id)
            if seller is None or not seller_can_publish(seller):
                raise InvalidStateError("The seller must be verified before an offer is accepted.")

            closed = await self._uow.offers.close(
                offer.id, status=OfferStatus.ACCEPTED, responded_at=now
            )
            await self._uow.listings.update(
                dataclasses.replace(listing, status=ListingStatus.RESERVED, updated_at=now)
            )
            transaction = await self._uow.transactions.add(
                Transaction(
                    id=self._ids.new(),
                    listing_id=offer.listing_id,
                    buyer_id=offer.buyer_id,
                    seller_id=offer.seller_id,
                    offer_id=offer.id,
                    amount=offer.amount,
                    currency=offer.currency,
                    status=TransactionStatus.INITIATED,
                    created_at=now,
                )
            )
            await notify(
                self._uow,
                self._ids,
                self._clock,
                user_id=offer.offered_by,
                type="OFFER_ACCEPTED",
                title="Offer accepted",
                body=f"Your offer of {offer.amount:,.2f} {offer.currency} was accepted.",
                data={"conversationId": str(offer.conversation_id), "offerId": str(offer.id)},
            )
            await self._uow.commit()
        return RespondToOfferResult(offer=closed, transaction=transaction)


@dataclass(frozen=True, slots=True)
class ConfirmHandoverCommand:
    transaction_id: UUID
    actor_id: UUID


class ConfirmHandover:
    """The QR check-in (QR-01): whoever opens the other party's QR code and
    confirms it moves the transaction to HANDED_OVER. Deliberately the same
    mutual-trust bar as `CompleteTransaction` - either party can confirm,
    there is no cryptographic proof the two phones were ever in the same
    room, just the existing "you are a party to this deal" auth check. The
    QR code itself is a plain deep link to this action, not a signed or
    time-limited token - the transaction's own open/closed state is what
    bounds how long an old code stays meaningful."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: ConfirmHandoverCommand) -> Transaction:
        now = self._clock.now()
        async with self._uow:
            txn = await self._uow.transactions.get(cmd.transaction_id)
            if txn is None:
                raise EntityNotFound("transaction", cmd.transaction_id)
            if cmd.actor_id not in (txn.buyer_id, txn.seller_id):
                raise PermissionDenied("This transaction belongs to someone else.")
            if not txn.is_open:
                raise InvalidStateError("This transaction is already closed.")
            if txn.status == TransactionStatus.DISPUTED:
                raise InvalidStateError(
                    "This transaction is under dispute. Wait for staff to resolve it."
                )
            if txn.status == TransactionStatus.HANDED_OVER:
                raise InvalidStateError("Handover has already been confirmed.")

            updated = await self._uow.transactions.update_status(
                txn.id, status=TransactionStatus.HANDED_OVER, at=now
            )
            other = txn.seller_id if cmd.actor_id == txn.buyer_id else txn.buyer_id
            await notify(
                self._uow,
                self._ids,
                self._clock,
                user_id=other,
                type="HANDOVER_CONFIRMED",
                title="Handover confirmed",
                body="The other party confirmed the handover via QR check-in.",
                data={"transactionId": str(txn.id)},
            )
            await self._uow.commit()
        return updated


@dataclass(frozen=True, slots=True)
class CompleteTransactionCommand:
    transaction_id: UUID
    actor_id: UUID


class CompleteTransaction:
    """Either party can mark a handover done - deliberately mutual-trust
    rather than requiring both sides to confirm. `RaiseDispute` (OPS-01) is
    the escape hatch when the two sides disagree about what happened."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: CompleteTransactionCommand) -> Transaction:
        now = self._clock.now()
        async with self._uow:
            txn = await self._uow.transactions.get(cmd.transaction_id)
            if txn is None:
                raise EntityNotFound("transaction", cmd.transaction_id)
            if cmd.actor_id not in (txn.buyer_id, txn.seller_id):
                raise PermissionDenied("This transaction belongs to someone else.")
            if not txn.is_open:
                raise InvalidStateError("This transaction is already closed.")
            if txn.status == TransactionStatus.DISPUTED:
                raise InvalidStateError(
                    "This transaction is under dispute. Wait for staff to resolve it."
                )
            plan = await self._uow.installments.get_plan_for_transaction(txn.id)
            if plan is not None and plan.is_open:
                raise InvalidStateError(
                    "Finish or cancel the installment plan before marking this deal done."
                )

            updated = await self._uow.transactions.update_status(
                txn.id, status=TransactionStatus.COMPLETED, at=now
            )
            listing = await self._uow.listings.get(txn.listing_id)
            if listing is not None:
                await self._uow.listings.update(
                    dataclasses.replace(listing, status=ListingStatus.SOLD, updated_at=now)
                )
            other = txn.seller_id if cmd.actor_id == txn.buyer_id else txn.buyer_id
            await notify(
                self._uow,
                self._ids,
                self._clock,
                user_id=other,
                type="TRANSACTION_COMPLETED",
                title="Deal marked complete",
                body="The other party marked this deal done. Leave a review when you're ready.",
                data={"transactionId": str(txn.id)},
            )
            await self._uow.commit()
        return updated


@dataclass(frozen=True, slots=True)
class CancelTransactionCommand:
    transaction_id: UUID
    actor_id: UUID
    reason: str


class CancelTransaction:
    """Cancelling releases the listing back to ACTIVE - a fallen-through
    deal should not leave an item permanently unsellable."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: CancelTransactionCommand) -> Transaction:
        now = self._clock.now()
        async with self._uow:
            txn = await self._uow.transactions.get(cmd.transaction_id)
            if txn is None:
                raise EntityNotFound("transaction", cmd.transaction_id)
            if cmd.actor_id not in (txn.buyer_id, txn.seller_id):
                raise PermissionDenied("This transaction belongs to someone else.")
            if not txn.is_open:
                raise InvalidStateError("This transaction is already closed.")
            if txn.status == TransactionStatus.DISPUTED:
                raise InvalidStateError(
                    "This transaction is under dispute. Wait for staff to resolve it."
                )

            updated = await self._uow.transactions.update_status(
                txn.id, status=TransactionStatus.CANCELLED, at=now, cancel_reason=cmd.reason
            )
            listing = await self._uow.listings.get(txn.listing_id)
            if listing is not None and listing.status == ListingStatus.RESERVED:
                seller = await self._uow.sellers.get(listing.seller_id)
                await self._uow.listings.update(
                    dataclasses.replace(
                        listing,
                        status=(
                            ListingStatus.ACTIVE
                            if seller is not None and seller_can_publish(seller)
                            else ListingStatus.DRAFT
                        ),
                        updated_at=now,
                    )
                )
            other = txn.seller_id if cmd.actor_id == txn.buyer_id else txn.buyer_id
            await notify(
                self._uow,
                self._ids,
                self._clock,
                user_id=other,
                type="TRANSACTION_CANCELLED",
                title="Deal cancelled",
                body=cmd.reason or "The other party cancelled this deal.",
                data={"transactionId": str(txn.id)},
            )
            await self._uow.commit()
        return updated


@dataclass(frozen=True, slots=True)
class RaiseDisputeCommand:
    transaction_id: UUID
    actor_id: UUID
    category: ReportCategory
    description: str


class RaiseDispute:
    """A party contests a transaction (OPS-01). Reuses MOD-01's generic
    `Report` rather than a parallel Dispute entity - a dispute is exactly
    "a report, targeting a transaction, that also freezes it" so neither
    side can unilaterally complete or cancel out from under a disagreement
    while staff look at it. `ResolveDispute` below is the other half."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: RaiseDisputeCommand) -> Transaction:
        description = clean_report_description(cmd.description)
        now = self._clock.now()
        async with self._uow:
            txn = await self._uow.transactions.get(cmd.transaction_id)
            if txn is None:
                raise EntityNotFound("transaction", cmd.transaction_id)
            if cmd.actor_id not in (txn.buyer_id, txn.seller_id):
                raise PermissionDenied("This transaction belongs to someone else.")
            if not txn.is_open:
                raise InvalidStateError("This transaction is already closed.")
            if txn.status == TransactionStatus.DISPUTED:
                raise InvalidStateError("This transaction is already under dispute.")

            await self._uow.reports.add(
                Report(
                    id=self._ids.new(),
                    reporter_id=cmd.actor_id,
                    target_type=ReportTargetType.TRANSACTION,
                    target_id=txn.id,
                    category=cmd.category,
                    description=description,
                    status=ReportStatus.OPEN,
                    created_at=now,
                )
            )
            updated = await self._uow.transactions.update_status(
                txn.id, status=TransactionStatus.DISPUTED, at=now
            )
            other = txn.seller_id if cmd.actor_id == txn.buyer_id else txn.buyer_id
            await notify(
                self._uow,
                self._ids,
                self._clock,
                user_id=other,
                type="TRANSACTION_DISPUTED",
                title="Deal disputed",
                body="The other party raised a dispute on this deal. Staff will review it.",
                data={"transactionId": str(txn.id)},
            )
            await self._uow.commit()
        return updated


@dataclass(frozen=True, slots=True)
class ResolveDisputeCommand:
    transaction_id: UUID
    resolver_id: UUID
    #: The only two outcomes a dispute can land on - same terminal pair
    #: every other transaction path already uses, so staff aren't inventing
    #: a third state nothing else in the system understands.
    outcome: TransactionStatus


class ResolveDispute:
    """Staff-only close-out of a disputed transaction (OPS-01) - the report
    itself is resolved separately via `ResolveReport` (documenting what was
    decided and why); this is the other half, unsticking the transaction's
    own state once a verdict is reached. Without this, `RaiseDispute` would
    freeze a transaction with no way to ever move it again."""

    def __init__(self, *, uow: UnitOfWork, clock: Clock, ids: IdGenerator) -> None:
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def execute(self, cmd: ResolveDisputeCommand) -> Transaction:
        if cmd.outcome not in (TransactionStatus.COMPLETED, TransactionStatus.CANCELLED):
            raise ValidationError(
                "A dispute can only resolve to completed or cancelled.", field="outcome"
            )
        now = self._clock.now()
        async with self._uow:
            txn = await self._uow.transactions.get(cmd.transaction_id)
            if txn is None:
                raise EntityNotFound("transaction", cmd.transaction_id)
            if txn.status != TransactionStatus.DISPUTED:
                raise InvalidStateError("This transaction isn't under dispute.")

            cancel_reason = (
                "Resolved by staff" if cmd.outcome == TransactionStatus.CANCELLED else None
            )
            updated = await self._uow.transactions.update_status(
                txn.id, status=cmd.outcome, at=now, cancel_reason=cancel_reason
            )
            listing = await self._uow.listings.get(txn.listing_id)
            if listing is not None:
                if cmd.outcome == TransactionStatus.COMPLETED:
                    await self._uow.listings.update(
                        dataclasses.replace(listing, status=ListingStatus.SOLD, updated_at=now)
                    )
                elif listing.status == ListingStatus.RESERVED:
                    seller = await self._uow.sellers.get(listing.seller_id)
                    await self._uow.listings.update(
                        dataclasses.replace(
                            listing,
                            status=(
                                ListingStatus.ACTIVE
                                if seller is not None and seller_can_publish(seller)
                                else ListingStatus.DRAFT
                            ),
                            updated_at=now,
                        )
                    )
            for user_id in (txn.buyer_id, txn.seller_id):
                await notify(
                    self._uow,
                    self._ids,
                    self._clock,
                    user_id=user_id,
                    type="DISPUTE_RESOLVED",
                    title="Dispute resolved",
                    body=f"Staff resolved this dispute: {cmd.outcome.value.title()}.",
                    data={"transactionId": str(txn.id)},
                )
            await self._uow.commit()
        return updated


class ListMyTransactions:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[Transaction]:
        bounded = max(1, min(limit, 50))
        async with self._uow:
            return await self._uow.transactions.list_for_user(
                user_id, limit=bounded, offset=max(0, offset)
            )


__all__ = [
    "DEFAULT_OFFER_TTL_HOURS",
    "CancelTransaction",
    "CancelTransactionCommand",
    "CompleteTransaction",
    "CompleteTransactionCommand",
    "ConfirmHandover",
    "ConfirmHandoverCommand",
    "CreateOffer",
    "CreateOfferCommand",
    "ListMyTransactions",
    "ListOffersForConversation",
    "RaiseDispute",
    "RaiseDisputeCommand",
    "ResolveDispute",
    "ResolveDisputeCommand",
    "RespondToOffer",
    "RespondToOfferCommand",
    "RespondToOfferResult",
]
