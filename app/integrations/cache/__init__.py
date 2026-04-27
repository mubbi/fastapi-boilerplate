"""Cache integration: Protocol + concrete adapters."""

from __future__ import annotations

from app.core.config import Settings
from app.core.logging import get_logger
from app.integrations.cache.base import CacheClient
from app.integrations.cache.in_memory import InMemoryCache
from app.integrations.cache.redis import RedisCache

log = get_logger(__name__)


async def build_cache_client(settings: Settings) -> CacheClient:
    """Pick the right adapter for the current environment.

    - The app always uses the configured Redis URL.
    - Tests inject in-memory fakes via the container fixture.
    """
    redis_url = settings.redis_url
    log.info("cache.adapter", adapter="redis", url_host=_safe_host(redis_url))
    return await RedisCache.connect(
        url=redis_url,
        max_connections=settings.redis.max_connections,
        socket_timeout=settings.redis.socket_timeout,
    )


def _safe_host(url: str) -> str:
    """Return the host part of a redis:// URL without leaking credentials."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.hostname or "unknown"
    except Exception:
        return "unknown"


__all__ = [
    "CacheClient",
    "InMemoryCache",
    "RedisCache",
    "build_cache_client",
]
