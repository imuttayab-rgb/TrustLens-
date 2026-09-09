"""Response model for the public listing catalog (buyer-facing browse/search).

Deliberately thin, same reasoning as the public score projection: no
description, no seller contact details - only what a buyer needs to decide
whether to open the listing.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from trustlens_api.api.v1.schemas.common import Schema


class PublicListingResponse(Schema):
    id: UUID
    title: str
    price: float | None = None
    currency: str | None = None
    category: str | None = None
    city: str | None = None
    created_at: datetime
    seller_handle: str
    seller_display_name: str
    image_url: str | None = None


__all__ = ["PublicListingResponse"]
