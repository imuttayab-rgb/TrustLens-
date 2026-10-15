"""Health and readiness endpoints.

Two distinct checks, because they answer different questions:

* /health/live  - is the process alive? NO dependency checks, so a Redis blip
                  cannot trigger a restart loop that makes an outage worse.
* /health/ready - can it serve traffic? Checks DB and cache, and gates
                  load-balancer traffic.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from trustlens_api.api.deps import ContainerDep

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", summary="Liveness probe")
async def live(container: ContainerDep) -> dict[str, Any]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
async def ready(container: ContainerDep, response: Response) -> dict[str, Any]:
    checks: dict[str, str] = {}

    try:
        async with container.session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        checks["cache"] = "ok" if await container.cache.ping() else "error"
    except Exception:
        checks["cache"] = "error"

    healthy = all(value == "ok" for value in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "ok" if healthy else "degraded"}


@router.get("/worker", summary="Is the worker still consuming jobs?")
async def worker(container: ContainerDep, response: Response) -> dict[str, Any]:
    """The check that catches the failure nothing else does (P9-07).

    A worker process can be alive, connected, and consuming nothing. Every
    process-level probe reports healthy, `restart: unless-stopped` sees nothing
    to restart, and the only symptom is verifications that never finish.

    This reads the heartbeat the worker writes after each job, so a stale or
    absent beat is visible *without talking to the worker* - which is the exact
    case being tested for. 503 when stale, so an uptime monitor pointed here
    actually pages someone.
    """
    from trustlens.shared.telemetry import Heartbeat

    beat = await Heartbeat().read(container.cache)

    if beat is None:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unknown"}

    if not beat["healthy"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "ok" if beat["healthy"] else "stale"}


__all__ = ["router"]
