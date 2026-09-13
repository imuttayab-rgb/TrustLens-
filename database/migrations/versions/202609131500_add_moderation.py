"""Add reports and blocks (feature MOD-01).

A report is a buyer or seller flagging a listing, seller, or message for
staff attention - separate from appeals/review_cases, which are about
disputing or triaging a *score decision*, not moderating content or contact.

A block is directional (blocker_id blocked blocked_id); messaging
enforcement checks both directions rather than relying on symmetry here.

Revision ID: 202609131500
Revises: 202609101400
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609131500"
down_revision: str | None = "202609101400"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUMS: dict[str, tuple[str, ...]] = {
    "report_target_type": ("LISTING", "SELLER", "MESSAGE", "OTHER"),
    "report_category": (
        "SCAM_OR_FRAUD",
        "PROHIBITED_ITEM",
        "HARASSMENT",
        "MISLEADING_LISTING",
        "OTHER",
    ),
    "report_status": ("OPEN", "UNDER_REVIEW", "RESOLVED", "DISMISSED"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def upgrade() -> None:
    for name, values in ENUMS.items():
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
        "reports",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "reporter_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("target_type", _enum("report_target_type"), nullable=False),
        sa.Column("target_id", uuid, nullable=False),
        sa.Column("category", _enum("report_category"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", _enum("report_status"), nullable=False, server_default="OPEN"),
        sa.Column("created_at", ts, nullable=False, server_default=now),
        sa.Column("updated_at", ts),
        sa.Column("resolved_at", ts),
        sa.Column("resolved_by", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("resolution_note", sa.Text()),
    )
    op.create_index("ix_reports_queue", "reports", ["status", "created_at"])
    op.create_index("ix_reports_reporter", "reports", ["reporter_id", "created_at"])
    op.create_index("ix_reports_target", "reports", ["target_type", "target_id"])

    op.create_table(
        "blocks",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "blocker_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "blocked_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", ts, nullable=False, server_default=now),
    )
    op.create_index(
        "uq_blocks_blocker_blocked", "blocks", ["blocker_id", "blocked_id"], unique=True
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS blocks CASCADE")
    op.execute("DROP TABLE IF EXISTS reports CASCADE")
    for name in ENUMS:
        op.execute(f"DROP TYPE IF EXISTS {name}")
