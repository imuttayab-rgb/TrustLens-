"""Reports and blocks request/response models (feature MOD-01)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from trustlens.core.application.use_cases.moderation import (
    MAX_REPORT_DESCRIPTION_CHARS,
    MIN_REPORT_DESCRIPTION_CHARS,
)
from trustlens_api.api.v1.schemas.common import Schema


class CreateReportRequest(Schema):
    target_type: str
    target_id: UUID
    category: str
    description: str = Field(
        min_length=MIN_REPORT_DESCRIPTION_CHARS, max_length=MAX_REPORT_DESCRIPTION_CHARS
    )


class ReportResponse(Schema):
    id: UUID
    target_type: str
    target_id: UUID
    category: str
    description: str
    status: str
    created_at: datetime
    resolved_at: datetime | None = None
    resolution_note: str | None = None


class BlockUserRequest(Schema):
    blocked_user_id: UUID


class ResolveReportRequest(Schema):
    status: str
    resolution_note: str | None = Field(default=None, max_length=2_000)


__all__ = [
    "BlockUserRequest",
    "CreateReportRequest",
    "ReportResponse",
    "ResolveReportRequest",
]
