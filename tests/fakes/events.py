"""Fake event publisher: records what would have been published."""

from __future__ import annotations

from app.events.types import DomainEvent


class RecordingEventPublisher:
    """Captures published events for assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[DomainEvent, str | None]] = []

    async def publish(self, event: DomainEvent, *, locale: str | None = None) -> None:
        self.events.append((event, locale))

    @property
    def names(self) -> list[str]:
        return [e.name for e, _ in self.events]
