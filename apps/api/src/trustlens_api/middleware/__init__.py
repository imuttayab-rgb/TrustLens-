"""HTTP middleware.

Order is a correctness concern, not a style choice - see `install_middleware`.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send

from trustlens.shared.config.settings import Settings
from trustlens.shared.logging import (
    actor_id_var,
    actor_type_var,
    get_logger,
    request_id_var,
    trace_id_var,
)

log = get_logger("trustlens.api.access")

Next = Callable[[Request], Awaitable[Response]]


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns the request id.

    Installed OUTERMOST so every log line downstream - including ones emitted
    by other middleware - carries it.
    """

    async def dispatch(self, request: Request, call_next: Next) -> Response:
        request_id = f"req_{uuid.uuid4().hex[:20]}"
        trace_id = request_id

        request_id_var.set(request_id)
        trace_id_var.set(trace_id)
        actor_id_var.set(None)
        actor_type_var.set(None)
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


def apply_security_headers(response: Response, *, is_production: bool) -> None:
    """Shared normal/error response protection, including outer 500 responses."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(self), microphone=(), geolocation=(), payment=()"
    )
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    # The API returns JSON, never markup, so it can afford the strictest
    # possible CSP.
    response.headers.setdefault(
        "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
    )
    if is_production:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Defence-in-depth headers.

    `camera=(self)` is required - the selfie capture step needs it. Everything
    else is denied.
    """

    def __init__(self, app: ASGIApp, *, is_production: bool) -> None:
        super().__init__(app)
        self._is_production = is_production

    async def dispatch(self, request: Request, call_next: Next) -> Response:
        response = await call_next(request)
        apply_security_headers(response, is_production=self._is_production)
        return response


class BodySizeLimitMiddleware:
    """Bound actual received bytes before routing, including chunked requests.

    Content-Length is only an early rejection hint. Bounded buffering prevents
    downstream multipart/JSON parsers from allocating an unlimited request.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length", b"")
        payload = bytearray()
        oversized = length.isdigit() and int(length) > self.max_bytes
        while not oversized:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            data = message.get("body", b"")
            if len(payload) + len(data) > self.max_bytes:
                oversized = True
                break
            payload.extend(data)
            if not message.get("more_body", False):
                break
        if oversized:
            response = JSONResponse(
                status_code=413,
                media_type="application/problem+json",
                content={
                    "type": "https://api.trustlens.app/errors/payload-too-large",
                    "title": "Payload too large",
                    "status": 413,
                    "detail": f"Request body exceeds {self.max_bytes} bytes.",
                    "code": "PAYLOAD_TOO_LARGE",
                    "requestId": request_id_var.get(),
                },
            )
            await response(scope, receive, send)
            return
        delivered = False

        async def replay() -> dict:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(payload), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class RequestBudgetMiddleware(BaseHTTPMiddleware):
    """Apply an IP budget to every API route, not just selected handlers."""

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next: Next) -> Response:
        container = getattr(request.app.state, "container", None)
        if (
            container is not None
            and self.settings.rate_limit.enabled
            and request.method != "OPTIONS"
            and request.url.path.startswith(("/api/", "/public/"))
        ):
            from trustlens_api.api.deps import _client_ip

            ip = _client_ip(request, self.settings.security.trusted_proxy_count) or "unknown"
            authenticated = request.headers.get("authorization", "").lower().startswith("bearer ")
            limit = (
                self.settings.rate_limit.ip_per_minute
                if authenticated
                else self.settings.rate_limit.anon_per_minute
            )
            try:
                allowed, _, retry = await container.rate_limiter.hit(
                    f"request:{'bearer' if authenticated else 'anonymous'}:{ip}",
                    limit=limit,
                    window_seconds=60,
                )
            except Exception:
                return JSONResponse(
                    status_code=503,
                    headers={"Retry-After": "30"},
                    content={
                        "code": "RATE_LIMIT_UNAVAILABLE",
                        "detail": "Service temporarily unavailable. Try again shortly.",
                        "requestId": request_id_var.get(),
                    },
                )
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry)},
                    content={
                        "code": "RATE_LIMITED",
                        "detail": "Too many requests. Try again shortly.",
                        "requestId": request_id_var.get(),
                    },
                )
        return await call_next(request)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Structured access log with duration.

    Wraps the routing layer so it times the full handler including
    serialisation, which is what actually matters for the latency targets.
    """

    async def dispatch(self, request: Request, call_next: Next) -> Response:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            log.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Response-Time-Ms"] = str(duration_ms)

        # Health checks are polled every few seconds by the platform; logging
        # them buries everything else.
        if not request.url.path.startswith("/health"):
            log.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
                query_count=len(request.query_params),
            )
        return response


def install_middleware(app: FastAPI, settings: Settings) -> None:
    """Install middleware in the correct order.

    Starlette applies middleware in REVERSE registration order, so the last
    one added is the outermost. Registering bottom-up here gives, from
    outside in:

        RequestContext -> SecurityHeaders -> CORS -> TrustedHost
        -> BodySizeLimit -> AccessLog -> router
    """
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestBudgetMiddleware, settings=settings)
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=settings.storage.storage_max_upload_bytes + 1_048_576,
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=[*settings.security.trusted_hosts, "testserver"]
    )
    app.add_middleware(
        CORSMiddleware,
        # Explicit allowlist. `*` is rejected at startup in production by the
        # Settings validator, so it cannot reach here.
        allow_origins=settings.security.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-Id",
            "X-CSRF-Token",
            "Idempotency-Key",
            "X-Device-Fingerprint",
        ],
        expose_headers=[
            "X-Request-Id",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
        ],
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware, is_production=settings.is_production)
    app.add_middleware(RequestContextMiddleware)


__all__ = [
    "AccessLogMiddleware",
    "BodySizeLimitMiddleware",
    "RequestContextMiddleware",
    "SecurityHeadersMiddleware",
    "install_middleware",
]
