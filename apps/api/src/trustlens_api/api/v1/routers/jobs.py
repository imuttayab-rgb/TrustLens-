"""Job status polling.

Backed by `job_runs` in Postgres rather than by Redis alone: Redis can evict,
and a seller asking "is my verification done?" needs a durable answer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from trustlens.core.domain.errors import EntityNotFound
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.common import envelope
from trustlens_api.api.v1.schemas.seller import JobStatusResponse

router = APIRouter(prefix="/jobs", tags=["Jobs"])

#: Coarse progress per stage. The wizard shows these so a 30-second wait reads
#: as visible progress rather than a frozen screen - the difference between
#: "it's broken" and "it's working" in a demo.
STAGE_PROGRESS: dict[str, tuple[str, int]] = {
    "QUEUED": ("Waiting to start", 5),
    "RUNNING": ("Processing", 50),
    "SUCCEEDED": ("Complete", 100),
    "FAILED": ("Failed", 100),
    "DEAD": ("Failed", 100),
    "CANCELLED": ("Cancelled", 100),
}


@router.get("/{job_id}", summary="Poll a background job")
async def get_job(
    job_id: str,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    run = await uow.job_runs.get_by_key(job_id)

    if run is None:
        # Fall back to the queue: the job may not have been mirrored yet.
        queue_status = await container.queue.status(job_id)
        if queue_status is None:
            raise EntityNotFound("job", job_id)
        stage, progress = STAGE_PROGRESS.get(queue_status.upper(), ("Processing", 50))
        return envelope(
            JobStatusResponse(
                job_id=job_id, status=queue_status.upper(), stage=stage, progress=progress
            ).model_dump(by_alias=True),
            request_id=meta.request_id,
        )

    stage, progress = STAGE_PROGRESS.get(run.status, ("Processing", 50))
    return envelope(
        JobStatusResponse(
            job_id=job_id,
            status=run.status,
            stage=stage,
            progress=progress,
            result=run.result,
            # The user-facing reason only. The stack trace stays in the log.
            error=run.error_message if run.status in {"FAILED", "DEAD"} else None,
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


__all__ = ["router"]
