"""HTTP client Protocol — services depend on this, never on ``httpx`` directly."""

from __future__ import annotations

from typing import Protocol

import httpx


class HttpClient(Protocol):
    """Async HTTP client with bounded retries and shared connection pool.

    Implementations expose the underlying ``httpx.AsyncClient`` only through
    explicit verbs so cross-cutting policies (retries, timeouts, tracing, metrics)
    can be enforced at the boundary.
    """

    async def get(self, url: str, **kwargs: object) -> httpx.Response: ...

    async def post(self, url: str, **kwargs: object) -> httpx.Response: ...

    async def put(self, url: str, **kwargs: object) -> httpx.Response: ...

    async def patch(self, url: str, **kwargs: object) -> httpx.Response: ...

    async def delete(self, url: str, **kwargs: object) -> httpx.Response: ...

    async def request(self, method: str, url: str, **kwargs: object) -> httpx.Response: ...

    async def aclose(self) -> None: ...
