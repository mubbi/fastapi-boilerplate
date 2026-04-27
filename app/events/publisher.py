"""Event publisher: hands off domain events to Celery for async processing.

Hard rules:
- Always called **after** the UoW commits — never inside.
- ``locale`` is forwarded as a separate Celery kwarg, NOT folded into the payload.
- ``task_id == event.event_id`` so the broker can dedupe at-most-once.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.core.logging import get_logger
from app.events.registry import task_for
from app.events.types import DomainEvent

if TYPE_CHECKING:
    from celery import Celery

log = get_logger(__name__)


class EventPublisher(Protocol):
    """Adapter contract — services depend on this, not on Celery."""

    async def publish(self, event: DomainEvent, *, locale: str | None = None) -> None: ...


class CeleryEventPublisher:
    """Production publisher backed by a Celery app."""

    def __init__(self, celery_app: Celery) -> None:
        self._celery = celery_app

    async def publish(self, event: DomainEvent, *, locale: str | None = None) -> None:
        task_name = task_for(event)
        if not task_name:
            log.warning("event.no_handler", event=event.name)
            return
        try:
            self._celery.send_task(
                task_name,
                kwargs={"event": event.payload(), "locale": locale},
                task_id=str(event.event_id),
            )
            log.info(
                "event.published",
                event=event.name,
                task=task_name,
                aggregate_id=event.aggregate_id,
                locale=locale,
            )
        except Exception as exc:
            log.error("event.publish_failed", event=event.name, error=str(exc))
            raise


class InMemoryEventPublisher:
    """Test publisher; records published events for assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[DomainEvent, str | None]] = []

    async def publish(self, event: DomainEvent, *, locale: str | None = None) -> None:
        self.events.append((event, locale))
