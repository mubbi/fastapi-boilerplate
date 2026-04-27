"""Mapping from event name → Celery task name.

Each registered event has a corresponding task in ``app/workers/tasks/`` that
performs the side effect (e.g., send email, refresh denormalized view).
"""

from __future__ import annotations

from app.events.types import DomainEvent

EVENT_TASK_REGISTRY: dict[str, str] = {
    "SystemPingEmitted": "system.handle_ping_emitted",
}


def task_for(event: DomainEvent) -> str | None:
    """Return the Celery task name responsible for processing ``event``."""
    return EVENT_TASK_REGISTRY.get(event.name)
