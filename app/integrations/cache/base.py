"""Cache Protocol — the contract every adapter must satisfy.

Spec §6.2 / §10. Hard rules:
- Every key has a TTL; no infinite caches.
- Keys are namespaced (``boilerplate:v1:...``); never include unbounded user input.
- Distributed locks set both ``EX`` (TTL) and a unique token for safe ``DEL``.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol


class CacheClient(Protocol):
    """Async cache client capable of basic KV ops and distributed locking."""

    async def get(self, key: str) -> str | None: ...

    async def set(
        self,
        key: str,
        value: str,
        *,
        ttl_seconds: int,
        nx: bool = False,
    ) -> bool: ...

    async def delete(self, *keys: str) -> int: ...

    async def incr(self, key: str, *, ttl_seconds: int | None = None) -> int: ...

    async def exists(self, key: str) -> bool: ...

    async def ping(self) -> bool: ...

    def lock(
        self,
        key: str,
        *,
        ttl_seconds: int,
        blocking_timeout: float | None = None,
    ) -> AbstractAsyncContextManager[bool]:
        """Distributed lock context manager. Enters ``True`` if acquired, else ``False``.

        Implementations return an async context manager (e.g. via
        ``@asynccontextmanager``); the structural return type is checked here.
        """
        ...

    async def aclose(self) -> None: ...
