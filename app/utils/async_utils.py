"""Reusable async building blocks.

Rules:
- Never block the event loop (no ``time.sleep``, no sync HTTP, no sync DB).
- Always honour cancellation — re-raise ``asyncio.CancelledError``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


async def gather_with_concurrency(
    limit: int,
    *coros: Awaitable[T],
    return_exceptions: bool = False,
) -> Sequence[T | BaseException]:
    """Like :func:`asyncio.gather` but caps concurrency at ``limit``.

    Useful for fan-out work where the downstream has a connection / RPS budget.
    """
    if limit <= 0:
        raise ValueError("limit must be > 0")
    semaphore = asyncio.Semaphore(limit)

    async def _bound(c: Awaitable[T]) -> T:
        async with semaphore:
            return await c

    return await asyncio.gather(
        *(_bound(c) for c in coros),
        return_exceptions=return_exceptions,
    )


async def with_timeout(coro: Awaitable[T], *, seconds: float) -> T:
    """Wrap ``coro`` with a hard timeout. Raises :class:`TimeoutError` on expiry."""
    return await asyncio.wait_for(coro, timeout=seconds)


async def call_in_thread(func: Callable[..., T], /, *args: object, **kwargs: object) -> T:
    """Run a sync ``func`` on the default thread pool — keeps the event loop free."""
    return await asyncio.to_thread(func, *args, **kwargs)
