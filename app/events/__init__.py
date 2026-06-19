"""Domain events: types, registry, publisher.

Spec §10.2; rules in ``.cursor/rules/domain-events.mdc``.

Hard rules:
- Events are immutable past-tense facts (``UserRegistered``).
- ``locale`` is **not** a field on the event payload — pass it as a separate
  ``EventPublisher.publish(..., locale=...)`` kwarg, which is forwarded to the
  Celery task.
- Events are dispatched **after** the UoW commits, never inside it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.events.publisher import (
    CeleryEventPublisher,
    EventPublisher,
    InMemoryEventPublisher,
)

if TYPE_CHECKING:
    from app.core.config import Settings

log = get_logger(__name__)


def build_event_publisher(settings: Settings) -> EventPublisher:
    """Build the production event publisher (Celery transport).

    Tests inject :class:`InMemoryEventPublisher` via the container fixture instead.
    """
    from app.workers.celery_app import celery_app

    log.info("events.publisher", adapter="celery", env=settings.app_env)
    return CeleryEventPublisher(celery_app)


__all__ = [
    "CeleryEventPublisher",
    "EventPublisher",
    "InMemoryEventPublisher",
    "build_event_publisher",
]
