"""Periodic schedule definition.

Each entry must wrap its body with a Redis distributed lock
(see :mod:`app.workers.tasks.system_tasks`) so a redundant Beat replica
cannot trigger duplicate work.
"""

from __future__ import annotations

from celery.schedules import crontab


def build_beat_schedule() -> dict[str, dict[str, object]]:
    """Return the ``beat_schedule`` dict consumed by Celery."""
    return {
        # Heartbeat lock-protected; demonstrates the multi-Beat-safe pattern.
        "system.heartbeat": {
            "task": "system.heartbeat",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "default"},
        },
    }
