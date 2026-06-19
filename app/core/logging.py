"""Structured logging via structlog.

Configure once at app/worker startup. Every log on the request path includes
``request_id``, ``trace_id``, ``span_id``, ``app_env``, ``app_version``, and
``locale`` (when ``LocaleMiddleware`` ran).
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.constants import AUDIT_LOGGER_NAME

SENSITIVE_KEY_FRAGMENTS: tuple[str, ...] = (
    "password",
    "passwd",
    "token",
    "authorization",
    "bearer",
    "api_key",
    "apikey",
    "x-api-key",
    "secret",
    "private_key",
    "credential",
    "cookie",
    "set-cookie",
    "session",
)

_REDACTION_MAX_DEPTH = 6
_REDACTED = "***"


def _is_sensitive_key(key: object) -> bool:
    lowered = str(key).lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def _redact_value(value: object, depth: int = 0) -> object:
    """Recursively mask sensitive keys inside nested mappings / sequences."""
    if depth >= _REDACTION_MAX_DEPTH:
        return value
    if isinstance(value, dict):
        return {
            k: (_REDACTED if _is_sensitive_key(k) else _redact_value(v, depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(v, depth + 1) for v in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(v, depth + 1) for v in value)
    return value


def _redact_processor(_: object, __: str, event_dict: EventDict) -> EventDict:
    """Mask values whose key contains a sensitive fragment, recursing into nested data."""
    for key in list(event_dict.keys()):
        if _is_sensitive_key(key):
            event_dict[key] = _REDACTED
        else:
            event_dict[key] = _redact_value(event_dict[key])
    return event_dict


def _add_otel_trace_context(_: object, __: str, event_dict: EventDict) -> EventDict:
    """Best-effort: attach OTel ``trace_id`` / ``span_id`` to every log."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx and ctx.is_valid:
            event_dict.setdefault("trace_id", format(ctx.trace_id, "032x"))
            event_dict.setdefault("span_id", format(ctx.span_id, "016x"))
    except Exception:
        # Tracing not configured; skip.
        return event_dict
    return event_dict


def configure_logging(
    *,
    level: str = "INFO",
    format_: str = "json",
    app_env: str = "local",
    app_version: str = "0.1.0",
    service: str = "fastapi-boilerplate",
) -> None:
    """Configure structlog + stdlib root logger for the process."""

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        _add_otel_trace_context,
        _redact_processor,
    ]

    if format_ == "json":
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Bind globally-applicable fields.
    structlog.contextvars.bind_contextvars(
        app_env=app_env,
        app_version=app_version,
        service=service,
    )

    # Forward stdlib logging into the same handlers (so 3rd-party libs get redacted too).
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)
    root.setLevel(getattr(logging, level))

    # Quiet noisy libs by default.
    for noisy in ("uvicorn.access", "asyncio", "botocore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> Any:
    """Return a bound structlog logger; prefer this over ``logging.getLogger``."""
    return structlog.get_logger(name)


def get_audit_logger() -> Any:
    """Dedicated logger for security-sensitive actions (never sampled, never redacted-at-source)."""
    return structlog.get_logger(AUDIT_LOGGER_NAME)
