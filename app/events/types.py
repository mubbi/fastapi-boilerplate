"""Domain event base + sample event.

Domain code adds new events here (or in dedicated submodules per bounded context).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.utils.ids import new_uuid7


class DomainEvent(BaseModel):
    """Base envelope every event inherits from.

    Hard rules:
    - ``frozen=True`` so events are immutable.
    - ``locale`` MUST NOT be added as a field — it is a rendering concern.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    event_id: UUID = Field(default_factory=new_uuid7)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    aggregate_type: str
    aggregate_id: str
    schema_version: int = 1

    @property
    def name(self) -> str:
        """Event name = subclass name."""
        return type(self).__name__

    def payload(self) -> dict[str, Any]:
        """JSON-serializable payload, used by the Celery transport."""
        return self.model_dump(mode="json")


# ── Sample event (boilerplate keeps a tiny, runnable example) ───


class SystemPingEmitted(DomainEvent):
    """Demo event used by the smoke tests."""

    aggregate_type: str = "system"
    note: str = ""
