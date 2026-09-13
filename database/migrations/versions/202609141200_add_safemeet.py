"""Add meeting venues and meetups (feature SAFE-01).

Revision ID: 202609141200
Revises: 202609140900
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609141200"
down_revision: str | None = "202609140900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MEETUP_STATUS_VALUES = ("PROPOSED", "ACCEPTED", "DECLINED", "CANCELLED")


def _enum() -> postgresql.ENUM:
    return postgresql.ENUM(*MEETUP_STATUS_VALUES, name="meetup_status", create_type=False)


def upgrade() -> None:
    rendered = ", ".join(f"'{v}'" for v in MEETUP_STATUS_VALUES)
    op.execute(
        f"DO $$ BEGIN "
        f"CREATE TYPE meetup_status AS ENUM ({rendered}); "
        f"EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )

    uuid = postgresql.UUID(as_uuid=True)
    ts = sa.DateTime(timezone=True)
    now = sa.text("now()")

    op.create_table(
        "meeting_venues",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("area", sa.String(100)),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", ts, nullable=False, server_default=now),
    )
    op.create_index("ix_meeting_venues_city", "meeting_venues", ["city", "is_active"])

    op.create_table(
        "meetups",
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
            "proposed_by", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "venue_id",
            uuid,
            sa.ForeignKey("meeting_venues.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("proposed_time", ts, nullable=False),
        sa.Column("status", _enum(), nullable=False, server_default="PROPOSED"),
        sa.Column("created_at", ts, nullable=False, server_default=now),
        sa.Column("message", sa.Text()),
        sa.Column("responded_at", ts),
    )
    op.create_index("ix_meetups_conversation", "meetups", ["conversation_id", "created_at"])
    op.execute(
        "CREATE UNIQUE INDEX uq_meetups_conversation_open ON meetups (conversation_id) "
        "WHERE status = 'PROPOSED'"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS meetups CASCADE")
    op.execute("DROP TABLE IF EXISTS meeting_venues CASCADE")
    op.execute("DROP TYPE IF EXISTS meetup_status")
