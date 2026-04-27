"""Redis-backed implementation of :class:`CacheClient`.

Uses ``redis.asyncio`` from ``redis-py``. The adapter owns its connection pool
and exposes a graceful ``aclose``.
"""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from typing import Self, cast

import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool

from app.core.logging import get_logger

log = get_logger(__name__)

_UNLOCK_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""


class RedisCache:
    """Production cache adapter."""

    def __init__(self, client: aioredis.Redis, pool: ConnectionPool) -> None:
        self._client = client
        self._pool = pool

    @classmethod
    async def connect(
        cls,
        *,
        url: str,
        max_connections: int,
        socket_timeout: float,
    ) -> Self:
        pool = ConnectionPool.from_url(
            url,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            decode_responses=True,
        )
        client = aioredis.Redis(connection_pool=pool)
        await client.ping()
        return cls(client, pool)

    async def get(self, key: str) -> str | None:
        result = await self._client.get(key)
        if result is None:
            return None
        return result if isinstance(result, str) else str(result)

    async def set(
        self,
        key: str,
        value: str,
        *,
        ttl_seconds: int,
        nx: bool = False,
    ) -> bool:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0 — infinite caches are banned")
        result = await self._client.set(key, value, ex=ttl_seconds, nx=nx)
        return bool(result)

    async def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        return int(await self._client.delete(*keys))

    async def incr(self, key: str, *, ttl_seconds: int | None = None) -> int:
        value = int(await self._client.incr(key))
        if ttl_seconds is not None and value == 1:
            await self._client.expire(key, ttl_seconds)
        return value

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(key))

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False

    @asynccontextmanager
    async def lock(
        self,
        key: str,
        *,
        ttl_seconds: int,
        blocking_timeout: float | None = None,
    ) -> AsyncIterator[bool]:
        """Distributed lock via ``SET NX EX`` + safe-DEL via Lua."""
        token = secrets.token_urlsafe(24)
        acquired = await self._client.set(key, token, ex=ttl_seconds, nx=True)
        try:
            yield bool(acquired)
        finally:
            if acquired:
                try:
                    res = self._client.eval(_UNLOCK_LUA, 1, key, token)
                    await cast("Awaitable[object]", res)
                except Exception:
                    log.warning("cache.lock.release_failed", key=key)

    async def aclose(self) -> None:
        try:
            await self._client.aclose()
        finally:
            await self._pool.aclose()
