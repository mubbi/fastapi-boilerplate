"""Top-level pytest configuration.

Hard rules enforced here:
- Tests NEVER touch the dev database. We assert that the resolved DB URL
  matches a test marker (``_test`` or ``localhost`` host with a ``_test`` db).
- Any FastAPI dependency may be overridden via ``app.dependency_overrides``;
  fixtures below construct a test-friendly container.
"""

from __future__ import annotations

import os
import warnings
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Force test env BEFORE importing app modules.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("EMAIL_ENABLED", "false")
os.environ.setdefault("EMAIL_PROVIDER", "null")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://app_test:app_test@localhost:55432/app_test"
)
os.environ.setdefault(
    "DATABASE_URL_TEST", "postgresql+asyncpg://app_test:app_test@localhost:55432/app_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:56379/0")
os.environ.setdefault("REDIS_URL_TEST", "redis://localhost:56379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:56379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:56379/2")
os.environ.setdefault("CELERY_BROKER_URL_TEST", "redis://localhost:56379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND_TEST", "redis://localhost:56379/2")
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "")

from app.core.config import get_settings
from app.core.container import Container

# ── Guardrail: never let tests reach a non-test database ────────


def _assert_test_database(url: str) -> None:
    """Halt the suite if the resolved DB URL doesn't look like a test DB."""
    lowered = url.lower()
    safe = (
        "_test" in lowered
        or "localhost:55432" in lowered
        or "127.0.0.1:55432" in lowered
        or "postgres_test" in lowered
    )
    if not safe:
        raise RuntimeError(
            f"Refusing to run tests against suspicious DATABASE_URL='{url}'. "
            "Tests must target the isolated test stack only."
        )


@pytest.fixture(scope="session", autouse=True)
def _enforce_test_db() -> None:
    settings = get_settings()
    _assert_test_database(settings.database_url_test)
    _assert_test_database(settings.database_url)


@pytest.fixture(scope="session")
def settings():
    """Cached test settings."""
    get_settings.cache_clear()
    return get_settings()


# ── Test container with in-memory adapters ─────────────────────


@pytest.fixture
async def container(settings) -> AsyncIterator[Container]:
    """Build a container with deterministic, in-memory adapters.

    Cache uses :class:`InMemoryCache`; email uses :class:`NullEmailSender`;
    HTTP uses ``respx``-friendly httpx; DB uses the isolated test database.
    """
    from app.core.clock import SystemClock
    from app.core.i18n import BabelTranslator
    from app.db.session import build_engine, build_sessionmaker
    from app.integrations.cache.in_memory import InMemoryCache
    from app.integrations.email import build_email_sender
    from app.integrations.http import build_http_client
    from tests.fakes.events import RecordingEventPublisher

    translator = BabelTranslator(settings=settings)
    cache = InMemoryCache()
    email = await build_email_sender(settings, translator=translator)
    http = await build_http_client(settings)
    engine = build_engine(settings)
    session_factory = build_sessionmaker(engine)

    c = Container(
        settings=settings,
        clock=SystemClock(),
        translator=translator,
        db_engine=engine,
        db_session_factory=session_factory,
        cache=cache,
        email=email,
        http=http,
        events=RecordingEventPublisher(),
    )
    try:
        yield c
    finally:
        await c.aclose()


# ── FastAPI test client with overridden dependencies ───────────


@pytest.fixture
async def app(container: Container) -> AsyncIterator[FastAPI]:
    """Construct the FastAPI app and inject the in-memory container."""
    from app.core.container import get_container
    from app.main import create_app

    fast_app = create_app()
    fast_app.state.container = container
    fast_app.state.settings = container.settings

    fast_app.dependency_overrides[get_container] = lambda: container
    try:
        yield fast_app
    finally:
        fast_app.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Async HTTP client bound to the in-process app — no network."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _silence_warnings() -> Iterator[None]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield
