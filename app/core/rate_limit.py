"""Rate limiting using ``slowapi`` (Redis-backed in production, in-memory for tests).

Routers opt-in via ``@limiter.limit("10/minute")`` decorators.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

if TYPE_CHECKING:
    from app.core.config import Settings


def _key_func(request: Request) -> str:
    """Use authenticated user id when available, otherwise the remote address.

    Per-project auth populates ``request.state.user_id``; the boilerplate
    falls back gracefully when no auth middleware is wired.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


def build_limiter(settings: Settings) -> Limiter:
    """Build a ``Limiter`` configured for the current environment."""
    storage_uri = settings.redis_url_test if settings.is_test else settings.redis_url
    return Limiter(
        key_func=_key_func,
        default_limits=[settings.rate_limit_default],
        storage_uri=str(storage_uri),
        enabled=not settings.is_test,
        headers_enabled=True,
    )


def register_rate_limiter(app: FastAPI, limiter: Limiter) -> None:
    """Attach the limiter + handler to a FastAPI app."""
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    async def _handler(request: Request, exc: Exception) -> JSONResponse:
        from app.core.constants import HEADER_RETRY_AFTER
        from app.core.exceptions import RateLimitedError, domain_error_handler

        if not isinstance(exc, RateLimitExceeded):
            raise exc
        # Delegate to the canonical domain handler so the 429 carries the same
        # translated envelope (request_id, timestamp, Content-Language) as every
        # other error, then layer the Retry-After hint on top.
        response = await domain_error_handler(
            request, RateLimitedError(message="errors.rate_limited")
        )
        retry_after = getattr(exc, "retry_after", None)
        if retry_after:
            response.headers[HEADER_RETRY_AFTER] = str(int(retry_after))
        return response

    app.add_exception_handler(RateLimitExceeded, _handler)
