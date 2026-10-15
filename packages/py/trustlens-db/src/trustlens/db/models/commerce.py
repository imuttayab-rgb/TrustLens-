"""Commerce models. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from trustlens.core.domain import enums as e
from trustlens.db.base import (
    Base,
    uuid_fk,
    uuid_pk,
)
from .common import pg_enum


class OfferModel(Base):
    """An offer or counter-offer inside a conversation (OFF-01). A counter
    is a new row with parent_offer_id set - the original is closed out
    (COUNTERED), never edited."""

    __tablename__ = "offers"

    id: Mapped[UUID] = uuid_pk()
    conversation_id: Mapped[UUID] = uuid_fk("conversations.id")
    listing_id: Mapped[UUID] = uuid_fk("listings.id")
    buyer_id: Mapped[UUID] = uuid_fk("users.id")
    seller_id: Mapped[UUID] = uuid_fk("users.id")
    offered_by: Mapped[UUID] = uuid_fk("users.id")
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")
    status: Mapped[e.OfferStatus] = mapped_column(
        pg_enum(e.OfferStatus, "offer_status"), nullable=False, default=e.OfferStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    parent_offer_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("offers.id", ondelete="SET NULL")
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_offers_conversation", "conversation_id", "created_at"),
        # At most one open offer per listing at a time - a partial index
        # rather than a plain unique constraint, since closed offers must
        # pile up (the negotiation history) without blocking the next one.
        Index(
            "uq_offers_listing_open",
            "listing_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
    )


class TransactionModel(Base):
    """Created the moment an offer is accepted; reserves the listing."""

    __tablename__ = "transactions"

    id: Mapped[UUID] = uuid_pk()
    listing_id: Mapped[UUID] = uuid_fk("listings.id")
    buyer_id: Mapped[UUID] = uuid_fk("users.id")
    seller_id: Mapped[UUID] = uuid_fk("users.id")
    offer_id: Mapped[UUID] = uuid_fk("offers.id")
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")
    status: Mapped[e.TransactionStatus] = mapped_column(
        pg_enum(e.TransactionStatus, "transaction_status"),
        nullable=False,
        default=e.TransactionStatus.INITIATED,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_transactions_buyer", "buyer_id", "created_at"),
        Index("ix_transactions_seller", "seller_id", "created_at"),
    )


class InstallmentPlanModel(Base):
    """Buy-now-pay-later, sandboxed (PAY-01) - tracks a payment schedule
    against an existing transaction. No real money moves through it."""

    __tablename__ = "installment_plans"

    id: Mapped[UUID] = uuid_pk()
    transaction_id: Mapped[UUID] = uuid_fk("transactions.id")
    buyer_id: Mapped[UUID] = uuid_fk("users.id")
    seller_id: Mapped[UUID] = uuid_fk("users.id")
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")
    installment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[e.InstallmentPlanStatus] = mapped_column(
        pg_enum(e.InstallmentPlanStatus, "installment_plan_status"),
        nullable=False,
        default=e.InstallmentPlanStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # At most one open plan per transaction at a time.
        Index(
            "uq_installment_plans_transaction_open",
            "transaction_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )


class InstallmentModel(Base):
    __tablename__ = "installments"

    id: Mapped[UUID] = uuid_pk()
    plan_id: Mapped[UUID] = uuid_fk("installment_plans.id")
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[e.InstallmentStatus] = mapped_column(
        pg_enum(e.InstallmentStatus, "installment_status"),
        nullable=False,
        default=e.InstallmentStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index("ix_installments_plan_sequence", "plan_id", "sequence_number", unique=True),
    )


class AuctionModel(Base):
    """A listing sold competitively instead of at a fixed price (AUC-01)."""

    __tablename__ = "auctions"

    id: Mapped[UUID] = uuid_pk()
    listing_id: Mapped[UUID] = uuid_fk("listings.id")
    seller_id: Mapped[UUID] = uuid_fk("users.id")
    starting_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[e.AuctionStatus] = mapped_column(
        pg_enum(e.AuctionStatus, "auction_status"),
        nullable=False,
        default=e.AuctionStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    #: Never exposed to bidders - see the domain entity's docstring.
    reserve_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    #: Deliberately no FK to `bids.id`: that would make `auctions` and
    #: `bids` reference each other circularly for no real benefit - this is
    #: only ever set by `CloseAuction` to a bid row it just read or created,
    #: the same "untyped reference, named by convention" shape
    #: `ReviewCase.related_entity_id` already uses elsewhere.
    winning_bid_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_auctions_listing_open",
            "listing_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        # The worker sweep's "find everything overdue" query.
        Index("ix_auctions_active_ends_at", "ends_at", postgresql_where=text("status = 'ACTIVE'")),
    )


class BidModel(Base):
    __tablename__ = "bids"

    id: Mapped[UUID] = uuid_pk()
    auction_id: Mapped[UUID] = uuid_fk("auctions.id")
    bidder_id: Mapped[UUID] = uuid_fk("users.id")
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # The leaderboard query: highest bid first, for one auction.
        Index("ix_bids_auction_amount", "auction_id", "amount"),
    )
