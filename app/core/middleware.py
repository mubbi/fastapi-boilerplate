"""Cross-cutting middleware: request ID, locale resolution, security headers, timing.

Order matters — apply them via ``register_middlewares`` so the chain is consistent
between dev, test, and prod.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.config import Settings
from app.core.constants import (
    HEADER_API_VERSION,
    HEADER_CONTENT_LANGUAGE,
    HEADER_REQUEST_ID,
)
from app.core.i18n import resolve_locale
from app.core.logging import get_logger
from app.core.metrics import (
    HTTP_IN_FLIGHT,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
)
from app.utils.ids import new_uuid7_hex

log = get_logger(__name__)

CallNext = Callable[[Request], Awaitable[Response]]


# ── RequestContextMiddleware ─────────────────────────────────────


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Generate / propagate ``X-Request-ID`` and bind structlog contextvars.

    Locale is resolved by ``LocaleMiddleware`` first; this middleware re-binds
    ``locale`` to contextvars after that resolution.
    """

    def __init__(self, app: FastAPI, *, app_version: str) -> None:
        super().__init__(app)
        self._app_version = app_version

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        request_id = request.headers.get(HEADER_REQUEST_ID) or new_uuid7_hex()
        request.state.request_id = request_id

        clear_contextvars()
        bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            locale=getattr(request.state, "locale", None),
        )
        start = time.perf_counter()
        HTTP_IN_FLIGHT.inc()
        try:
            response = await call_next(request)
            route = getattr(request.scope.get("route"), "path", request.url.path)
            status_class = f"{response.status_code // 100}xx"
            duration_seconds = time.perf_counter() - start
            log.info(
                "http.request",
                route=route,
                status_code=response.status_code,
                status_class=status_class,
                duration_ms=round(duration_seconds * 1000.0, 2),
            )
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                route=route,
                status_class=status_class,
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=request.method,
                route=route,
            ).observe(duration_seconds)
        finally:
            HTTP_IN_FLIGHT.dec()
            clear_contextvars()
        response.headers[HEADER_REQUEST_ID] = request_id
        response.headers[HEADER_API_VERSION] = self._app_version
        return response


# ── LocaleMiddleware ─────────────────────────────────────────────


class LocaleMiddleware(BaseHTTPMiddleware):
    """Resolve the request locale and stamp ``Content-Language`` on every response.

    Priority: query param → authenticated user pref → ``Accept-Language`` → default.
    """

    def __init__(self, app: FastAPI, *, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        query_value: str | None = None
        if self._settings.locale_query_param:
            query_value = request.query_params.get(self._settings.locale_query_param)

        # User preference is a per-project hook; the boilerplate ships only the slot.
        user_pref: str | None = getattr(request.state, "user_locale_pref", None)
        accept_language = request.headers.get(self._settings.locale_header_name)

        locale = resolve_locale(
            query_value=query_value,
            user_pref=user_pref,
            accept_language=accept_language,
            settings=self._settings,
        )
        request.state.locale = locale
        # Re-bind contextvar in case RequestContextMiddleware ran first.
        bind_contextvars(locale=locale)

        response = await call_next(request)
        response.headers[HEADER_CONTENT_LANGUAGE] = locale
        return response


# ── SecurityHeadersMiddleware ────────────────────────────────────


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Set defensible security headers on every response."""

    def __init__(self, app: FastAPI, *, is_production: bool) -> None:
        super().__init__(app)
        self._is_production = is_production

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "()")
        if request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data: https:; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
            )
        if self._is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


# ── Registration ─────────────────────────────────────────────────


def register_middlewares(app: FastAPI, *, settings: Settings) -> None:
    """Wire the middleware stack in the right order.

    Starlette runs middlewares in REVERSE add-order, so the last ``add_middleware``
    call is the **outermost** layer. We add inside-out:
      RequestContext (outermost; wraps everything in correlation/log timing)
      ↓
      Security headers
      ↓
      Locale (sets ``request.state.locale`` before handlers / errors)
      ↓
      CORS (must wrap the actual app for proper preflight handling)
      ↓
      TrustedHost (innermost — first to inspect Host header)
    """
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.app_trusted_hosts,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app_cors_origins,
        allow_credentials=settings.app_cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            HEADER_REQUEST_ID,
            HEADER_API_VERSION,
            HEADER_CONTENT_LANGUAGE,
        ],
    )
    app.add_middleware(LocaleMiddleware, settings=settings)  # type: ignore[arg-type]
    app.add_middleware(
        SecurityHeadersMiddleware,  # type: ignore[arg-type]
        is_production=settings.is_production,
    )
    app.add_middleware(
        RequestContextMiddleware,  # type: ignore[arg-type]
        app_version=settings.app_version,
    )
