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
    CancelTransaction,
    CancelTransactionCommand,
    CompleteTransaction,
    CompleteTransactionCommand,
    ConfirmHandover,
    ConfirmHandoverCommand,
    CreateOffer,
    CreateOfferCommand,
    ListMyTransactions,
    ListOffersForConversation,
    RespondToOffer,
    RespondToOfferCommand,
)
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.commerce import (
    CancelTransactionRequest,
    CreateOfferRequest,
    OfferResponse,
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


def _to_transaction_response(txn: Any) -> TransactionResponse:
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
                _to_transaction_response(result.transaction).model_dump(by_alias=True)
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
        [_to_transaction_response(t).model_dump(by_alias=True) for t in transactions],
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
        _to_transaction_response(txn).model_dump(by_alias=True), request_id=meta.request_id
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
        _to_transaction_response(txn).model_dump(by_alias=True), request_id=meta.request_id
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
        _to_transaction_response(txn).model_dump(by_alias=True), request_id=meta.request_id
    )


__all__ = ["router"]
