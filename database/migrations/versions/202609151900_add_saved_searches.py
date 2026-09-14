"""Add saved_searches table (feature FAV-01).

Revision ID: 202609151900
Revises: 202609151800
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609151900"
down_revision: str | None = "202609151800"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_searches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(80)),
        sa.Column("q", sa.String(200)),
        sa.Column("city", sa.String(80)),
        sa.Column("area", sa.String(120)),
        sa.Column("min_price", sa.Numeric(14, 2)),
        sa.Column("max_price", sa.Numeric(14, 2)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_saved_searches_user_created", "saved_searches", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_saved_searches_user_created", table_name="saved_searches")
    op.drop_table("saved_searches")
