"""Domain event publisher + registry wiring."""

from __future__ import annotations

import pytest

from app.events.publisher import InMemoryEventPublisher
from app.events.registry import task_for
from app.events.types import SystemPingEmitted
from tests.fakes.events import RecordingEventPublisher


@pytest.mark.unit
def test_event_payload_excludes_locale() -> None:
    """``locale`` is a rendering concern and must never be a field on the event."""
    event = SystemPingEmitted(aggregate_id="sys-1", note="hello")
    payload = event.payload()
    assert "locale" not in payload
    assert payload["aggregate_type"] == "system"
    assert event.name == "SystemPingEmitted"


@pytest.mark.unit
def test_registry_resolves_known_event() -> None:
    event = SystemPingEmitted(aggregate_id="sys-1")
    assert task_for(event) == "system.handle_ping_emitted"


@pytest.mark.unit
async def test_in_memory_publisher_records_event_and_locale() -> None:
    publisher = InMemoryEventPublisher()
    event = SystemPingEmitted(aggregate_id="sys-1")
    await publisher.publish(event, locale="ar")
    assert publisher.events == [(event, "ar")]


@pytest.mark.unit
async def test_recording_publisher_exposes_names() -> None:
    publisher = RecordingEventPublisher()
    await publisher.publish(SystemPingEmitted(aggregate_id="sys-1"))
    assert publisher.names == ["SystemPingEmitted"]
