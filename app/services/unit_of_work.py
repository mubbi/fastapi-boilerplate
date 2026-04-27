"""Service-layer transaction boundaries."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class UnitOfWork:
    """Async UoW. Wrap multi-step writes in ``async with uow: ...``.

    Repositories only flush; services own commit/rollback through this boundary.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UnitOfWork is not active — wrap calls in `async with uow:`")
        return self._session

    async def __aenter__(self) -> UnitOfWork:
        self._session = self._session_factory()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._session is None:
            raise RuntimeError("UnitOfWork exited before it was entered")
        try:
            if exc_type is not None:
                await self._session.rollback()
            else:
                await self._session.commit()
        finally:
            await self._session.close()
            self._session = None


@asynccontextmanager
async def transactional(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Inline transactional scope when a session already exists."""
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
