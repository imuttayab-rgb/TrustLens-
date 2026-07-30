"""Structured logging with PII redaction.

Redaction runs as the last processor in the chain rather than at call sites,
because call sites are exactly where people forget. Given this system handles
CNIC numbers, selfies and face embeddings, a single careless
`log.info("verifying", document=doc)` would otherwise put a national ID into a
log aggregator forever.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any, Literal

import structlog

#: Request-scoped context, attached to every log line emitted during a request
#: or job. `request_id` is what turns a user's "verification failed" report
#: into a single log query.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
actor_id_var: ContextVar[str | None] = ContextVar("actor_id", default=None)
actor_type_var: ContextVar[str | None] = ContextVar("actor_type", default=None)

#: Keys whose values are replaced wholesale. Substring matching, so
#: `user_password`, `refresh_token` and `x-api-key` are all covered.
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "authorization",
        "api_key",
        "apikey",
        "cookie",
        "set-cookie",
        "otp",
        "code_hash",
        "cnic",
        "cnic_number",
        "national_id",
        "dob",
        "date_of_birth",
        "face_embedding",
        "embedding",
        "selfie",
        "private_key",
        "pepper",
        "encryption_key",
        "credit_card",
    }
)

#: Keys that are useful for debugging but must be shortened rather than
#: dropped entirely.
PARTIAL_KEYS = frozenset({"email", "phone", "e164", "ip", "ip_address"})

REDACTED = "[redacted]"


def _mask(key: str, value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return REDACTED
    if "email" in key:
        local, _, domain = value.partition("@")
        return f"{local[:2]}***@{domain}" if domain else REDACTED
    if "phone" in key or key == "e164":
        return f"{value[:4]}***{value[-2:]}" if len(value) > 6 else REDACTED
    if "ip" in key:
        # Keep the network portion for correlation, drop the host portion.
        parts = value.split(".")
        return ".".join([*parts[:2], "x", "x"]) if len(parts) == 4 else REDACTED
    return REDACTED


def redact_processor(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Drop or mask sensitive values anywhere in the event, including nested."""

    def scrub(value: Any, depth: int = 0) -> Any:
        if depth > 6:  # guard against pathological nesting
            return value
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for k, v in value.items():
                key = str(k).lower()
                if any(s in key for s in SENSITIVE_KEYS):
                    out[k] = REDACTED
                elif any(p in key for p in PARTIAL_KEYS):
                    out[k] = _mask(key, v)
                else:
                    out[k] = scrub(v, depth + 1)
            return out
        if isinstance(value, list | tuple):
            return [scrub(v, depth + 1) for v in value]
        return value

    return scrub(event_dict)  # type: ignore[return-value]


def context_processor(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Attach the request-scoped identifiers to every line."""
    for key, var in (
        ("request_id", request_id_var),
        ("trace_id", trace_id_var),
        ("actor_id", actor_id_var),
        ("actor_type", actor_type_var),
    ):
        if (value := var.get()) is not None:
            event_dict.setdefault(key, value)
    return event_dict


def configure_logging(
    *,
    level: str = "INFO",
    fmt: Literal["console", "json"] = "json",
    service: str = "trustlens-api",
    version: str = "0.0.0",
    env: str = "development",
) -> None:
    """Configure structlog and route stdlib logging through it.

    Output goes to stdout as JSON in deployed environments - Railway and most
    platforms aggregate stdout, and a JSON line is greppable by field.
    """
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        # structlog's own add_log_level, not the stdlib one: we render through
        # PrintLoggerFactory (straight to stdout), and the stdlib processors
        # assume a logging.Logger with a .name attribute.
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        context_processor,
        _static_fields(service=service, version=version, env=env),
        # Redaction is LAST so nothing added by an earlier processor escapes it.
        redact_processor,
    ]

    renderer: Any = (
        structlog.dev.ConsoleRenderer(colors=True)
        if fmt == "console"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level]),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "botocore", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _static_fields(**fields: str) -> Any:
    def processor(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        for key, value in fields.items():
            event_dict.setdefault(key, value)
        return event_dict

    return processor


def get_logger(name: str | None = None) -> Any:
    """Returns a bound logger, tagged with the caller's module name."""
    return structlog.get_logger().bind(logger=name) if name else structlog.get_logger()


__all__ = [
    "PARTIAL_KEYS",
    "REDACTED",
    "SENSITIVE_KEYS",
    "actor_id_var",
    "actor_type_var",
    "configure_logging",
    "get_logger",
    "redact_processor",
    "request_id_var",
    "trace_id_var",
]
