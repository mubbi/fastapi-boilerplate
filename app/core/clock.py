"""Clock Protocol — inject so time-dependent code is deterministic in tests.

Never call ``datetime.utcnow()`` or ``datetime.now()`` directly in the app.
Use ``Clock.now()`` (UTC).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Clock abstraction. Implementations: ``SystemClock`` (prod), ``FrozenClock`` (tests)."""

    def now(self) -> datetime: ...


class SystemClock:
    """Default clock backed by ``datetime.now(tz=UTC)``."""

    def now(self) -> datetime:
        return datetime.now(tz=UTC)
