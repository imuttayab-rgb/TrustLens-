"""Error reporting and health signals (P9-07).

This module was an empty file until 22 August 2026, which meant the system had
no way to tell anyone it was broken. The failure mode that matters here is not
a crash - a crash is visible. It is the worker quietly stopping consumption:
no OCR, no face match, no verification email, no OTP, no rescoring, and a UI
that keeps saying "processing" forever.

**Works with nothing configured.** Structured JSON logs are always emitted, so
`docker compose logs` is a complete monitoring setup for a laptop demo. Sentry
is additive: set `SENTRY_DSN` and the same events also go there. Nothing here
requires an account, a network, or a hosting platform - which is the point,
because the students may run this on a laptop for a year before choosing a
host.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from trustlens.shared.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from trustlens.shared.config.settings import ObservabilitySettings

log = get_logger(__name__)

_sentry_enabled = False


def init_error_reporting(
    settings: ObservabilitySettings,
    *,
    environment: str,
    release: str,
    component: Literal["api", "worker"],
) -> bool:
    """Wire up Sentry if a DSN is configured. Returns whether it was.

    Deliberately never raises. Monitoring that can take down the thing it
    monitors is worse than no monitoring, and a typo in a DSN must not stop
    the API from booting.
    """
    global _sentry_enabled

    if not settings.sentry_dsn:
        log.info("error_reporting_disabled", reason="no SENTRY_DSN configured")
        return False

    try:
        import sentry_sdk
    except ImportError:
        log.warning(
            "sentry_sdk_not_installed",
            hint="pip install sentry-sdk, or leave SENTRY_DSN blank",
        )
        return False

    try:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=environment,
            release=release,
            traces_sample_rate=0,  # Request traces can carry query/body data; export sanitized errors only.
            # This system holds CNIC numbers, selfies and phone numbers. Never
            # let an error report carry a request body or headers off the box.
            send_default_pii=False,
            max_request_body_size="never",
            before_send=_scrub,
        )
        sentry_sdk.set_tag("component", component)
    except Exception as exc:
        log.warning("error_reporting_init_failed", error=str(exc))
        return False

    _sentry_enabled = True
    log.info("error_reporting_enabled", environment=environment, release=release)
    return True


#: Substrings that must never leave the machine inside an error report.
_SENSITIVE = (
    "password",
    "token",
    "secret",
    "authorization",
    "cookie",
    "cnic",
    "otp",
    "api_key",
    "apikey",
    "private_key",
    "selfie",
)


def _scrub(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """Export only error classification and bounded source locations, never PII."""
    import re
    from pathlib import PurePosixPath
    from trustlens.shared.logging import redact_processor

    identifier = re.compile(r"^[A-Za-z_][A-Za-z0-9_.<>-]{0,99}$")
    safe = {
        k: v
        for k, v in event.items()
        if k
        in {
            "event_id",
            "timestamp",
            "platform",
            "level",
            "release",
            "environment",
            "logger",
        }
    }
    exception = event.get("exception")
    values = exception.get("values", []) if isinstance(exception, dict) else []
    projected = []
    for item in values[:5] if isinstance(values, list) else []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type", "Exception"))
        trace = item.get("stacktrace")
        frames = trace.get("frames", []) if isinstance(trace, dict) else []
        locations = []
        for frame in frames[-30:] if isinstance(frames, list) else []:
            if not isinstance(frame, dict):
                continue
            filename = PurePosixPath(str(frame.get("filename", "unknown")).replace("\\", "/")).name
            function = str(frame.get("function", "unknown"))
            locations.append(
                {
                    "filename": filename if identifier.fullmatch(filename) else "unknown",
                    "function": function if identifier.fullmatch(function) else "unknown",
                    "lineno": frame.get("lineno") if type(frame.get("lineno")) is int else None,
                    "in_app": frame.get("in_app") is True,
                }
            )
        projected.append(
            {
                "type": kind if identifier.fullmatch(kind) else "Exception",
                "value": "[redacted]",
                "stacktrace": {"frames": locations},
            }
        )
    safe = redact_processor(None, "error", safe)
    safe["exception"] = {"values": projected}
    return safe


def capture_exception(exc: BaseException, **context: Any) -> None:
    """Report an error. Always logs; also sends to Sentry when configured."""
    log.error("exception", error=str(exc), error_type=type(exc).__name__, **context)
    if not _sentry_enabled:
        return
    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_exception(exc)
    except Exception:  # noqa: S110 - reporting must never raise
        pass


# ── Worker liveness ──────────────────────────────────────────────────


@dataclass(slots=True)
class Heartbeat:
    """Records that the worker is still consuming jobs.

    A process can be running and useless. `restart: unless-stopped` catches a
    crash; it cannot catch a worker that is alive, connected and silently
    processing nothing. This is the signal that separates the two, and it
    pairs with the reconnect logic in the supervisor (P9-09).

    Stored in Redis with a TTL rather than in memory, so an external check can
    read it without talking to the worker - the worker being unreachable is
    exactly the case being checked for.
    """

    key: str = "worker:heartbeat"
    ttl_seconds: int = 120
    jobs_completed: int = 0
    started_at: float = field(default_factory=time.monotonic)

    async def beat(self, cache: Any, *, job_name: str | None = None) -> None:
        self.jobs_completed += 1
        try:
            await cache.set(
                self.key,
                f"{time.time():.0f}|{self.jobs_completed}|{job_name or '-'}",
                ttl_seconds=self.ttl_seconds,
            )
        except Exception as exc:
            # A heartbeat that fails is worth a line, never an interruption:
            # the job it accompanies has already been done.
            log.warning("heartbeat_write_failed", error=str(exc))

    async def read(self, cache: Any) -> dict[str, Any] | None:
        """What an external check sees. `None` means no beat within the TTL."""
        try:
            raw = await cache.get(self.key)
        except Exception as exc:
            log.warning("heartbeat_read_failed", error=str(exc))
            return None
        if not raw:
            return None

        timestamp, _, rest = str(raw).partition("|")
        completed, _, job = rest.partition("|")
        age = time.time() - float(timestamp)
        return {
            "last_beat_epoch": float(timestamp),
            "seconds_since_last_beat": round(age, 1),
            "jobs_completed": int(completed or 0),
            "last_job": job or None,
            "healthy": age < self.ttl_seconds,
        }


__all__ = [
    "Heartbeat",
    "capture_exception",
    "init_error_reporting",
]
