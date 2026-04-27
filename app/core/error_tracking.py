"""Sentry error tracking configuration."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)


def configure_error_tracking(settings: Settings) -> None:
    """Configure Sentry when ``SENTRY_DSN`` is provided."""
    if not settings.sentry_dsn:
        log.info("sentry.disabled", reason="SENTRY_DSN not set")
        return

    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.types import Event

    def _before_send(event: Event, hint: dict[str, Any]) -> Event | None:
        request = event.get("request")
        if isinstance(request, dict):
            request.pop("data", None)
            request.pop("cookies", None)
            request.pop("headers", None)
        return event

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.app_version,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[CeleryIntegration()],
        before_send=_before_send,
        send_default_pii=False,
    )
    log.info("sentry.configured")
