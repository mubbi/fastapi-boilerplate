"""System-level scheduled tasks.

Each scheduled task wraps its body in a Redis distributed lock so a redundant
Celery Beat replica cannot trigger duplicate work.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import CELERY_CRON_LOCK_SKIPPED_TOTAL
from app.workers.celery_app import celery_app

log = get_logger(__name__)


def _redis_client() -> redis.Redis:
    settings = get_settings()
    url = settings.redis_url_test if settings.is_test else settings.redis_url
    return redis.Redis.from_url(url, decode_responses=True)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="system.heartbeat",
    bind=True,
    acks_late=True,
)
def heartbeat(self: Any) -> dict[str, Any]:
    """Demonstrates the multi-Beat-safe lock pattern.

    Acquires ``cron:lock:system.heartbeat`` for ``celery_cron_lock_ttl_seconds``;
    skips if a peer Beat already triggered the same window.
    """
    settings = get_settings()
    lock_key = f"{settings.celery_cron_lock_prefix}:system.heartbeat"
    client = _redis_client()
    try:
        acquired = client.set(
            lock_key,
            self.request.id,
            ex=settings.celery_cron_lock_ttl_seconds,
            nx=True,
        )
        if not acquired:
            CELERY_CRON_LOCK_SKIPPED_TOTAL.labels(task="system.heartbeat").inc()
            log.info("task.heartbeat.skipped_peer_holds_lock")
            return {"skipped": True}

        log.info("task.heartbeat", task_id=self.request.id)
        return {"skipped": False, "task_id": self.request.id}
    finally:
        with contextlib.suppress(Exception):
            client.close()


def _run_async(coro: Any) -> Any:
    """Run an awaitable inside a Celery task.

    Celery tasks are sync; create a fresh event loop per call so we never
    leak loop state between tasks on the same worker.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
