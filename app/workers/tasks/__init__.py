"""Eagerly import task modules so Celery autodiscovery registers them."""

from app.workers.tasks import events_tasks, system_tasks  # noqa: F401
