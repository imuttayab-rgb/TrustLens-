"""In-app notification (NOT-01) response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from trustlens_api.api.v1.schemas.common import Schema


class NotificationResponse(Schema):
    id: UUID
    type: str
    title: str
    body: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    read_at: datetime | None = None


__all__ = ["NotificationResponse"]
