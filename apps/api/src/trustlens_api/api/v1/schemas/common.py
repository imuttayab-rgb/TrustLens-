"""Shared response schemas.

JSON is camelCase on the wire, snake_case in Python. The alias generator does
the translation once, here, so neither codebase compromises its own idiom.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class Schema(BaseModel):
    """Base for every request/response model."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        # Reject unknown fields: silently ignoring them is how mass-assignment
        # bugs happen, and a typo'd field name should fail loudly.
        extra="forbid",
        str_strip_whitespace=True,
    )


class PageMeta(Schema):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def build(cls, *, page: int, per_page: int, total: int) -> PageMeta:
        total_pages = max(1, -(-total // per_page))  # ceil division
        return cls(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


class CursorMeta(Schema):
    next: str | None = None
    prev: str | None = None
    has_next: bool = False


class ResponseMeta(Schema):
    request_id: str | None = None
    timestamp: datetime
    pagination: PageMeta | None = None
    cursor: CursorMeta | None = None
    cached: bool | None = None
    warnings: list[str] | None = None


class Envelope[T](Schema):
    """The success envelope: `{data, meta}`.

    Errors do NOT use this - they use RFC 9457 problem+json, which is an IETF
    standard with existing client support (docs/06 section 3).
    """

    data: T
    meta: ResponseMeta


class ProblemDetail(Schema):
    """Documented purely so it appears in the OpenAPI schema.

    Partner integrators need the error shape in the generated client just as
    much as the success shape.
    """

    model_config = ConfigDict(alias_generator=None, populate_by_name=True, extra="allow")

    type: str
    title: str
    status: int
    detail: str
    code: str
    instance: str | None = None
    requestId: str | None = None  # noqa: N815 - wire format is already camelCase
    errors: list[dict[str, Any]] | None = None


class FieldError(Schema):
    field: str
    code: str
    message: str


class MessageResponse(Schema):
    message: str


class JobAccepted(Schema):
    """202 response for anything that queues background work."""

    job_id: str
    status: str = "QUEUED"
    poll_url: str = Field(description="Poll this until status is terminal.")


def envelope(
    data: Any,
    *,
    request_id: str | None = None,
    pagination: PageMeta | None = None,
    cached: bool | None = None,
) -> dict[str, Any]:
    """Build a response body without needing a concrete generic type."""
    from datetime import UTC

    meta: dict[str, Any] = {
        "requestId": request_id,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if pagination is not None:
        meta["pagination"] = pagination.model_dump(by_alias=True)
    if cached is not None:
        meta["cached"] = cached
    return {"data": data, "meta": meta}


__all__ = [
    "CursorMeta",
    "Envelope",
    "FieldError",
    "JobAccepted",
    "MessageResponse",
    "PageMeta",
    "ProblemDetail",
    "ResponseMeta",
    "Schema",
    "envelope",
]
