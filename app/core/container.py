"""Composition root.

Wires every concrete implementation of every Protocol used by the app and exposes
them via FastAPI ``Depends`` factories.

**Hard rule:** the container is the *only* place that instantiates infrastructure
collaborators. Routers / services depend on Protocols and use the ``get_*``
factories below.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request

from app.core.clock import Clock, SystemClock
from app.core.config import Settings, get_settings
from app.core.i18n import BabelTranslator, Translator
from app.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from app.integrations.cache.base import CacheClient
    from app.integrations.email.base import EmailSender
    from app.integrations.http.base import HttpClient

log = get_logger(__name__)


# ── Container dataclass ──────────────────────────────────────────


@dataclass(slots=True)
class Container:
    """Lives on ``app.state.container``; rebuilt per process, never shared across tests."""

    settings: Settings
    clock: Clock
    translator: Translator
    db_engine: AsyncEngine
    db_session_factory: async_sessionmaker[AsyncSession]
    cache: CacheClient
    email: EmailSender
    http: HttpClient

    async def aclose(self) -> None:
        """Dispose long-lived resources in reverse construction order."""
        await self.http.aclose()
        await self.email.aclose()
        await self.cache.aclose()
        await self.db_engine.dispose()


# ── Builder ──────────────────────────────────────────────────────


async def build_container(settings: Settings) -> Container:
    """Construct the live container. Called once at app startup."""
    from app.db.session import build_engine, build_sessionmaker
    from app.integrations.cache import build_cache_client
    from app.integrations.email import build_email_sender
    from app.integrations.http import build_http_client

    clock: Clock = SystemClock()
    translator: Translator = BabelTranslator(settings=settings)
    engine = build_engine(settings)
    session_factory = build_sessionmaker(engine)
    cache = await build_cache_client(settings)
    email = await build_email_sender(settings, translator=translator)
    http = await build_http_client(settings)

    return Container(
        settings=settings,
        clock=clock,
        translator=translator,
        db_engine=engine,
        db_session_factory=session_factory,
        cache=cache,
        email=email,
        http=http,
    )


# ── Dependency factories (FastAPI ``Depends`` targets) ──────────


def get_container(request: Request) -> Container:
    """Return the container attached to the running ``FastAPI`` app."""
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise RuntimeError("Container not initialised — lifespan startup did not run")
    if not isinstance(container, Container):
        raise RuntimeError("Container instance is not a Container — check lifespan setup")
    return container


ContainerDependency = Annotated[Container, Depends(get_container)]


def get_clock(container: ContainerDependency) -> Clock:
    return container.clock


def get_translator(container: ContainerDependency) -> Translator:
    return container.translator


def get_cache(container: ContainerDependency) -> CacheClient:
    return container.cache


def get_email_sender(container: ContainerDependency) -> EmailSender:
    return container.email


def get_http_client(container: ContainerDependency) -> HttpClient:
    return container.http


async def get_db_session(
    container: ContainerDependency,
) -> AsyncIterator[AsyncSession]:
    """Per-request DB session; commits / rollbacks are owned by services via UoW."""
    async with container.db_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# Convenience: settings can come from cache-friendly singleton.
def settings_dependency() -> Settings:
    return get_settings()


__all__ = [
    "Container",
    "build_container",
    "get_cache",
    "get_clock",
    "get_container",
    "get_db_session",
    "get_email_sender",
    "get_http_client",
    "get_translator",
    "settings_dependency",
]
