"""Tests for ``app.utils.*`` helpers — pure, no I/O."""

from __future__ import annotations

import asyncio

import pytest

from app.utils.async_utils import gather_with_concurrency, with_timeout
from app.utils.ids import new_uuid7, new_uuid7_hex
from app.utils.pagination import Page, PaginationParams
from app.utils.text import normalize_email, slugify, truncate


@pytest.mark.unit
def test_uuid7_is_uuid() -> None:
    u = new_uuid7()
    assert u.version == 7
    h = new_uuid7_hex()
    assert len(h) == 32
    assert all(c in "0123456789abcdef" for c in h)


@pytest.mark.unit
def test_pagination_clamps() -> None:
    p = PaginationParams(page=1, size=20)
    assert p.offset == 0
    assert p.limit == 20

    with pytest.raises(ValueError, match="page"):
        PaginationParams(page=0)
    with pytest.raises(ValueError, match="size"):
        PaginationParams(size=0)
    with pytest.raises(ValueError, match="size"):
        PaginationParams(size=10000)


@pytest.mark.unit
def test_page_metadata() -> None:
    page: Page[int] = Page(items=[1, 2, 3], page=2, size=3, total=8)
    assert page.total_pages == 3
    assert page.has_prev is True
    assert page.has_next is True


@pytest.mark.unit
def test_text_helpers() -> None:
    assert slugify("Hello World!") == "hello-world"
    assert slugify("café latté") == "cafe-latte"
    assert truncate("abcdef", max_length=4) == "abc…"
    assert normalize_email("  Foo@Bar.COM ") == "foo@bar.com"


@pytest.mark.unit
async def test_gather_with_concurrency_limits_parallelism() -> None:
    in_flight = 0
    peak = 0

    async def task() -> int:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return 1

    results = await gather_with_concurrency(2, *(task() for _ in range(10)))
    assert sum(r for r in results if isinstance(r, int)) == 10
    assert peak <= 2


@pytest.mark.unit
async def test_with_timeout_raises() -> None:
    async def slow() -> None:
        await asyncio.sleep(1)

    with pytest.raises(TimeoutError):
        await with_timeout(slow(), seconds=0.05)
