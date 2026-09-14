"""Add negotiable/attributes/video to listings, thumbnails to listing images
(feature LST-01).

Revision ID: 202609151400
Revises: 202609150900
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202609151400"
down_revision: str | None = "202609150900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE file_purpose ADD VALUE IF NOT EXISTS 'LISTING_VIDEO'")

    op.add_column(
        "listings",
        sa.Column("negotiable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "listings",
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "listings",
        sa.Column(
            "video_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("files.id", ondelete="SET NULL"),
        ),
    )
    op.add_column("listing_images", sa.Column("thumbnail_object_key", sa.Text()))


def downgrade() -> None:
    op.drop_column("listing_images", "thumbnail_object_key")
    op.drop_column("listings", "video_file_id")
    op.drop_column("listings", "attributes")
    op.drop_column("listings", "negotiable")
    # file_purpose values are not removed - Postgres cannot drop enum
    # values, and any LISTING_VIDEO rows would be orphaned by trying.
