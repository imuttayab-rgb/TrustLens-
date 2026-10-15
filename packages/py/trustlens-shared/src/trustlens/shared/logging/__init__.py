"""Structured logging with PII redaction.

Redaction runs as the last processor in the chain rather than at call sites,
because call sites are exactly where people forget. Given this system handles
CNIC numbers, selfies and face embeddings, a single careless
`log.info("verifying", document=doc)` would otherwise put a national ID into a
log aggregator forever.
"""

from __future__ import annotations

import logging
import re
import sys
from contextvars import ContextVar
from typing import Any, Literal, cast

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
        "email",
        "phone",
        "e164",
        "ip_address",
        "user_agent",
        "full_name",
        "address",
        "query",
        "exception",
        "exc_info",
        "stack",
        "error",
        "detail",
        "headers",
        "body",
        "payload",
        "context",
        "recipient",
    }
)

#: Keys that are useful for debugging but must be shortened rather than
#: dropped entirely.
PARTIAL_KEYS = frozenset({"ip"})

REDACTED = "[redacted]"


def _mask(key: str, value: Any) -> str:
    """Personal values are omitted, including network prefixes."""
    return REDACTED


def safe_text(value: str) -> str:
    """Scrub common embedded identifiers; structured sensitive fields are dropped entirely.

    This is defense in depth, not a promise to identify every secret in arbitrary
    prose. Callers should use stable event names and typed metadata, not free text.
    """
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", REDACTED, value)
    value = re.sub(
        r"(?i)(password|passwd|token|secret|otp|code|api[-_]?key|authorization)\s*[=:]\s*[^\s&,;]+",
        r"\1=[redacted]",
        value,
    )
    value = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", REDACTED, value)
    value = re.sub(r"(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)", REDACTED, value)
    value = re.sub(r"(?i)(https?://[^\s?]+)\?[^\s]+", r"\1?[redacted]", value)
    value = re.sub(r"(?i)(://)[^\s/@:]+:[^\s/@]+@", r"\1[redacted]@", value)
    return value[:4000]


def redact_processor(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Drop or mask sensitive values anywhere in the event, including nested."""

    def scrub(value: Any, depth: int = 0) -> Any:
        if depth > 6:  # guard against pathological nesting
            return REDACTED
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for k, v in value.items():
                key = str(k).lower()
                if (
                    key in {"error_type", "exception_type"}
                    and isinstance(v, str)
                    and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,99}", v)
                ):
                    out[k] = v
                elif any(s in key for s in SENSITIVE_KEYS):
                    out[k] = REDACTED
                elif any(p in key for p in PARTIAL_KEYS):
                    out[k] = _mask(key, v)
                else:
                    out[k] = scrub(v, depth + 1)
            return out
        if isinstance(value, list | tuple):
            return [scrub(v, depth + 1) for v in value]
        if isinstance(value, str):
            return safe_text(value)
        return value if value is None or type(value) in (bool, int, float) else REDACTED

    return cast("dict[str, Any]", scrub(event_dict))


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
        structlog.processors.format_exc_info,
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
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level]),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    class SafeFormatter(logging.Formatter):
        """Route third-party logging through the same policy; never render raw exceptions."""

        def format(self, record: logging.LogRecord) -> str:
            message = safe_text(record.getMessage())
            # Libraries sometimes embed SQL, request bodies or credentials in free text.
            # Keep the logger/level, but suppress unknown message text in deployed logs.
            event = {
                "event": message if env in {"development", "test"} else "library_log",
                "logger": record.name,
                "level": record.levelname,
            }
            if record.exc_info:
                event["exception_type"] = (
                    record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
                )
            import json

            return json.dumps(redact_processor(None, record.levelname, event))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(SafeFormatter())
    logging.basicConfig(handlers=[handler], level=level, force=True)
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
