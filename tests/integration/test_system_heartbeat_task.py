"""Celery ``system.heartbeat`` lock + Redis on the test stack."""

from __future__ import annotations

import pytest

from app.workers.tasks.system_tasks import heartbeat


@pytest.mark.integration
def test_heartbeat_skips_second_invocation_in_same_cron_window(
    clear_system_heartbeat_lock,
) -> None:
    """Redis lock dedupes the same schedule tick (multi-Beat-safe pattern)."""
    first = heartbeat.apply()
    assert first.successful()
    out = first.result
    assert out["skipped"] is False
    window = out["window"]

    second = heartbeat.apply()
    assert second.successful()
    assert second.result["skipped"] is True
    assert second.result["window"] == window
