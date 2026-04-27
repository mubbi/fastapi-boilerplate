"""System-level scheduled tasks.

Each scheduled task wraps its body in a Redis distributed lock so a redundant
Celery Beat replica cannot trigger duplicate work.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import Any

import redis
from celery import Task

from app.core.config import get_settings
from app.core.constants import CELERY_HEARTBEAT_CRON_MINUTES
from app.core.logging import get_logger
from app.core.metrics import CELERY_CRON_LOCK_SKIPPED_TOTAL
from app.utils.cron_windows import utc_cron_window_key
from app.workers.celery_app import celery_app

log = get_logger(__name__)


def _redis_client() -> redis.Redis:
    settings = get_settings()
    url = settings.redis_url_test if settings.is_test else settings.redis_url
    return redis.Redis.from_url(url, decode_responses=True)


@celery_app.task(
    name="system.heartbeat",
    bind=True,
    acks_late=True,
    max_retries=5,
)
def heartbeat(self: Task[Any, Any]) -> dict[str, Any]:
    """Demonstrates the multi-Beat-safe lock pattern.

    Acquires a per-cron-window key under ``celery_cron_lock_prefix`` for
    ``celery_cron_lock_ttl_seconds``; skips if a peer already ran this window.
    """
    settings = get_settings()
    now = datetime.now(tz=UTC)
    window_key = utc_cron_window_key(now, step_minutes=CELERY_HEARTBEAT_CRON_MINUTES)
    lock_key = f"{settings.celery_cron_lock_prefix}:system.heartbeat:{window_key}"
    client = _redis_client()
    try:
        task_id = str(self.request.id or "")
        acquired = client.set(
            lock_key,
            task_id,
            ex=settings.celery_cron_lock_ttl_seconds,
            nx=True,
        )
        if not acquired:
            CELERY_CRON_LOCK_SKIPPED_TOTAL.labels(task="system.heartbeat").inc()
            log.info(
                "task.heartbeat.skipped_peer_holds_lock",
                task="system.heartbeat",
                window=window_key,
            )
            return {"skipped": True, "window": window_key}

        log.info("task.heartbeat", task_id=self.request.id, window=window_key)
        return {"skipped": False, "task_id": self.request.id, "window": window_key}
    finally:
        with contextlib.suppress(Exception):
            client.close()
