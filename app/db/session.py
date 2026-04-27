"""Async SQLAlchemy engine + sessionmaker factories.

Spec §6.1; rules in ``.cursor/rules/sqlalchemy-async.mdc``.

The composition root (``app/core/container.py``) constructs exactly one engine
per process and reuses the sessionmaker for every request.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def build_engine(settings: Settings) -> AsyncEngine:
    """Build the application's async engine.

    Notes:
        - ``pool_pre_ping=True`` recovers from severed connections (Cloud reapers, NAT idle).
        - ``pool_recycle`` rotates connections before the server side closes them.
        - ``connect_args`` apply asyncpg-specific timeouts and a server settings hook
          (statement_timeout) so runaway queries cannot wedge a worker.
    """
    return create_async_engine(
        settings.database_url,
        echo=settings.database.echo,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_recycle=settings.database.pool_recycle_seconds,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                "application_name": settings.app_name,
                "statement_timeout": str(settings.database.statement_timeout_ms),
            },
            "command_timeout": settings.database.statement_timeout_ms / 1000.0,
        },
    )


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build the per-process sessionmaker.

    ``expire_on_commit=False`` lets services hand entities back to routers without
    triggering refresh queries on detached objects.
    """
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
