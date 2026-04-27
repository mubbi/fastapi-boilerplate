"""Tasks that handle published domain events.

Hard rules:
- Primitive args only — never ORM objects.
- Idempotent — replays must converge to the same final state.
- ``locale`` is **always** a separate kwarg (never embedded in the event).
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

log = get_logger(__name__)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="system.handle_ping_emitted",
    bind=True,
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def handle_ping_emitted(
    self: Any,
    *,
    event: dict[str, Any],
    locale: str | None = None,
) -> dict[str, Any]:
    """Demo handler: log the event and return a status dict."""
    log.info(
        "task.handle_ping_emitted",
        task_id=self.request.id,
        attempt=self.request.retries,
        event_id=event.get("event_id"),
        locale=locale,
    )
    return {"processed": True, "event_id": event.get("event_id"), "locale": locale}
