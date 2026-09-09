"""Add favorites (buyer-saved listings).

Revision ID: 202609100930
Revises: 202607310900
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609100930"
down_revision: str | None = "202607310900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    ts = sa.DateTime(timezone=True)
    now = sa.text("now()")

    op.create_table(
        "favorites",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "listing_id", uuid, sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", ts, nullable=False, server_default=now),
    )
    op.create_index("ix_favorites_user_created", "favorites", ["user_id", "created_at"])
    op.create_index(
        "uq_favorites_user_listing", "favorites", ["user_id", "listing_id"], unique=True
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS favorites CASCADE")
