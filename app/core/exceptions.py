"""Domain exception hierarchy + FastAPI handler registration.

Services raise ``DomainError`` subclasses with a stable ``code`` and a gettext key
as ``message``. The handler in this module translates the message to the
request-resolved locale and emits the canonical error envelope (see
spec §9.1 and ``.cursor/rules/domain-exceptions.mdc``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.constants import HEADER_CONTENT_LANGUAGE, HEADER_REQUEST_ID
from app.core.logging import get_logger

log = get_logger(__name__)


# ── Hierarchy ────────────────────────────────────────────────────


class DomainError(Exception):
    """Base for all domain failures.

    Attributes:
        code: stable, locale-independent SCREAMING_SNAKE_CASE identifier.
        message: English source string AND the gettext translation key.
        details: templating params for the translated message + structured payload.
    """

    default_code: str = "DOMAIN_ERROR"
    default_message: str = "An unexpected error occurred"

    def __init__(
        self,
        *,
        code: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code or self.default_code
        self.message = message or self.default_message
        self.details: dict[str, Any] = details or {}
        super().__init__(self.message)


class NotFoundError(DomainError):
    default_code = "NOT_FOUND"
    default_message = "Resource not found"


class ConflictError(DomainError):
    default_code = "CONFLICT"
    default_message = "Conflicting request"


class ValidationError(DomainError):
    default_code = "VALIDATION_ERROR"
    default_message = "Validation failed"


class UnauthorizedError(DomainError):
    default_code = "UNAUTHORIZED"
    default_message = "Authentication required"


class ForbiddenError(DomainError):
    default_code = "FORBIDDEN"
    default_message = "Permission denied"


class RateLimitedError(DomainError):
    default_code = "RATE_LIMITED"
    default_message = "Too many requests"


class ExternalServiceError(DomainError):
    default_code = "EXTERNAL_SERVICE_ERROR"
    default_message = "Upstream service failure"


class TimeoutError(DomainError):
    default_code = "TIMEOUT"
    default_message = "Operation timed out"


# ── HTTP status mapping ──────────────────────────────────────────

_HTTP_422: int = 422

STATUS_MAP: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    ValidationError: _HTTP_422,
    UnauthorizedError: status.HTTP_401_UNAUTHORIZED,
    ForbiddenError: status.HTTP_403_FORBIDDEN,
    RateLimitedError: status.HTTP_429_TOO_MANY_REQUESTS,
    ExternalServiceError: status.HTTP_502_BAD_GATEWAY,
    TimeoutError: status.HTTP_504_GATEWAY_TIMEOUT,
    DomainError: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def _status_for(err: DomainError) -> int:
    for cls in type(err).__mro__:
        if cls in STATUS_MAP:
            return STATUS_MAP[cls]
    return status.HTTP_500_INTERNAL_SERVER_ERROR


# ── Envelope construction ────────────────────────────────────────


def _build_envelope(
    *,
    code: str,
    message: str,
    details: dict[str, Any],
    request_id: str,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
            "timestamp": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    }


def _request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _locale_of(request: Request) -> str:
    return getattr(request.state, "locale", "en")


def _translator_of(request: Request) -> Any:
    container = getattr(request.app.state, "container", None)
    translator = getattr(container, "translator", None)
    if translator is not None:
        return translator

    from app.core.i18n import get_translator

    return get_translator()


# ── Handlers ─────────────────────────────────────────────────────


async def _domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map ``DomainError`` subclasses to the canonical envelope, with translation."""
    if not isinstance(exc, DomainError):  # defensive
        return await _unhandled_handler(request, exc)

    locale = _locale_of(request)
    translator = _translator_of(request)
    try:
        translated = translator.gettext(exc.message, locale=locale, **exc.details)
    except Exception:
        translated = exc.message

    status_code = _status_for(exc)
    if status_code >= 500:
        log.error(
            "domain_error.server",
            code=exc.code,
            message=exc.message,
            status_code=status_code,
            exc_info=True,
        )
    else:
        log.info(
            "domain_error.client",
            code=exc.code,
            status_code=status_code,
        )

    request_id = _request_id_of(request)
    envelope = _build_envelope(
        code=exc.code,
        message=translated,
        details=exc.details,
        request_id=request_id,
    )
    headers: dict[str, str] = {HEADER_CONTENT_LANGUAGE: locale}
    if request_id:
        headers[HEADER_REQUEST_ID] = request_id
    return JSONResponse(status_code=status_code, content=envelope, headers=headers)


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map Pydantic / FastAPI validation errors to the envelope."""
    if not isinstance(exc, RequestValidationError):
        return await _unhandled_handler(request, exc)

    locale = _locale_of(request)
    translator = _translator_of(request)
    fields = {}
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ()) if part != "body")
        fields[loc or "<root>"] = err.get("msg", "invalid")
    request_id = _request_id_of(request)
    envelope = _build_envelope(
        code="VALIDATION_ERROR",
        message=translator.gettext("Validation failed", locale=locale),
        details={"fields": fields},
        request_id=request_id,
    )
    headers: dict[str, str] = {HEADER_CONTENT_LANGUAGE: locale}
    if request_id:
        headers[HEADER_REQUEST_ID] = request_id
    return JSONResponse(
        status_code=_HTTP_422,
        content=envelope,
        headers=headers,
    )


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Wrap Starlette/FastAPI HTTPException into the standard envelope."""
    if not isinstance(exc, StarletteHTTPException):
        return await _unhandled_handler(request, exc)

    locale = _locale_of(request)
    translator = _translator_of(request)
    detail = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    code = "HTTP_" + str(exc.status_code)
    request_id = _request_id_of(request)
    envelope = _build_envelope(
        code=code,
        message=translator.gettext(detail, locale=locale),
        details={},
        request_id=request_id,
    )
    headers: dict[str, str] = {HEADER_CONTENT_LANGUAGE: locale}
    if request_id:
        headers[HEADER_REQUEST_ID] = request_id
    return JSONResponse(status_code=exc.status_code, content=envelope, headers=headers)


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler — never leak stack traces to clients."""
    log.error("unhandled_exception", error=str(exc), exc_info=True)
    locale = _locale_of(request)
    translator = _translator_of(request)
    request_id = _request_id_of(request)
    envelope = _build_envelope(
        code="INTERNAL_SERVER_ERROR",
        message=translator.gettext("An unexpected error occurred", locale=locale),
        details={},
        request_id=request_id,
    )
    headers: dict[str, str] = {HEADER_CONTENT_LANGUAGE: locale}
    if request_id:
        headers[HEADER_REQUEST_ID] = request_id
    return JSONResponse(status_code=500, content=envelope, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    """Wire all error handlers onto the FastAPI app."""
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
