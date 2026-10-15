"""ARQ job queue adapter."""

from __future__ import annotations

from typing import Any

from arq import create_pool
from arq.connections import ArqRedis
from arq.connections import RedisSettings as ArqRedisSettings

from trustlens.core.domain.ports import JobQueue


class ArqJobQueue(JobQueue):
    """Enqueues jobs BY NAME.

    This is the mechanism that enforces ADR-0003: if the API imported worker
    functions to enqueue them, it would inherit torch and tensorflow through
    the import graph and the "thin API" decision would silently evaporate.
    """

    def __init__(self, redis: ArqRedis) -> None:
        self._redis = redis

    @classmethod
    async def connect(cls, url: str) -> ArqJobQueue:
        return cls(await create_pool(ArqRedisSettings.from_dsn(url)))

    async def enqueue(
        self,
        job_name: str,
        *args: Any,
        job_id: str | None = None,
        defer_seconds: int | None = None,
        **kwargs: Any,
    ) -> str:
        job = await self._redis.enqueue_job(
            job_name,
            *args,
            _job_id=job_id,
            _defer_by=defer_seconds,
            **kwargs,
        )
        # A None result means a job with this id already exists - the dedup
        # path, not an error: it is how the score-recompute debounce collapses
        # a burst of verification events into one computation.
        return job.job_id if job is not None else (job_id or "")

    async def status(self, job_id: str) -> str | None:
        from arq.jobs import Job

        job = Job(job_id, self._redis)
        try:
            return str(await job.status())
        except Exception:
            return None

    async def describe(self, job_id: str) -> dict[str, Any] | None:
        """Read server-enqueued scope before allowing a status lookup."""
        from arq.jobs import Job

        info = await Job(job_id, self._redis).info()
        return None if info is None else {"job_name": info.function, "payload": info.kwargs}

    async def close(self) -> None:
        await self._redis.aclose()


__all__ = ["ArqJobQueue"]
