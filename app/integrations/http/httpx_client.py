"""``httpx.AsyncClient`` adapter with tenacity-driven retries.

Constructed **once** per process via :func:`build_http_client` (see
``app.integrations.http.__init__``) and reused for every outbound call.
"""

from __future__ import annotations

from typing import Any, Self

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.config import Settings
from app.core.exceptions import ExternalServiceError
from app.core.exceptions import TimeoutError as DomainTimeoutError
from app.core.logging import get_logger

log = get_logger(__name__)


class HttpxClient:
    """Reusable async HTTP client with retries on connect/read errors."""

    def __init__(self, *, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    @classmethod
    async def connect(cls, *, settings: Settings) -> Self:
        timeout = httpx.Timeout(
            connect=settings.http_client.timeout_seconds,
            read=settings.http_client.timeout_seconds,
            write=settings.http_client.timeout_seconds,
            pool=settings.http_client.timeout_seconds,
        )
        limits = httpx.Limits(
            max_connections=settings.http_client.max_connections,
            max_keepalive_connections=settings.http_client.max_keepalive,
        )
        client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            follow_redirects=False,
            headers={
                "User-Agent": f"{settings.app_name}/{settings.app_version}",
            },
        )
        return cls(client=client, settings=settings)

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        retryer = AsyncRetrying(
            stop=stop_after_attempt(self._settings.http_client.retry_attempts + 1),
            wait=wait_exponential_jitter(
                initial=self._settings.http_client.retry_backoff_base,
                max=10.0,
            ),
            retry=retry_if_exception_type(
                (httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.PoolTimeout)
            ),
            reraise=True,
        )
        try:
            async for attempt in retryer:
                with attempt:
                    response = await self._client.request(method, url, **kwargs)
                    return response
        except httpx.TimeoutException as exc:
            log.warning("http.timeout", url=str(url), method=method)
            raise DomainTimeoutError(message="errors.http.timeout") from exc
        except RetryError as exc:
            log.error("http.retries_exhausted", url=str(url), method=method)
            raise ExternalServiceError(message="errors.http.upstream_unreachable") from exc
        except httpx.HTTPError as exc:
            log.error("http.error", url=str(url), method=method, error=str(exc))
            raise ExternalServiceError(message="errors.http.upstream_failure") from exc
        # Pragma: unreachable — AsyncRetrying always returns or raises.
        raise ExternalServiceError(message="errors.http.unreachable")

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", url, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()
