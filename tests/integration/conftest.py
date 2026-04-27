"""Fixtures for integration tests (real Postgres + Redis in docker-compose.test.yml)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
import redis

from app.core.config import get_settings
from app.core.constants import CELERY_HEARTBEAT_CRON_MINUTES
from app.utils.cron_windows import utc_cron_window_key


@pytest.fixture
def clear_system_heartbeat_lock() -> Iterator[None]:
    """Remove the current window's ``system.heartbeat`` lock; restore after the test."""
    settings = get_settings()
    window = utc_cron_window_key(datetime.now(tz=UTC), step_minutes=CELERY_HEARTBEAT_CRON_MINUTES)
    key = f"{settings.celery_cron_lock_prefix}:system.heartbeat:{window}"
    url = settings.redis_url_test if settings.is_test else settings.redis_url
    client: redis.Redis = redis.Redis.from_url(url, decode_responses=True)
    try:
        client.delete(key)
        yield
    finally:
        client.delete(key)
        client.close()
