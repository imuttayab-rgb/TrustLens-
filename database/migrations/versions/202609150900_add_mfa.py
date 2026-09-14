"""Add staff MFA: recovery codes table, MFA_LOGIN token purpose (feature BLK-04).

`users.mfa_enabled`/`users.mfa_secret_encrypted` already exist from the
initial schema - this migration only adds what was still missing: the
recovery-codes table, and a new token_purpose value for the short-lived
challenge issued between password and MFA code during login.

Revision ID: 202609150900
Revises: 202609141600
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609150900"
down_revision: str | None = "202609141600"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE token_purpose ADD VALUE IF NOT EXISTS 'MFA_LOGIN'")

    uuid = postgresql.UUID(as_uuid=True)
    ts = sa.DateTime(timezone=True)
    now = sa.text("now()")

    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("used_at", ts),
        sa.Column("created_at", ts, nullable=False, server_default=now),
    )
    op.create_index("ix_mfa_recovery_codes_user", "mfa_recovery_codes", ["user_id"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mfa_recovery_codes CASCADE")
    # token_purpose values are not removed - Postgres cannot drop enum
    # values, and any MFA_LOGIN rows would be orphaned by trying.
