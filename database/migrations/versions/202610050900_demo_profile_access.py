"""Revocable access allowlist; existing verification evidence is untouched."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "202610050900"
down_revision = "202610050030"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "demo_profile_access",
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("seller_id", pg.UUID(as_uuid=True), sa.ForeignKey("seller_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch", sa.String(80), nullable=False),
        sa.Column("enrolled_email", sa.String(254), nullable=False),
        sa.Column("fixture_ref", sa.String(100), nullable=False),
        sa.Column("account_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    raise RuntimeError("Use the access disable command; do not drop the access audit records.")
