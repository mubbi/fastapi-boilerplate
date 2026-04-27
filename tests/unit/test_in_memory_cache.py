"""Contract tests for the in-memory cache adapter."""

from __future__ import annotations

import pytest

from app.integrations.cache.in_memory import InMemoryCache


@pytest.mark.unit
async def test_set_and_get() -> None:
    cache = InMemoryCache()
    await cache.set("k", "v", ttl_seconds=60)
    assert await cache.get("k") == "v"
    assert await cache.exists("k") is True


@pytest.mark.unit
async def test_set_nx_conflict() -> None:
    cache = InMemoryCache()
    assert await cache.set("k", "v1", ttl_seconds=60, nx=True) is True
    assert await cache.set("k", "v2", ttl_seconds=60, nx=True) is False
    assert await cache.get("k") == "v1"


@pytest.mark.unit
async def test_delete_returns_count() -> None:
    cache = InMemoryCache()
    await cache.set("a", "1", ttl_seconds=60)
    await cache.set("b", "2", ttl_seconds=60)
    deleted = await cache.delete("a", "b", "c")
    assert deleted == 2


@pytest.mark.unit
async def test_incr_with_ttl() -> None:
    cache = InMemoryCache()
    assert await cache.incr("hits", ttl_seconds=60) == 1
    assert await cache.incr("hits", ttl_seconds=60) == 2


@pytest.mark.unit
async def test_invalid_ttl_rejected() -> None:
    cache = InMemoryCache()
    with pytest.raises(ValueError, match="ttl_seconds must be > 0"):
        await cache.set("k", "v", ttl_seconds=0)
