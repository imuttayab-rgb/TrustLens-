"""Commerce repositories. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from trustlens.core.domain import entities as ent
from trustlens.core.domain import enums as e
from trustlens.db import mappers as map_
from trustlens.db import models as m


class SqlOfferRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, offer: ent.Offer) -> ent.Offer:
        self._s.add(
            m.OfferModel(
                id=offer.id,
                conversation_id=offer.conversation_id,
                listing_id=offer.listing_id,
                buyer_id=offer.buyer_id,
                seller_id=offer.seller_id,
                offered_by=offer.offered_by,
                amount=offer.amount,
                currency=offer.currency,
                status=offer.status,
                created_at=offer.created_at,
                expires_at=offer.expires_at,
                message=offer.message,
                parent_offer_id=offer.parent_offer_id,
            )
        )
        await self._s.flush()
        return offer

    async def get(self, offer_id: UUID) -> ent.Offer | None:
        row = await self._s.get(m.OfferModel, offer_id)
        return map_.to_offer(row) if row else None

    async def list_for_conversation(self, conversation_id: UUID) -> list[ent.Offer]:
        stmt = (
            select(m.OfferModel)
            .where(m.OfferModel.conversation_id == conversation_id)
            .order_by(m.OfferModel.created_at.asc())
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_offer(r) for r in rows]

    async def get_open_for_listing(self, listing_id: UUID) -> ent.Offer | None:
        stmt = select(m.OfferModel).where(
            m.OfferModel.listing_id == listing_id, m.OfferModel.status == e.OfferStatus.PENDING
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_offer(row) if row else None

    async def close(
        self, offer_id: UUID, *, status: e.OfferStatus, responded_at: datetime
    ) -> ent.Offer:
        await self._s.execute(
            update(m.OfferModel)
            .where(m.OfferModel.id == offer_id)
            .values(status=status, responded_at=responded_at)
        )
        row = await self._s.get(m.OfferModel, offer_id)
        assert row is not None
        return map_.to_offer(row)


class SqlTransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, transaction: ent.Transaction) -> ent.Transaction:
        self._s.add(
            m.TransactionModel(
                id=transaction.id,
                listing_id=transaction.listing_id,
                buyer_id=transaction.buyer_id,
                seller_id=transaction.seller_id,
                offer_id=transaction.offer_id,
                amount=transaction.amount,
                currency=transaction.currency,
                status=transaction.status,
                created_at=transaction.created_at,
            )
        )
        await self._s.flush()
        return transaction

    async def get(self, transaction_id: UUID) -> ent.Transaction | None:
        row = await self._s.get(m.TransactionModel, transaction_id)
        return map_.to_transaction(row) if row else None

    async def get_open_for_listing(self, listing_id: UUID) -> ent.Transaction | None:
        stmt = select(m.TransactionModel).where(
            m.TransactionModel.listing_id == listing_id,
            m.TransactionModel.status.notin_(
                [e.TransactionStatus.COMPLETED, e.TransactionStatus.CANCELLED]
            ),
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_transaction(row) if row else None

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[ent.Transaction]:
        stmt = (
            select(m.TransactionModel)
            .where(
                or_(
                    m.TransactionModel.buyer_id == user_id,
                    m.TransactionModel.seller_id == user_id,
                )
            )
            .order_by(m.TransactionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_transaction(r) for r in rows]

    async def count_completed_for_seller(self, seller_user_id: UUID) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count(m.TransactionModel.id)).where(
                        m.TransactionModel.seller_id == seller_user_id,
                        m.TransactionModel.status == e.TransactionStatus.COMPLETED,
                    )
                )
            ).scalar_one()
        )

    async def update_status(
        self,
        transaction_id: UUID,
        *,
        status: e.TransactionStatus,
        at: datetime,
        cancel_reason: str | None = None,
    ) -> ent.Transaction:
        values: dict[str, Any] = {"status": status, "updated_at": at}
        if status == e.TransactionStatus.COMPLETED:
            values["completed_at"] = at
        if status == e.TransactionStatus.CANCELLED:
            values["cancelled_at"] = at
            values["cancel_reason"] = cancel_reason
        await self._s.execute(
            update(m.TransactionModel)
            .where(m.TransactionModel.id == transaction_id)
            .values(**values)
        )
        row = await self._s.get(m.TransactionModel, transaction_id)
        assert row is not None
        return map_.to_transaction(row)


class SqlInstallmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add_plan(self, plan: ent.InstallmentPlan) -> ent.InstallmentPlan:
        self._s.add(
            m.InstallmentPlanModel(
                id=plan.id,
                transaction_id=plan.transaction_id,
                buyer_id=plan.buyer_id,
                seller_id=plan.seller_id,
                total_amount=plan.total_amount,
                currency=plan.currency,
                installment_count=plan.installment_count,
                status=plan.status,
                created_at=plan.created_at,
            )
        )
        await self._s.flush()
        return plan

    async def get_plan(self, plan_id: UUID) -> ent.InstallmentPlan | None:
        row = await self._s.get(m.InstallmentPlanModel, plan_id)
        return map_.to_installment_plan(row) if row else None

    async def get_plan_for_transaction(self, transaction_id: UUID) -> ent.InstallmentPlan | None:
        stmt = (
            select(m.InstallmentPlanModel)
            .where(m.InstallmentPlanModel.transaction_id == transaction_id)
            .order_by(m.InstallmentPlanModel.created_at.desc())
            .limit(1)
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_installment_plan(row) if row else None

    async def update_plan(self, plan: ent.InstallmentPlan) -> ent.InstallmentPlan:
        await self._s.execute(
            update(m.InstallmentPlanModel)
            .where(m.InstallmentPlanModel.id == plan.id)
            .values(status=plan.status, cancelled_at=plan.cancelled_at)
        )
        return plan

    async def add_installment(self, installment: ent.Installment) -> ent.Installment:
        self._s.add(
            m.InstallmentModel(
                id=installment.id,
                plan_id=installment.plan_id,
                sequence_number=installment.sequence_number,
                amount=installment.amount,
                due_at=installment.due_at,
                status=installment.status,
                created_at=installment.created_at,
            )
        )
        await self._s.flush()
        return installment

    async def list_installments(self, plan_id: UUID) -> list[ent.Installment]:
        stmt = (
            select(m.InstallmentModel)
            .where(m.InstallmentModel.plan_id == plan_id)
            .order_by(m.InstallmentModel.sequence_number.asc())
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_installment(r) for r in rows]

    async def get_installment(self, installment_id: UUID) -> ent.Installment | None:
        row = await self._s.get(m.InstallmentModel, installment_id)
        return map_.to_installment(row) if row else None

    async def update_installment(self, installment: ent.Installment) -> ent.Installment:
        await self._s.execute(
            update(m.InstallmentModel)
            .where(m.InstallmentModel.id == installment.id)
            .values(
                status=installment.status,
                paid_at=installment.paid_at,
                paid_by=installment.paid_by,
            )
        )
        return installment


class SqlAuctionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, auction: ent.Auction) -> ent.Auction:
        self._s.add(
            m.AuctionModel(
                id=auction.id,
                listing_id=auction.listing_id,
                seller_id=auction.seller_id,
                starting_price=auction.starting_price,
                currency=auction.currency,
                ends_at=auction.ends_at,
                status=auction.status,
                created_at=auction.created_at,
                reserve_price=auction.reserve_price,
            )
        )
        await self._s.flush()
        return auction

    async def get(self, auction_id: UUID) -> ent.Auction | None:
        row = await self._s.get(m.AuctionModel, auction_id)
        return map_.to_auction(row) if row else None

    async def get_for_listing(self, listing_id: UUID) -> ent.Auction | None:
        stmt = (
            select(m.AuctionModel)
            .where(m.AuctionModel.listing_id == listing_id)
            .order_by(m.AuctionModel.created_at.desc())
            .limit(1)
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_auction(row) if row else None

    async def update(self, auction: ent.Auction) -> ent.Auction:
        await self._s.execute(
            update(m.AuctionModel)
            .where(m.AuctionModel.id == auction.id)
            .values(
                status=auction.status,
                winning_bid_id=auction.winning_bid_id,
                ended_at=auction.ended_at,
            )
        )
        return auction

    async def list_ending_before(self, at: datetime, *, limit: int = 100) -> list[ent.Auction]:
        stmt = (
            select(m.AuctionModel)
            .where(
                m.AuctionModel.status == e.AuctionStatus.ACTIVE,
                m.AuctionModel.ends_at <= at,
            )
            .limit(limit)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_auction(r) for r in rows]

    async def add_bid(self, bid: ent.Bid) -> ent.Bid:
        self._s.add(
            m.BidModel(
                id=bid.id,
                auction_id=bid.auction_id,
                bidder_id=bid.bidder_id,
                amount=bid.amount,
                created_at=bid.created_at,
            )
        )
        await self._s.flush()
        return bid

    async def list_bids(self, auction_id: UUID) -> list[ent.Bid]:
        stmt = (
            select(m.BidModel)
            .where(m.BidModel.auction_id == auction_id)
            .order_by(m.BidModel.amount.desc())
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_bid(r) for r in rows]

    async def get_highest_bid(self, auction_id: UUID) -> ent.Bid | None:
        stmt = (
            select(m.BidModel)
            .where(m.BidModel.auction_id == auction_id)
            .order_by(m.BidModel.amount.desc())
            .limit(1)
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_bid(row) if row else None
