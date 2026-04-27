"""Celery application factory.

Single Celery app per process. Used by:
- ``celery -A app.workers.celery_app worker`` (worker role)
- ``celery -A app.workers.celery_app beat``   (beat role; exactly one replica)

Spec §10.1 / §10.4; rules in ``.cursor/rules/celery-tasks.mdc`` and ``celery-beat.mdc``.
"""

from __future__ import annotations

from celery import Celery
from celery.signals import setup_logging

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger

log = get_logger(__name__)


def _build_celery(settings: Settings) -> Celery:
    """Build the Celery app with broker/backend + sane defaults."""
    app = Celery(
        settings.app_name,
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["app.workers.tasks.events_tasks", "app.workers.tasks.system_tasks"],
    )

    queues = [q.strip() for q in settings.celery_queues.split(",") if q.strip()]
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=settings.celery_task_acks_late,
        task_reject_on_worker_lost=True,
        task_time_limit=settings.celery_task_time_limit,
        task_soft_time_limit=settings.celery_task_soft_time_limit,
        worker_concurrency=settings.celery_worker_concurrency,
        worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
        worker_send_task_events=True,
        worker_max_tasks_per_child=1000,
        broker_connection_retry_on_startup=True,
        result_expires=3600,
        task_default_queue="default",
        task_queues={q: {"exchange": q, "routing_key": q} for q in queues or ["default"]},
        task_always_eager=settings.celery_task_always_eager,
        task_eager_propagates=True,
    )
    return app


settings = get_settings()
celery_app: Celery = _build_celery(settings)


@setup_logging.connect  # type: ignore[untyped-decorator]
def _configure_celery_logging(*_args: object, **_kwargs: object) -> None:
    """Pipe Celery logs through the same structlog configuration."""
    configure_logging(
        level=settings.app_log_level,
        format_=settings.app_log_format,
        app_env=settings.app_env,
        app_version=settings.app_version,
        service=f"{settings.app_name}-celery",
    )


# Wire the periodic schedule lazily so ``beat_schedule.py`` can import the
# ``celery_app`` without circulars.
def install_beat_schedule() -> None:
    from app.workers.beat_schedule import build_beat_schedule

    celery_app.conf.beat_schedule = build_beat_schedule()
    celery_app.conf.beat_scheduler = settings.celery_beat_scheduler


install_beat_schedule()
