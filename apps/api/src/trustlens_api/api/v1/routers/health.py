"""Health and readiness endpoints.

Two distinct checks, because they answer different questions:

* /health/live  - is the process alive? NO dependency checks, so a Redis blip
                  cannot trigger a restart loop that makes an outage worse.
* /health/ready - can it serve traffic? Checks DB and cache, and gates
                  load-balancer traffic.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from trustlens_api.api.deps import ContainerDep

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", summary="Liveness probe")
async def live(container: ContainerDep) -> dict:
    return {
        "status": "ok",
        "service": container.settings.observability.otel_service_name,
        "version": container.settings.app_version,
        "env": container.settings.env.value,
    }


@router.get("/ready", summary="Readiness probe")
async def ready(container: ContainerDep, response: Response) -> dict:
    checks: dict[str, str] = {}

    try:
        async with container.session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"

    try:
        checks["cache"] = "ok" if await container.cache.ping() else "error"
    except Exception as exc:
        checks["cache"] = f"error: {type(exc).__name__}"

    healthy = all(value == "ok" for value in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "ok" if healthy else "degraded", "checks": checks}


__all__ = ["router"]
