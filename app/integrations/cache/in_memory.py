"""In-memory ``CacheClient`` for unit tests / local feature spikes.

Not thread-safe and not multi-process-safe — DO NOT use in production.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass(slots=True)
class _Entry:
    value: str
    expires_at: float


class InMemoryCache:
    """Process-local cache with TTL and a simple lock implementation."""

    def __init__(self) -> None:
        self._data: dict[str, _Entry] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _now(self) -> float:
        return time.monotonic()

    def _purge(self, key: str) -> None:
        entry = self._data.get(key)
        if entry and entry.expires_at <= self._now():
            self._data.pop(key, None)

    async def get(self, key: str) -> str | None:
        self._purge(key)
        entry = self._data.get(key)
        return entry.value if entry else None

    async def set(
        self,
        key: str,
        value: str,
        *,
        ttl_seconds: int,
        nx: bool = False,
    ) -> bool:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        self._purge(key)
        if nx and key in self._data:
            return False
        self._data[key] = _Entry(value=value, expires_at=self._now() + ttl_seconds)
        return True

    async def delete(self, *keys: str) -> int:
        removed = 0
        for k in keys:
            if self._data.pop(k, None) is not None:
                removed += 1
        return removed

    async def incr(self, key: str, *, ttl_seconds: int | None = None) -> int:
        self._purge(key)
        current = self._data.get(key)
        new = int(current.value) + 1 if current else 1
        ttl = ttl_seconds or 60
        self._data[key] = _Entry(value=str(new), expires_at=self._now() + ttl)
        return new

    async def exists(self, key: str) -> bool:
        self._purge(key)
        return key in self._data

    async def ping(self) -> bool:
        return True

    @asynccontextmanager
    async def lock(
        self,
        key: str,
        *,
        ttl_seconds: int,
        blocking_timeout: float | None = None,
    ) -> AsyncIterator[bool]:
        async_lock = self._locks.setdefault(key, asyncio.Lock())
        try:
            if blocking_timeout is None:
                acquired = async_lock.locked() is False
                if acquired:
                    await async_lock.acquire()
            else:
                try:
                    await asyncio.wait_for(async_lock.acquire(), timeout=blocking_timeout)
                    acquired = True
                except TimeoutError:
                    acquired = False
            yield acquired
        finally:
            if async_lock.locked():
                async_lock.release()

    async def aclose(self) -> None:
        self._data.clear()
        self._locks.clear()
