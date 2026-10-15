"""Unified profile evidence and owner-only pause state. Additive migration."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "202610050030"
down_revision = "202610041530"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column(n, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
        for n in ("created_at", "updated_at")
    ]


def upgrade():
    op.create_table(
        "profile_photos",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "identity_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("identity_verifications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bucket", sa.String(80), nullable=False),
        sa.Column("object_key", sa.String(400), nullable=False, unique=True),
        sa.Column("sha256", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column("engine", sa.String(40)),
        sa.Column("similarity", sa.Numeric(5, 4)),
        sa.Column("threshold", sa.Numeric(5, 4)),
        sa.Column("reason", sa.String(100)),
        sa.Column("consent_version", sa.String(20), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *timestamps(),
    )
    op.create_index("ix_profile_photos_user_created", "profile_photos", ["user_id", "created_at"])
    op.create_table(
        "account_profiles",
        sa.Column("username_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("public_name", sa.String(150)),
        sa.Column("name_status", sa.String(20), nullable=False, server_default="NOT_STARTED"),
        sa.Column(
            "name_identity_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("identity_verifications.id", ondelete="SET NULL"),
        ),
        sa.Column("name_encrypted", sa.LargeBinary()),
        sa.Column("name_verified_at", sa.DateTime(timezone=True)),
        sa.Column(
            "approved_photo_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("profile_photos.id", ondelete="SET NULL"),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *timestamps(),
    )
    op.execute(
        "INSERT INTO account_profiles (user_id) SELECT id FROM users WHERE deleted_at IS NULL"
    )
    op.create_table(
        "profile_name_requests",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "identity_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("identity_verifications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requested_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="REVIEW"),
        sa.Column("note", sa.String(1000), nullable=False, server_default=""),
        sa.Column(
            "decided_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("decision_note", sa.String(1000)),
        *timestamps(),
    )
    op.create_index(
        "ix_profile_name_requests_status_created", "profile_name_requests", ["status", "created_at"]
    )
    op.create_table(
        "profile_handle_aliases",
        sa.Column("handle", pg.CITEXT(), primary_key=True),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.execute(
        "INSERT INTO profile_handle_aliases (handle,user_id) SELECT handle,user_id FROM seller_profiles WHERE deleted_at IS NULL"
    )
    op.create_table(
        "listing_pauses",
        sa.Column(
            "listing_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("listings.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade():
    for table in (
        "listing_pauses",
        "profile_handle_aliases",
        "profile_name_requests",
        "account_profiles",
        "profile_photos",
    ):
        op.drop_table(table)
