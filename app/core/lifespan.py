"""Application lifespan: startup / shutdown hooks for the FastAPI app.

Owns construction + graceful teardown of long-lived resources (DB engine,
Redis client, HTTP client, OTel exporters) and surfaces them through
``app.state`` for dependency injection.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.error_tracking import configure_error_tracking
from app.core.logging import configure_logging, get_logger
from app.core.metrics import reset_multiproc_dir
from app.core.tracing import configure_tracing, instrument_app

if TYPE_CHECKING:
    from app.core.container import Container


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the DI container at startup, dispose it at shutdown."""
    from app.core.container import build_container

    settings = get_settings()
    configure_logging(
        level=settings.app_log_level,
        format_=settings.app_log_format,
        app_env=settings.app_env,
        app_version=settings.app_version,
        service=settings.app_name,
    )
    log = get_logger(__name__)
    reset_multiproc_dir()
    configure_error_tracking(settings)
    configure_tracing(settings)

    container: Container = await build_container(settings)
    app.state.settings = settings
    app.state.container = container

    instrument_app(app)

    log.info(
        "app.startup.complete",
        env=settings.app_env,
        service_role=settings.service_role,
        version=settings.app_version,
    )

    try:
        yield
    finally:
        log.info("app.shutdown.start")
        try:
            await asyncio.wait_for(
                container.aclose(), timeout=settings.app_graceful_shutdown_seconds
            )
        except TimeoutError:
            log.warning("app.shutdown.timeout")
        log.info("app.shutdown.complete")
