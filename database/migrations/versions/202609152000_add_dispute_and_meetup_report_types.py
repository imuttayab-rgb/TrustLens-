"""Add TRANSACTION and MEETUP report target types (feature OPS-01).

Revision ID: 202609152000
Revises: 202609151900
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "202609152000"
down_revision: str | None = "202609151900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE report_target_type ADD VALUE IF NOT EXISTS 'TRANSACTION'")
        op.execute("ALTER TYPE report_target_type ADD VALUE IF NOT EXISTS 'MEETUP'")


def downgrade() -> None:
    pass
    # report_target_type values are not removed - Postgres cannot drop enum
    # values, and any TRANSACTION/MEETUP rows would be orphaned by trying.
