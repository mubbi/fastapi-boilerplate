"""Application factory.

Single source of truth for the FastAPI app. Used by:
- ``uvicorn app.main:app`` for local dev
- ``gunicorn`` (production) via the docker entrypoint
- ``tests/conftest.py`` for in-process API tests
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.system import router as system_router
from app.api.v1.router import api_router as v1_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.middleware import register_middlewares
from app.core.rate_limit import build_limiter, register_rate_limiter


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the FastAPI app."""
    cfg = settings or get_settings()

    app = FastAPI(
        title=cfg.app_name,
        version=cfg.app_version,
        debug=cfg.app_debug,
        docs_url="/docs" if cfg.app_docs_enabled else None,
        redoc_url="/redoc" if cfg.app_docs_enabled else None,
        openapi_url="/openapi.json" if cfg.app_docs_enabled else None,
        lifespan=lifespan,
    )

    register_middlewares(app, settings=cfg)
    register_exception_handlers(app)

    limiter = build_limiter(cfg)
    register_rate_limiter(app, limiter)

    app.include_router(system_router)
    app.include_router(v1_router, prefix=cfg.app_api_v1_prefix)

    return app


app = create_app()
