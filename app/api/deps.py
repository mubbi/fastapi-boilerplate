"""Shared FastAPI dependency factories.

Routers depend on these via ``Annotated[X, Depends(...)]``. All factories must be
overridable in tests via ``app.dependency_overrides``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request

from app.core.container import (
    Container,
    get_cache,
    get_clock,
    get_container,
    get_db_session,
    get_email_sender,
    get_event_publisher,
    get_http_client,
    get_translator,
    settings_dependency,
)
from app.services.system_service import SystemService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.clock import Clock
    from app.core.config import Settings
    from app.core.i18n import Translator
    from app.events.publisher import EventPublisher
    from app.integrations.cache.base import CacheClient
    from app.integrations.email.base import EmailSender
    from app.integrations.http.base import HttpClient


# ── Type aliases used by routers ─────────────────────────────────

SettingsDep = Annotated["Settings", Depends(settings_dependency)]
ContainerDep = Annotated[Container, Depends(get_container)]
ClockDep = Annotated["Clock", Depends(get_clock)]
TranslatorDep = Annotated["Translator", Depends(get_translator)]
CacheDep = Annotated["CacheClient", Depends(get_cache)]
EmailDep = Annotated["EmailSender", Depends(get_email_sender)]
HttpDep = Annotated["HttpClient", Depends(get_http_client)]
EventPublisherDep = Annotated["EventPublisher", Depends(get_event_publisher)]
DbSessionDep = Annotated["AsyncSession", Depends(get_db_session)]


# ── Service factories ────────────────────────────────────────────


def get_system_service(container: ContainerDep) -> SystemService:
    """Service factory for the ``/health`` + ``/ready`` endpoints."""
    return SystemService(
        cache=container.cache,
        session_factory=container.db_session_factory,
        app_version=container.settings.app_version,
        app_env=container.settings.app_env,
    )


SystemServiceDep = Annotated[SystemService, Depends(get_system_service)]


# ── Locale ───────────────────────────────────────────────────────


def get_current_locale(request: Request) -> str:
    """Return the locale set by :class:`LocaleMiddleware`, else the configured default."""
    locale = getattr(request.state, "locale", None)
    if locale:
        return str(locale)
    settings = getattr(request.app.state, "settings", None)
    return getattr(settings, "locale_default", "en")


CurrentLocaleDep = Annotated[str, Depends(get_current_locale)]


# ── Request id ───────────────────────────────────────────────────


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


RequestIdDep = Annotated[str, Depends(get_request_id)]
