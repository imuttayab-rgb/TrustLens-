"""Keeps the ARQ worker consuming across Redis outages (P9-09).

ARQ's `run_worker` returns when its Redis connection dies. Run directly as the
container's entrypoint, that means the process exits and the queue stops being
consumed - no OCR, no face matching, no email, no OTP, no rescoring - and
nothing announces it. The jobs are still there; nobody is taking them.

Locally this looked environmental: Docker Desktop shut down overnight and both
worker processes were gone in the morning. In production it is routine.
**Upstash closes idle connections by design**, so a worker that dies on a
dropped connection dies every quiet night.

A container restart policy alone is not enough, for two reasons:

* Restarting reloads the OCR and face models from disk. That is seconds of work
  to recover from a blip that lasted milliseconds.
* A crash-looping container on a free tier gets throttled or stopped, which
  turns a transient network event into an outage that needs a human.

So the retry lives here, inside the process, and the restart policy stays as
the outer net for everything this cannot catch.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import signal
from typing import Any

from arq.worker import Worker
from arq.worker import Worker as _ArqWorker

from trustlens.shared.logging import get_logger

log = get_logger(__name__)

#: Backoff between reconnect attempts. Starts fast because most drops are a
#: blip, and caps so a genuinely dead Redis is retried at a rate that neither
#: hammers it nor waits so long that recovery needs a human.
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 60.0
BACKOFF_FACTOR = 2.0

#: After this long connected, the next failure is treated as a fresh incident
#: rather than a continuation. Without it a worker that reconnects fine every
#: few hours would creep up to the maximum backoff and stay there.
HEALTHY_RESET_SECONDS = 120.0


async def run_forever(settings_cls: type, *, max_restarts: int | None = None) -> int:
    """Run the ARQ worker, restarting it when Redis drops.

    `max_restarts` exists for the tests; production passes None and this only
    returns on a deliberate signal.
    """
    loop = asyncio.get_running_loop()
    stopping = asyncio.Event()

    def request_stop(sig: signal.Signals) -> None:
        # A deliberate stop must not be retried. Without this the supervisor
        # would treat SIGTERM as an outage and restart the worker the
        # orchestrator just asked to go away.
        log.info("worker_stop_requested", signal=sig.name)
        stopping.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        # Windows has no add_signal_handler for these. Development only;
        # the deployed target is Linux.
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, request_stop, sig)

    backoff = INITIAL_BACKOFF_SECONDS
    restarts = 0

    while not stopping.is_set():
        worker: Worker | None = None
        started_at = loop.time()
        try:
            worker = Worker(**_worker_kwargs(settings_cls))
            log.info("worker_connecting")
            await worker.async_run()
            # A clean return means ARQ stopped on its own terms - a burst limit
            # or a close. Not an error, so not retried.
            log.info("worker_exited_cleanly")
            return 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if stopping.is_set():
                break

            uptime = loop.time() - started_at
            if uptime >= HEALTHY_RESET_SECONDS:
                backoff = INITIAL_BACKOFF_SECONDS

            restarts += 1
            log.warning(
                "worker_connection_lost",
                error=type(exc).__name__,
                detail=str(exc)[:200],
                uptime_seconds=round(uptime, 1),
                restart=restarts,
                retry_in_seconds=round(backoff, 1),
            )

            if max_restarts is not None and restarts >= max_restarts:
                return 1

            try:
                await asyncio.wait_for(stopping.wait(), timeout=backoff)
                break  # Stop was requested while we were waiting.
            except TimeoutError:
                pass

            backoff = min(backoff * BACKOFF_FACTOR, MAX_BACKOFF_SECONDS)
        finally:
            if worker is not None:
                # The connection is usually already gone by here, so closing it
                # frequently raises. That must not mask the original error or
                # abort the retry - which is the whole point of this loop.
                with contextlib.suppress(Exception):
                    await worker.close()

    log.info("worker_stopped", restarts=restarts)
    return 0


def _worker_kwargs(settings_cls: type) -> dict[str, Any]:
    """Translate a WorkerSettings class into Worker(**kwargs).

    `arq.run_worker` does this itself, but it also installs its own signal
    handlers and owns the event loop, which is exactly what has to be inverted
    here.
    """
    # Intersected with the live signature, not just the constant: an arq
    # upgrade that renames or drops a parameter would otherwise raise
    # TypeError at boot, in production, on a platform with no shell.
    #
    # Deliberately reads `_ArqWorker`, the real class captured at import, not
    # the module-level `Worker` that tests substitute - otherwise the
    # intersection is taken against the stand-in and every real parameter is
    # filtered out, which is a fake passing while production breaks.
    accepted = _WORKER_FIELDS & set(inspect.signature(_ArqWorker.__init__).parameters)
    kwargs = {
        key: getattr(settings_cls, key)
        for key in dir(settings_cls)
        if not key.startswith("_") and key in accepted
    }
    # ARQ installs its own SIGTERM/SIGINT handlers and cancels the run on them.
    # This supervisor owns the signals instead, so a deliberate stop can be
    # told apart from a dropped connection - otherwise SIGTERM looks like an
    # outage and gets "recovered" from by restarting what was just stopped.
    kwargs["handle_signals"] = False
    return kwargs


#: Attributes ARQ's `Worker.__init__` accepts (arq 0.28). Named explicitly, and
#: intersected with the real signature below, so an unrelated attribute on
#: WorkerSettings cannot become an unexpected keyword argument at boot - and so
#: an arq upgrade that drops a parameter fails loudly here rather than in
#: production.
_WORKER_FIELDS = frozenset(
    {
        "after_job_end",
        "allow_abort_jobs",
        "cron_jobs",
        "ctx",
        "expires_extra_ms",
        "functions",
        "health_check_interval",
        "health_check_key",
        "job_completion_wait",
        "job_deserializer",
        "job_serializer",
        "job_timeout",
        "keep_result",
        "keep_result_forever",
        "log_results",
        "max_burst_jobs",
        "max_jobs",
        "max_tries",
        "on_job_end",
        "on_job_start",
        "on_shutdown",
        "on_startup",
        "poll_delay",
        "queue_name",
        "queue_read_limit",
        "redis_pool",
        "redis_settings",
        "retry_jobs",
        "timezone",
    }
)


def main() -> int:
    from trustlens_worker.main import WorkerSettings

    return asyncio.run(run_forever(WorkerSettings))


if __name__ == "__main__":
    raise SystemExit(main())
