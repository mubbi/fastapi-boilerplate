"""System service: liveness + readiness composition.

Spec §13.4: ``/health`` is liveness only (process up); ``/ready`` aggregates the
health of every required dependency (DB, cache) with a short cache TTL to
prevent dependency stampede during high-frequency probes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from app.core.constants import (
    READY_CHECK_CACHE_TTL_SECONDS,
    READY_CHECK_TIMEOUT_SECONDS,
)
from app.core.logging import get_logger
from app.utils.async_utils import with_timeout

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.integrations.cache.base import CacheClient

log = get_logger(__name__)


# ── Result types ─────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    healthy: bool
    duration_ms: float
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    ready: bool
    checks: tuple[CheckResult, ...] = field(default_factory=tuple)


# ── Service ──────────────────────────────────────────────────────


class SystemService:
    """Composes liveness + readiness."""

    # Readiness is cached process-wide (not per instance): a fresh SystemService is
    # built per request, so an instance-scoped cache would never hit. Sharing it on
    # the class lets the short TTL absorb high-frequency probe traffic (spec §13.4).
    _readiness_cache: ClassVar[tuple[float, ReadinessReport] | None] = None

    def __init__(
        self,
        *,
        cache: CacheClient,
        session_factory: async_sessionmaker[AsyncSession],
        app_version: str,
        app_env: str,
    ) -> None:
        self._cache = cache
        self._session_factory = session_factory
        self._app_version = app_version
        self._app_env = app_env

    def health(self) -> dict[str, str]:
        """Process-up signal — must NEVER touch a dependency."""
        return {
            "status": "ok",
            "version": self._app_version,
            "env": self._app_env,
        }

    async def readiness(self) -> ReadinessReport:
        """Aggregate dependency health.

        Cached briefly to absorb high-frequency Kubernetes / Render probe traffic.
        """
        now = time.monotonic()
        cached = SystemService._readiness_cache
        if cached and (now - cached[0]) < READY_CHECK_CACHE_TTL_SECONDS:
            return cached[1]

        db = await self._check_db()
        redis = await self._check_redis()
        ready = db.healthy and redis.healthy
        report = ReadinessReport(ready=ready, checks=(db, redis))
        SystemService._readiness_cache = (now, report)
        if not ready:
            log.warning("ready.unhealthy", db=db.healthy, redis=redis.healthy)
        return report

    async def _check_db(self) -> CheckResult:
        from sqlalchemy import text

        start = time.perf_counter()
        try:

            async def _probe() -> None:
                async with self._session_factory() as session:
                    await session.execute(text("SELECT 1"))

            await with_timeout(_probe(), seconds=READY_CHECK_TIMEOUT_SECONDS)
            return CheckResult(
                name="postgres",
                healthy=True,
                duration_ms=round((time.perf_counter() - start) * 1000.0, 2),
            )
        except Exception as exc:
            return CheckResult(
                name="postgres",
                healthy=False,
                duration_ms=round((time.perf_counter() - start) * 1000.0, 2),
                error=type(exc).__name__,
            )

    async def _check_redis(self) -> CheckResult:
        start = time.perf_counter()
        try:
            ok = await with_timeout(self._cache.ping(), seconds=READY_CHECK_TIMEOUT_SECONDS)
            return CheckResult(
                name="redis",
                healthy=bool(ok),
                duration_ms=round((time.perf_counter() - start) * 1000.0, 2),
            )
        except Exception as exc:
            return CheckResult(
                name="redis",
                healthy=False,
                duration_ms=round((time.perf_counter() - start) * 1000.0, 2),
                error=type(exc).__name__,
            )
