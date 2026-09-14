"""Add installment plans and auctions (features PAY-01, AUC-01).

Revision ID: 202609161200
Revises: 202609160900
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609161200"
down_revision: str | None = "202609160900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_ENUMS: dict[str, tuple[str, ...]] = {
    "installment_plan_status": ("ACTIVE", "COMPLETED", "CANCELLED"),
    "installment_status": ("PENDING", "PAID"),
    "auction_status": ("ACTIVE", "ENDED", "CANCELLED"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*NEW_ENUMS[name], name=name, create_type=False)


def upgrade() -> None:
    for name, values in NEW_ENUMS.items():
        rendered = ", ".join(f"'{v}'" for v in values)
        op.execute(
            f"DO $$ BEGIN "
            f"CREATE TYPE {name} AS ENUM ({rendered}); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        )

    uuid = postgresql.UUID(as_uuid=True)
    ts = sa.DateTime(timezone=True)
    now = sa.text("now()")

    op.create_table(
        "installment_plans",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "transaction_id",
            uuid,
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("buyer_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PKR"),
        sa.Column("installment_count", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            _enum("installment_plan_status"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("created_at", ts, nullable=False, server_default=now),
        sa.Column("cancelled_at", ts),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_installment_plans_transaction_open ON installment_plans "
        "(transaction_id) WHERE status = 'ACTIVE'"
    )

    op.create_table(
        "installments",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "plan_id",
            uuid,
            sa.ForeignKey("installment_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("due_at", ts, nullable=False),
        sa.Column("status", _enum("installment_status"), nullable=False, server_default="PENDING"),
        sa.Column("created_at", ts, nullable=False, server_default=now),
        sa.Column("paid_at", ts),
        sa.Column("paid_by", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    op.create_index(
        "ix_installments_plan_sequence", "installments", ["plan_id", "sequence_number"], unique=True
    )

    op.create_table(
        "auctions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "listing_id", uuid, sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("seller_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("starting_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PKR"),
        sa.Column("ends_at", ts, nullable=False),
        sa.Column("status", _enum("auction_status"), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", ts, nullable=False, server_default=now),
        sa.Column("reserve_price", sa.Numeric(12, 2)),
        # No FK to bids.id (bids references auctions.id) - see the model's
        # docstring on why this stays an untyped reference.
        sa.Column("winning_bid_id", uuid),
        sa.Column("ended_at", ts),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_auctions_listing_open ON auctions (listing_id) "
        "WHERE status = 'ACTIVE'"
    )
    op.execute(
        "CREATE INDEX ix_auctions_active_ends_at ON auctions (ends_at) WHERE status = 'ACTIVE'"
    )

    op.create_table(
        "bids",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "auction_id", uuid, sa.ForeignKey("auctions.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("bidder_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", ts, nullable=False, server_default=now),
    )
    op.create_index("ix_bids_auction_amount", "bids", ["auction_id", "amount"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bids CASCADE")
    op.execute("DROP TABLE IF EXISTS auctions CASCADE")
    op.execute("DROP TABLE IF EXISTS installments CASCADE")
    op.execute("DROP TABLE IF EXISTS installment_plans CASCADE")
    for name in NEW_ENUMS:
        op.execute(f"DROP TYPE IF EXISTS {name}")
