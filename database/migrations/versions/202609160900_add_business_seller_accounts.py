"""Add business seller accounts (feature BUS-01).

Revision ID: 202609160900
Revises: 202609152000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609160900"
down_revision: str | None = "202609152000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCOUNT_TYPE_VALUES = ("INDIVIDUAL", "BUSINESS")


def upgrade() -> None:
    rendered = ", ".join(f"'{v}'" for v in ACCOUNT_TYPE_VALUES)
    op.execute(
        f"DO $$ BEGIN "
        f"CREATE TYPE seller_account_type AS ENUM ({rendered}); "
        f"EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )

    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE file_purpose ADD VALUE IF NOT EXISTS 'BUSINESS_REGISTRATION'")
        op.execute("ALTER TYPE review_case_type ADD VALUE IF NOT EXISTS 'BUSINESS_VERIFICATION'")

    op.add_column(
        "seller_profiles",
        sa.Column(
            "account_type",
            postgresql.ENUM(*ACCOUNT_TYPE_VALUES, name="seller_account_type", create_type=False),
            nullable=False,
            server_default="INDIVIDUAL",
        ),
    )
    op.add_column("seller_profiles", sa.Column("business_legal_name", sa.String(200)))
    op.add_column("seller_profiles", sa.Column("business_registration_number", sa.String(80)))
    op.add_column(
        "seller_profiles",
        sa.Column(
            "business_document_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("files.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "seller_profiles",
        sa.Column(
            "business_verification_status",
            postgresql.ENUM(
                "NOT_STARTED",
                "PENDING",
                "PROCESSING",
                "VERIFIED",
                "REJECTED",
                "EXPIRED",
                "FAILED",
                name="verification_status",
                create_type=False,
            ),
            nullable=False,
            server_default="NOT_STARTED",
        ),
    )


def downgrade() -> None:
    op.drop_column("seller_profiles", "business_verification_status")
    op.drop_column("seller_profiles", "business_document_file_id")
    op.drop_column("seller_profiles", "business_registration_number")
    op.drop_column("seller_profiles", "business_legal_name")
    op.drop_column("seller_profiles", "account_type")
    op.execute("DROP TYPE IF EXISTS seller_account_type")
    # file_purpose/review_case_type values are not removed - Postgres cannot
    # drop enum values, and any BUSINESS_REGISTRATION/BUSINESS_VERIFICATION
    # rows would be orphaned by trying.
