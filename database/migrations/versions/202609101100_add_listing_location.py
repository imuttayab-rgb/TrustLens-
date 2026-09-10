"""Add structured location (area, lat/lng) to listings.

`city` was already free text; this adds `area` (the OLX-style city->area
picker's second step - see PAKISTAN_LOCATIONS in packages/constants) plus
optional coordinates for the Google Maps location picker. All three are
nullable and additive: an existing listing with only `city` set keeps
working exactly as it did.

Revision ID: 202609101100
Revises: 202609100930
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202609101100"
down_revision: str | None = "202609100930"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("area", sa.String(120)))
    op.add_column("listings", sa.Column("latitude", sa.Numeric(9, 6)))
    op.add_column("listings", sa.Column("longitude", sa.Numeric(9, 6)))
    op.create_index("ix_listings_city_area", "listings", ["city", "area"])


def downgrade() -> None:
    op.drop_index("ix_listings_city_area", table_name="listings")
    op.drop_column("listings", "longitude")
    op.drop_column("listings", "latitude")
    op.drop_column("listings", "area")
