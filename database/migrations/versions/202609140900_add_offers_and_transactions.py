"""Add offers, counter-offers and transactions (feature OFF-01).

Also extends listing_status with RESERVED and SOLD - an accepted offer
reserves the listing, a completed transaction sells it. Adding enum values
must run outside the migration's ambient transaction (Postgres restriction
on ALTER TYPE ... ADD VALUE), hence the autocommit_block() below.

Revision ID: 202609140900
Revises: 202609131500
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609140900"
down_revision: str | None = "202609131500"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_ENUMS: dict[str, tuple[str, ...]] = {
    "offer_status": ("PENDING", "ACCEPTED", "REJECTED", "COUNTERED", "WITHDRAWN", "EXPIRED"),
    "transaction_status": (
        "INITIATED",
        "AGREED",
        "MEETUP_PLANNED",
        "HANDED_OVER",
        "COMPLETED",
        "CANCELLED",
        "DISPUTED",
    ),
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

    # listing_status already exists (initial schema) - add to it rather than
    # recreate it. Each ADD VALUE needs its own transaction.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE listing_status ADD VALUE IF NOT EXISTS 'RESERVED' AFTER 'EXPIRED'")
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE listing_status ADD VALUE IF NOT EXISTS 'SOLD' AFTER 'RESERVED'")

    uuid = postgresql.UUID(as_uuid=True)
    ts = sa.DateTime(timezone=True)
    now = sa.text("now()")

    op.create_table(
        "offers",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "conversation_id",
            uuid,
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "listing_id", uuid, sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("buyer_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "offered_by", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PKR"),
        sa.Column("status", _enum("offer_status"), nullable=False, server_default="PENDING"),
        sa.Column("created_at", ts, nullable=False, server_default=now),
        sa.Column("expires_at", ts, nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("parent_offer_id", uuid, sa.ForeignKey("offers.id", ondelete="SET NULL")),
        sa.Column("responded_at", ts),
    )
    op.create_index("ix_offers_conversation", "offers", ["conversation_id", "created_at"])
    op.execute(
        "CREATE UNIQUE INDEX uq_offers_listing_open ON offers (listing_id) WHERE status = 'PENDING'"
    )

    op.create_table(
        "transactions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "listing_id", uuid, sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("buyer_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "offer_id", uuid, sa.ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PKR"),
        sa.Column(
            "status", _enum("transaction_status"), nullable=False, server_default="INITIATED"
        ),
        sa.Column("created_at", ts, nullable=False, server_default=now),
        sa.Column("updated_at", ts),
        sa.Column("completed_at", ts),
        sa.Column("cancelled_at", ts),
        sa.Column("cancel_reason", sa.Text()),
    )
    op.create_index("ix_transactions_buyer", "transactions", ["buyer_id", "created_at"])
    op.create_index("ix_transactions_seller", "transactions", ["seller_id", "created_at"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS transactions CASCADE")
    op.execute("DROP TABLE IF EXISTS offers CASCADE")
    for name in NEW_ENUMS:
        op.execute(f"DROP TYPE IF EXISTS {name}")
    # listing_status values are not removed - Postgres cannot drop enum
    # values, and any RESERVED/SOLD rows would be orphaned by trying.
