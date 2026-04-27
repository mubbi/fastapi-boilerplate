---
description: Add a Celery task (one-off or scheduled) that is idempotent and Beat-singleton safe.
---

# /new-celery-task

Author a Celery task that follows the project's reliability + scheduling rules.

## Decide first

- **One-off (queued by services / API):** declare under `app/workers/tasks/<context>_tasks.py`.
- **Scheduled (cron):** declare the task **and** add to `app/workers/beat_schedule.py` **and** wrap the task body in a Redis lock.
- **Listener for a domain event:** register the task name in `app/events/registry.py` and have the body call a service method.

## Required hygiene

- Task name: `@celery_app.task(name="context.action", acks_late=True, max_retries=5)`.
- **Primitive arguments only** — pass IDs, fetch state inside the task. ORM objects in args = reject.
- **Idempotent body.** Re-running with the same args must yield the same state.
- Constructs the service via the **same DI container** as the API (`get_*_service`); does not duplicate wiring.
- Logs start/finish with `task_id`, sanitized args, `locale` (if user-facing), and duration.
- On retryable failure: `autoretry_for=(SpecificError,)`, `retry_backoff=True`, `retry_backoff_max`, `retry_jitter=True`.
- On permanent failure: route to DLQ (`task_routes` / `routing_key`) and emit a metric.
- **Locale-bearing tasks** (anything that sends user-visible notifications: emails, SMS, push, in-app messages) accept `locale: str = "en"` as an explicit kwarg — **not** as a field embedded in another payload. The `task_prerun` hook binds it to structlog contextvars so all task logs carry it. See `.cursor/rules/i18n-l10n.mdc`.
- **No hardcoded user-visible strings inside tasks.** Use `Translator.gettext(..., locale=locale)` and `EmailSender.send_template(..., locale=locale)`.

## Scheduled-task extras (Beat singleton + multi-server agnostic)

Even though only **one** Beat replica runs in production, every scheduled task body must:

1. Compute a window key (e.g. `floor(now / interval)`).
2. `SET {CELERY_CRON_LOCK_PREFIX}:<task_name>:<window> NX EX <CELERY_CRON_LOCK_TTL_SECONDS>`.
3. If lock not acquired → log `cron.skipped` at INFO and return.
4. If acquired → run the body; lock auto-expires.

This guarantees:
- Two Beat processes (misconfig) won't double-run.
- A long-running task won't overlap with the next tick.

## Plan before code

1. File: `app/workers/tasks/<context>_tasks.py`.
2. Test: `tests/integration/test_<context>_tasks.py` — runs with `CELERY_TASK_ALWAYS_EAGER=true` and asserts side effects + idempotency by running twice.
3. If scheduled: add to `app/workers/beat_schedule.py` with a clear `name`, `task`, `schedule`, and any `options`.
4. Sentry capture is automatic for failed tasks; verify by injecting a controlled failure in a manual test.

## Linked rules

- `.cursor/rules/celery-tasks.mdc`
- `.cursor/rules/celery-beat.mdc`
- `.cursor/rules/domain-events.mdc`
- `.cursor/rules/cache-redis.mdc`
- `.cursor/rules/i18n-l10n.mdc`
