"""Exception handling: domain errors -> RFC 9457 problem+json.

One mapping table, no scattered `HTTPException`s in routers. Two rules are
absolute:

* Internal exception text is NEVER returned to a client. The response carries
  a `requestId` the user can quote; the log carries the stack trace.
* Every error body has a stable machine-readable `code`. Clients switch on the
  code, never on the human-readable title.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from trustlens.core.domain.errors import (
    AccountLocked,
    ApiKeyRevoked,
    AuthenticationError,
    ConflictError,
    DomainError,
    EntityNotFound,
    ExternalServiceError,
    InvalidStateError,
    PermissionDenied,
    RateLimitExceeded,
    ValidationError,
    VersionConflict,
)
from trustlens.shared.logging import get_logger, request_id_var

log = get_logger(__name__)

PROBLEM_BASE = "https://api.trustlens.app/errors"
PROBLEM_CONTENT_TYPE = "application/problem+json"

#: Domain error class -> (status, problem type slug). Order matters: the first
#: matching entry by isinstance wins, so subclasses precede their bases.
STATUS_MAP: tuple[tuple[type[DomainError], int, str], ...] = (
    (VersionConflict, 409, "version-conflict"),
    (ConflictError, 409, "conflict"),
    (ApiKeyRevoked, 410, "api-key-revoked"),
    (AccountLocked, 429, "account-locked"),
    (RateLimitExceeded, 429, "rate-limited"),
    (PermissionDenied, 403, "permission-denied"),
    (AuthenticationError, 401, "unauthenticated"),
    (EntityNotFound, 404, "not-found"),
    (ValidationError, 422, "validation-failed"),
    (InvalidStateError, 422, "invalid-state"),
    (ExternalServiceError, 502, "upstream-failed"),
    (DomainError, 400, "bad-request"),
)


def status_for(error: DomainError) -> tuple[int, str]:
    for error_type, status, slug in STATUS_MAP:
        if isinstance(error, error_type):
            return status, slug
    return 400, "bad-request"


def problem(
    *,
    status: int,
    slug: str,
    title: str,
    detail: str,
    code: str,
    instance: str,
    errors: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{PROBLEM_BASE}/{slug}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
        "code": code,
        "requestId": request_id_var.get(),
    }
    if errors:
        body["errors"] = errors
    if extra:
        body.update(extra)

    return JSONResponse(
        status_code=status,
        content=body,
        media_type=PROBLEM_CONTENT_TYPE,
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError) -> JSONResponse:
        status, slug = status_for(exc)

        headers: dict[str, str] = {}
        if isinstance(exc, RateLimitExceeded):
            headers["Retry-After"] = str(exc.retry_after)

        errors = None
        if isinstance(exc, ValidationError) and exc.field:
            errors = [{"field": exc.field, "code": exc.code, "message": exc.message}]

        # 4xx are expected outcomes, not incidents - log at info so genuine
        # problems stay visible in the noise.
        log.info(
            "domain_error",
            code=exc.code,
            status=status,
            path=request.url.path,
            detail=exc.message,
        )
        return problem(
            status=status,
            slug=slug,
            title=exc.title,
            detail=exc.message,
            code=exc.code,
            instance=request.url.path,
            errors=errors,
            extra={"details": exc.details} if exc.details else None,
            headers=headers or None,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                # Dotted path so React Hook Form can map straight onto inputs.
                # loc[0] is "body"/"query"/"path" and is dropped.
                "field": ".".join(str(part) for part in error["loc"][1:]) or "body",
                "code": error["type"].upper(),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return problem(
            status=422,
            slug="validation-failed",
            title="Validation failed",
            detail="One or more fields are invalid.",
            code="VALIDATION_FAILED",
            instance=request.url.path,
            errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(
            status=exc.status_code,
            slug=_slug_for_status(exc.status_code),
            title=str(exc.detail),
            detail=str(exc.detail),
            code=f"HTTP_{exc.status_code}",
            instance=request.url.path,
            headers=dict(exc.headers or {}),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # The ONLY place a stack trace is recorded, and it never reaches the
        # client. Correlate with the requestId echoed in the response.
        log.exception(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error_type=type(exc).__name__,
        )
        return problem(
            status=500,
            slug="internal",
            title="Internal server error",
            detail=(
                "Something went wrong on our side. "
                "Quote the request id below if you contact support."
            ),
            code="INTERNAL_ERROR",
            instance=request.url.path,
        )


def _slug_for_status(status: int) -> str:
    return {
        400: "bad-request",
        401: "unauthenticated",
        403: "permission-denied",
        404: "not-found",
        405: "method-not-allowed",
        409: "conflict",
        413: "payload-too-large",
        415: "unsupported-media-type",
        422: "validation-failed",
        429: "rate-limited",
        503: "unavailable",
    }.get(status, "error")


__all__ = ["PROBLEM_CONTENT_TYPE", "problem", "register_exception_handlers", "status_for"]
