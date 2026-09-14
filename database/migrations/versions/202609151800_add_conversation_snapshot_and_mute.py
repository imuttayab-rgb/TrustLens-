"""Add listing snapshot and per-side mute to conversations (feature SOC-01).

Revision ID: 202609151800
Revises: 202609151400
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202609151800"
down_revision: str | None = "202609151400"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("listing_title_snapshot", sa.String(200)))
    op.add_column("conversations", sa.Column("listing_price_snapshot", sa.Numeric(14, 2)))
    op.add_column("conversations", sa.Column("listing_currency_snapshot", sa.String(3)))
    op.add_column(
        "conversations",
        sa.Column("muted_by_buyer", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "conversations",
        sa.Column("muted_by_seller", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("conversations", "muted_by_seller")
    op.drop_column("conversations", "muted_by_buyer")
    op.drop_column("conversations", "listing_currency_snapshot")
    op.drop_column("conversations", "listing_price_snapshot")
    op.drop_column("conversations", "listing_title_snapshot")
