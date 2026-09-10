"""Add buyer<->seller messaging (conversations + messages).

A conversation is between a buyer (any signed-in user) and a seller
(seller_profiles), optionally anchored to the listing that started it.
Polled, not websocket-backed - see ListMessages/SendMessage in
trustlens.core.application.use_cases.messaging for why.

Revision ID: 202609101400
Revises: 202609101100
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609101400"
down_revision: str | None = "202609101100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    ts = sa.DateTime(timezone=True)
    now = sa.text("now()")

    op.create_table(
        "conversations",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("listing_id", uuid, sa.ForeignKey("listings.id", ondelete="SET NULL")),
        sa.Column(
            "seller_id",
            uuid,
            sa.ForeignKey("seller_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("buyer_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", ts, nullable=False, server_default=now),
        sa.Column("last_message_at", ts, nullable=False, server_default=now),
    )
    op.create_index("ix_conversations_buyer", "conversations", ["buyer_id", "last_message_at"])
    op.create_index("ix_conversations_seller", "conversations", ["seller_id", "last_message_at"])
    # Best-effort de-dup for the common "message this seller about this
    # listing again" case. Two NULL listing_id rows for the same pair are
    # not blocked by this (composite-unique NULLs are never equal in
    # Postgres) - StartConversation's find-or-create handles that path
    # in the application layer instead.
    op.create_index(
        "uq_conversations_buyer_seller_listing",
        "conversations",
        ["buyer_id", "seller_id", "listing_id"],
        unique=True,
    )

    op.create_table(
        "messages",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "conversation_id",
            uuid,
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", ts, nullable=False, server_default=now),
        sa.Column("read_at", ts),
    )
    op.create_index(
        "ix_messages_conversation_created", "messages", ["conversation_id", "created_at"]
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS messages CASCADE")
    op.execute("DROP TABLE IF EXISTS conversations CASCADE")
