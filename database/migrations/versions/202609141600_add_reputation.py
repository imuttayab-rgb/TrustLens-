"""Add follows and reviews (feature REP-01).

Revision ID: 202609141600
Revises: 202609141200
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609141600"
down_revision: str | None = "202609141200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    ts = sa.DateTime(timezone=True)
    now = sa.text("now()")

    op.create_table(
        "follows",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "follower_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("seller_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", ts, nullable=False, server_default=now),
    )
    op.create_index("ix_follows_seller", "follows", ["seller_id"])
    op.create_index(
        "uq_follows_follower_seller", "follows", ["follower_id", "seller_id"], unique=True
    )

    op.create_table(
        "reviews",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "transaction_id",
            uuid,
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "listing_id", uuid, sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "reviewer_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "reviewee_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", ts, nullable=False, server_default=now),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="review_rating_in_range"),
    )
    op.create_index("ix_reviews_reviewee", "reviews", ["reviewee_id", "created_at"])
    op.create_index(
        "uq_reviews_transaction_reviewer",
        "reviews",
        ["transaction_id", "reviewer_id"],
        unique=True,
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reviews CASCADE")
    op.execute("DROP TABLE IF EXISTS follows CASCADE")
