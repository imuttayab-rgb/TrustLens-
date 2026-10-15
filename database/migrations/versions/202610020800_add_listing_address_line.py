"""Add the seller's private full address to listings (Post-an-Ad v2).

The Post-an-Ad location step asks for a full address so the map pin can be
placed automatically. That address is PRIVATE: it is shown only to the
seller who owns the listing (to edit it) and is never part of any public
projection. Buyers keep seeing the existing city/area plus a coordinate
rounded to about 1.1 km.

Purely additive and nullable: existing rows keep NULL, and older API/worker
images simply ignore the column, so an image rollback does not need a schema
downgrade.

Revision ID: 202610020800
Revises: 202610011830
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202610020800"
down_revision: str | None = "202610011830"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("address_line", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("listings", "address_line")
