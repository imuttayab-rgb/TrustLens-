"""Private indexed photo fingerprints. Additive; retained on application rollback."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "202610041530"
down_revision = "202610020800"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "photo_guard_state",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("ready", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("INSERT INTO photo_guard_state (id, ready) VALUES (1, false)")
    op.create_table(
        "photo_fingerprints",
        sa.Column(
            "image_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("listing_images.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "owner_user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("digests", pg.ARRAY(sa.Text()), nullable=False),
        sa.Column("bands", pg.ARRAY(sa.Text()), nullable=False),
        sa.Column("fingerprint", pg.JSONB(), nullable=False),
        sa.Column("legacy", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_photo_digests", "photo_fingerprints", ["digests"], postgresql_using="gin")
    op.create_index("ix_photo_bands", "photo_fingerprints", ["bands"], postgresql_using="gin")


def downgrade():
    op.drop_table("photo_fingerprints")
    op.drop_table("photo_guard_state")
