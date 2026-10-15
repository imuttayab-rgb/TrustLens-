"""Allow a private holding-card evidence image (HOLD_ID).

Revision ID: 202610011830
Revises: 202609161200
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "202610011830"
down_revision: str | None = "202609161200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL ENUM additions cannot be safely removed while historic rows
    # may still refer to that value. This is additive and preserves old rows.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE file_purpose ADD VALUE IF NOT EXISTS 'HOLD_ID'")


def downgrade() -> None:
    # Existing HOLD_ID stored_files must remain readable after a code rollback.
    pass
