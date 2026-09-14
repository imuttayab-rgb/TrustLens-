"""Offers and transactions endpoints (feature OFF-01, plus QR-01's handover
confirmation).

Offers live under /conversations/{id}/offers, matching the spec's own
proposed route shape; everything else (responding, completing, cancelling,
confirming a QR handover, listing my transactions) lives under /offers and
/transactions, and /me/transactions - the same "any signed-in user, no role
check" convention /me/favorites and /me/conversations already use, since
either the buyer or the seller can be on either side of a
response/complete/cancel/handover action.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, status

from trustlens.core.application.use_cases.commerce import (
    CancelInstallmentPlan,
    CancelInstallmentPlanCommand,
    CancelTransaction,
    CancelTransactionCommand,
    CompleteTransaction,
    CompleteTransactionCommand,
    ConfirmHandover,
    ConfirmHandoverCommand,
    CreateAuction,
    CreateAuctionCommand,
    CreateInstallmentPlan,
    CreateInstallmentPlanCommand,
    CreateOffer,
    CreateOfferCommand,
    GetAuction,
    GetInstallmentPlan,
    ListBidsForAuction,
    ListMyTransactions,
    ListOffersForConversation,
    PayInstallment,
    PayInstallmentCommand,
    PlaceBid,
    PlaceBidCommand,
    RaiseDispute,
    RaiseDisputeCommand,
    RespondToOffer,
    RespondToOfferCommand,
)
from trustlens.core.domain.enums import ReportCategory
from trustlens.core.domain.errors import ValidationError
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.commerce import (
    AuctionResponse,
    BidResponse,
    CancelTransactionRequest,
    CreateAuctionRequest,
    CreateInstallmentPlanRequest,
    CreateOfferRequest,
    InstallmentPlanResponse,
    InstallmentResponse,
    OfferResponse,
    PlaceBidRequest,
    RaiseDisputeRequest,
    RespondToOfferRequest,
    TransactionResponse,
)
from trustlens_api.api.v1.schemas.common import envelope

router = APIRouter(tags=["Commerce"])


def _to_offer_response(offer: Any) -> OfferResponse:
    return OfferResponse(
        id=offer.id,
        conversation_id=offer.conversation_id,
        listing_id=offer.listing_id,
        buyer_id=offer.buyer_id,
        seller_id=offer.seller_id,
        offered_by=offer.offered_by,
        amount=offer.amount,
        currency=offer.currency,
        status=offer.status.value,
        created_at=offer.created_at,
        expires_at=offer.expires_at,
        message=offer.message,
        parent_offer_id=offer.parent_offer_id,
        responded_at=offer.responded_at,
    )


def to_transaction_response(txn: Any) -> TransactionResponse:
    return TransactionResponse(
        id=txn.id,
        listing_id=txn.listing_id,
        buyer_id=txn.buyer_id,
        seller_id=txn.seller_id,
        offer_id=txn.offer_id,
        amount=txn.amount,
        currency=txn.currency,
        status=txn.status.value,
        created_at=txn.created_at,
        updated_at=txn.updated_at,
        completed_at=txn.completed_at,
        cancelled_at=txn.cancelled_at,
        cancel_reason=txn.cancel_reason,
    )


@router.post(
    "/conversations/{conversation_id}/offers",
    status_code=status.HTTP_201_CREATED,
    summary="Make an offer or counter-offer",
)
async def create_offer(
    conversation_id: UUID,
    body: CreateOfferRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    offer = await CreateOffer(uow=uow, clock=container.clock, ids=container.ids).execute(
        CreateOfferCommand(
            conversation_id=conversation_id,
            offered_by=actor.user_id,
            amount=body.amount,
            currency=body.currency,
            message=body.message,
            ttl_hours=body.ttl_hours,
        )
    )
    return envelope(_to_offer_response(offer).model_dump(by_alias=True), request_id=meta.request_id)


@router.get(
    "/conversations/{conversation_id}/offers",
    summary="The offer/counter-offer history for one conversation",
)
async def list_offers(
    conversation_id: UUID, actor: ActorDep, uow: UowDep, meta: MetaDep
) -> dict[str, Any]:
    assert actor.user_id is not None
    offers = await ListOffersForConversation(uow=uow).execute(conversation_id, actor.user_id)
    return envelope(
        [_to_offer_response(o).model_dump(by_alias=True) for o in offers],
        request_id=meta.request_id,
    )


@router.post("/offers/{offer_id}/respond", summary="Accept or reject an open offer")
async def respond_to_offer(
    offer_id: UUID,
    body: RespondToOfferRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    result = await RespondToOffer(uow=uow, clock=container.clock, ids=container.ids).execute(
        RespondToOfferCommand(offer_id=offer_id, responder_id=actor.user_id, accept=body.accept)
    )
    return envelope(
        {
            "offer": _to_offer_response(result.offer).model_dump(by_alias=True),
            "transaction": (
                to_transaction_response(result.transaction).model_dump(by_alias=True)
                if result.transaction is not None
                else None
            ),
        },
        request_id=meta.request_id,
    )


@router.get("/me/transactions", summary="My transactions, buying or selling")
async def list_my_transactions(actor: ActorDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    assert actor.user_id is not None
    transactions = await ListMyTransactions(uow=uow).execute(actor.user_id)
    return envelope(
        [to_transaction_response(t).model_dump(by_alias=True) for t in transactions],
        request_id=meta.request_id,
    )


@router.post(
    "/transactions/{transaction_id}/handover",
    summary="Confirm handover via QR check-in (QR-01)",
)
async def confirm_handover(
    transaction_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    txn = await ConfirmHandover(uow=uow, clock=container.clock, ids=container.ids).execute(
        ConfirmHandoverCommand(transaction_id=transaction_id, actor_id=actor.user_id)
    )
    return envelope(
        to_transaction_response(txn).model_dump(by_alias=True), request_id=meta.request_id
    )


@router.post("/transactions/{transaction_id}/complete", summary="Mark a handover as done")
async def complete_transaction(
    transaction_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    txn = await CompleteTransaction(uow=uow, clock=container.clock, ids=container.ids).execute(
        CompleteTransactionCommand(transaction_id=transaction_id, actor_id=actor.user_id)
    )
    return envelope(
        to_transaction_response(txn).model_dump(by_alias=True), request_id=meta.request_id
    )


@router.post("/transactions/{transaction_id}/cancel", summary="Cancel a transaction")
async def cancel_transaction(
    transaction_id: UUID,
    body: CancelTransactionRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    txn = await CancelTransaction(uow=uow, clock=container.clock, ids=container.ids).execute(
        CancelTransactionCommand(
            transaction_id=transaction_id, actor_id=actor.user_id, reason=body.reason
        )
    )
    return envelope(
        to_transaction_response(txn).model_dump(by_alias=True), request_id=meta.request_id
    )


@router.post(
    "/transactions/{transaction_id}/dispute",
    summary="Raise a dispute on a transaction",
    description=(
        "Freezes the transaction (neither party can complete or cancel it) "
        "and opens a report in the staff queue, the same one MOD-01's "
        "listing/seller/message reports already go through."
    ),
)
async def raise_dispute(
    transaction_id: UUID,
    body: RaiseDisputeRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    try:
        category = ReportCategory(body.category)
    except ValueError as exc:
        raise ValidationError(f"Invalid category: {body.category}", field="category") from exc

    txn = await RaiseDispute(uow=uow, clock=container.clock, ids=container.ids).execute(
        RaiseDisputeCommand(
            transaction_id=transaction_id,
            actor_id=actor.user_id,
            category=category,
            description=body.description,
        )
    )
    return envelope(
        to_transaction_response(txn).model_dump(by_alias=True), request_id=meta.request_id
    )


# ── Installments (PAY-01) ───────────────────────────────────────────
# A payment *schedule*, not a payment processor - see the use-case module's
# docstring for why "sandbox" is the honest word for this.


def _to_installment_response(installment: Any) -> InstallmentResponse:
    return InstallmentResponse(
        id=installment.id,
        sequence_number=installment.sequence_number,
        amount=installment.amount,
        due_at=installment.due_at,
        status=installment.status.value,
        paid_at=installment.paid_at,
        paid_by=installment.paid_by,
    )


def _to_installment_plan_response(detail: Any) -> InstallmentPlanResponse:
    plan = detail.plan
    return InstallmentPlanResponse(
        id=plan.id,
        transaction_id=plan.transaction_id,
        buyer_id=plan.buyer_id,
        seller_id=plan.seller_id,
        total_amount=plan.total_amount,
        currency=plan.currency,
        installment_count=plan.installment_count,
        status=plan.status.value,
        created_at=plan.created_at,
        cancelled_at=plan.cancelled_at,
        installments=[_to_installment_response(i) for i in detail.installments],
    )


@router.post(
    "/transactions/{transaction_id}/installment-plan",
    status_code=status.HTTP_201_CREATED,
    summary="Set up a buy-now-pay-later plan for a transaction",
)
async def create_installment_plan(
    transaction_id: UUID,
    body: CreateInstallmentPlanRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    await CreateInstallmentPlan(uow=uow, clock=container.clock, ids=container.ids).execute(
        CreateInstallmentPlanCommand(
            transaction_id=transaction_id,
            actor_id=actor.user_id,
            installment_count=body.installment_count,
            frequency_days=body.frequency_days,
        )
    )
    detail = await GetInstallmentPlan(uow=uow).execute(transaction_id, actor.user_id)
    assert detail is not None
    return envelope(
        _to_installment_plan_response(detail).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.get(
    "/transactions/{transaction_id}/installment-plan",
    summary="View the installment plan for a transaction, if any",
)
async def get_installment_plan(
    transaction_id: UUID,
    actor: ActorDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    detail = await GetInstallmentPlan(uow=uow).execute(transaction_id, actor.user_id)
    return envelope(
        _to_installment_plan_response(detail).model_dump(by_alias=True) if detail else None,
        request_id=meta.request_id,
    )


@router.post("/installments/{installment_id}/pay", summary="Mark one installment paid")
async def pay_installment(
    installment_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    paid = await PayInstallment(uow=uow, clock=container.clock, ids=container.ids).execute(
        PayInstallmentCommand(installment_id=installment_id, actor_id=actor.user_id)
    )
    return envelope(
        _to_installment_response(paid).model_dump(by_alias=True), request_id=meta.request_id
    )


@router.post("/installment-plans/{plan_id}/cancel", summary="Cancel an installment plan")
async def cancel_installment_plan(
    plan_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    plan = await CancelInstallmentPlan(uow=uow, clock=container.clock, ids=container.ids).execute(
        CancelInstallmentPlanCommand(plan_id=plan_id, actor_id=actor.user_id)
    )
    return envelope({"id": str(plan.id), "status": plan.status.value}, request_id=meta.request_id)


# ── Auctions (AUC-01) ────────────────────────────────────────────────


def _to_auction_response(
    auction: Any, *, current_price: float | None, bid_count: int
) -> AuctionResponse:
    return AuctionResponse(
        id=auction.id,
        listing_id=auction.listing_id,
        seller_id=auction.seller_id,
        starting_price=auction.starting_price,
        currency=auction.currency,
        ends_at=auction.ends_at,
        status=auction.status.value,
        created_at=auction.created_at,
        reserve_price=auction.reserve_price,
        winning_bid_id=auction.winning_bid_id,
        ended_at=auction.ended_at,
        current_price=current_price,
        bid_count=bid_count,
    )


def _to_bid_response(bid: Any) -> BidResponse:
    return BidResponse(
        id=bid.id,
        auction_id=bid.auction_id,
        bidder_id=bid.bidder_id,
        amount=bid.amount,
        created_at=bid.created_at,
    )


@router.post(
    "/listings/{listing_id}/auction",
    status_code=status.HTTP_201_CREATED,
    summary="List a listing as an auction instead of a fixed price",
)
async def create_auction(
    listing_id: UUID,
    body: CreateAuctionRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    auction = await CreateAuction(uow=uow, clock=container.clock, ids=container.ids).execute(
        CreateAuctionCommand(
            listing_id=listing_id,
            seller_id=actor.user_id,
            starting_price=body.starting_price,
            currency=body.currency,
            duration_hours=body.duration_hours,
            reserve_price=body.reserve_price,
        )
    )
    return envelope(
        _to_auction_response(auction, current_price=None, bid_count=0).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.get("/auctions/{auction_id}", summary="View one auction")
async def get_auction(
    auction_id: UUID, actor: ActorDep, uow: UowDep, meta: MetaDep
) -> dict[str, Any]:
    assert actor.user_id is not None
    auction = await GetAuction(uow=uow).execute(auction_id)
    bids = await ListBidsForAuction(uow=uow).execute(auction_id)
    current_price = bids[0].amount if bids else None
    return envelope(
        _to_auction_response(auction, current_price=current_price, bid_count=len(bids)).model_dump(
            by_alias=True
        ),
        request_id=meta.request_id,
    )


@router.get("/auctions/{auction_id}/bids", summary="Bid history for one auction, highest first")
async def list_bids(
    auction_id: UUID, actor: ActorDep, uow: UowDep, meta: MetaDep
) -> dict[str, Any]:
    assert actor.user_id is not None
    bids = await ListBidsForAuction(uow=uow).execute(auction_id)
    return envelope(
        [_to_bid_response(b).model_dump(by_alias=True) for b in bids], request_id=meta.request_id
    )


@router.post(
    "/auctions/{auction_id}/bids", status_code=status.HTTP_201_CREATED, summary="Place a bid"
)
async def place_bid(
    auction_id: UUID,
    body: PlaceBidRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    bid = await PlaceBid(uow=uow, clock=container.clock, ids=container.ids).execute(
        PlaceBidCommand(auction_id=auction_id, bidder_id=actor.user_id, amount=body.amount)
    )
    return envelope(_to_bid_response(bid).model_dump(by_alias=True), request_id=meta.request_id)


__all__ = ["router"]
