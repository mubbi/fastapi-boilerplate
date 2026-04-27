"""Deterministic clock fake."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class FrozenClock:
    """Returns a fixed instant; advance manually with ``tick``."""

    def __init__(self, *, at: datetime | None = None) -> None:
        self._now = at or datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def tick(self, *, seconds: float = 0, minutes: float = 0, hours: float = 0) -> None:
        self._now = self._now + timedelta(seconds=seconds, minutes=minutes, hours=hours)
