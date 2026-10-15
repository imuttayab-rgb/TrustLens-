"""Fail-closed abuse protection shared by account and upload operations."""

from hashlib import sha256
from fastapi import HTTPException
from trustlens.core.domain.errors import RateLimitExceeded


async def enforce_limit(container, key: str, *, limit: int, window: int) -> None:
    """Raise a retryable 503 when the authoritative limiter cannot be reached."""
    if not container.settings.rate_limit.enabled:
        return
    try:
        allowed, _, retry = await container.rate_limiter.hit(
            key, limit=limit, window_seconds=window
        )
    except Exception:
        raise HTTPException(
            503, "Abuse protection temporarily unavailable", headers={"Retry-After": "30"}
        ) from None
    if not allowed:
        raise RateLimitExceeded("Too many requests. Try again later.", retry_after=retry)


def private_key(value: str) -> str:
    """Keep email addresses out of Redis key names and diagnostic output."""
    return sha256(value.strip().lower().encode()).hexdigest()
