"""Redis cache, rate limiting and distributed locks."""

from __future__ import annotations

import secrets
from typing import Any, cast

from redis.asyncio import ConnectionPool, Redis

from trustlens.core.domain.ports import Cache


class RedisCache(Cache):
    """Cache-aside store.

    Never a system of record: every value here is derivable from Postgres, so
    losing all of Redis costs latency and nothing else.
    """

    def __init__(self, redis: Redis, *, namespace: str = "tl") -> None:
        self._redis = redis
        self._ns = namespace
        #: Lock tokens, so a lock is only released by the holder. Releasing
        #: someone else's expired lock is how two workers end up scoring the
        #: same seller concurrently.
        self._lock_tokens: dict[str, str] = {}

    @classmethod
    def from_url(cls, url: str, *, max_connections: int = 20) -> RedisCache:
        pool = ConnectionPool.from_url(url, max_connections=max_connections, decode_responses=True)
        return cls(Redis(connection_pool=pool))

    def _key(self, key: str) -> str:
        return f"{self._ns}:{key}"

    async def get(self, key: str) -> str | None:
        value = await self._redis.get(self._key(key))
        return value if value is None else str(value)

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        await self._redis.set(self._key(key), value, ex=ttl_seconds)

    async def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        return int(await self._redis.delete(*(self._key(k) for k in keys)))

    async def delete_pattern(self, pattern: str) -> int:
        """Delete by glob using SCAN.

        Deliberately not KEYS: KEYS blocks the Redis event loop for the whole
        scan, which on a shared instance is an outage waiting to happen.
        """
        deleted = 0
        async for key in self._redis.scan_iter(match=self._key(pattern), count=200):
            deleted += int(await self._redis.delete(key))
        return deleted

    async def incr(self, key: str, *, ttl_seconds: int | None = None) -> int:
        full = self._key(key)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.incr(full)
            if ttl_seconds is not None:
                # NX: only set the TTL on first increment, so a busy window is
                # not perpetually extended and never expires.
                pipe.expire(full, ttl_seconds, nx=True)
            result = await pipe.execute()
        return int(result[0])

    async def exists(self, key: str) -> bool:
        return bool(await self._redis.exists(self._key(key)))

    async def acquire_lock(self, key: str, *, ttl_seconds: int) -> bool:
        token = secrets.token_urlsafe(16)
        acquired = await self._redis.set(self._key(key), token, nx=True, ex=ttl_seconds)
        if acquired:
            self._lock_tokens[key] = token
        return bool(acquired)

    async def release_lock(self, key: str) -> None:
        token = self._lock_tokens.pop(key, None)
        if token is None:
            return
        # Compare-and-delete in Lua so we cannot delete a lock that already
        # expired and was re-acquired by someone else.
        # redis-py types eval() as sync-or-async depending on the client
        # flavour; this client is always the async one.
        await cast("Any", self._redis).eval(
            """
            if redis.call('get', KEYS[1]) == ARGV[1] then
              return redis.call('del', KEYS[1])
            end
            return 0
            """,
            1,
            self._key(key),
            token,
        )

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except Exception:
            return False

    async def close(self) -> None:
        await self._redis.aclose()


class TokenBucketLimiter:
    """Fixed-window rate limiter.

    A true token bucket would be smoother, but a fixed window is exact,
    trivially auditable, and its worst case (2x the limit across a window
    boundary) is acceptable for every limit in this system.
    """

    def __init__(self, cache: RedisCache) -> None:
        self._cache = cache

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> tuple[bool, int, int]:
        """Returns (allowed, remaining, retry_after_seconds)."""
        count = await self._cache.incr(f"ratelimit:{key}", ttl_seconds=window_seconds)
        allowed = count <= limit
        remaining = max(0, limit - count)
        return allowed, remaining, 0 if allowed else window_seconds


class IdempotencyStore:
    """Stores responses for replayed `Idempotency-Key` requests.

    Without this, a partner's retry-on-timeout doubles our LLM bill and can
    create duplicate sellers.
    """

    def __init__(self, cache: RedisCache, *, ttl_seconds: int = 86_400) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    async def get(self, key: str) -> dict[str, Any] | None:
        import json

        raw = await self._cache.get(f"idem:{key}")
        return None if raw is None else dict(json.loads(raw))

    async def put(self, key: str, *, fingerprint: str, status: int, body: str) -> None:
        import json

        await self._cache.set(
            f"idem:{key}",
            json.dumps({"fingerprint": fingerprint, "status": status, "body": body}),
            ttl_seconds=self._ttl,
        )


__all__ = ["IdempotencyStore", "RedisCache", "TokenBucketLimiter"]
