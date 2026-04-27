---
description: Add a domain event that services publish and Celery listeners consume.
---

# /new-event

Domain events are **facts that already happened** (past tense) emitted by services after the Unit of Work commits, dispatched into Celery for handling.

## Plan

1. **Define the event** in `app/events/types.py`:
   - Frozen dataclass or Pydantic model (immutable).
   - Required fields: `event_id` (UUID), `occurred_at` (UTC), `aggregate_type`, `aggregate_id`, `schema_version`.
   - Domain payload as additional typed fields.
   - Name: `<Aggregate><PastTenseVerb>` — e.g. `UserRegistered`, `InvoicePaid`. Never imperative.
   - **Never** include a `locale` field (or any rendering / presentation data). Events are facts; locale is a rendering concern (see `i18n-l10n.mdc`).
2. **Register routing** in `app/events/registry.py`:
   - Map the event type → Celery task name (e.g. `events.user_registered`).
   - Optionally: routing key / queue for dedicated workers.
3. **Publish from the service** — only after UoW commit:
   ```python
   # pseudo-code
   await self._uow.commit()
   await self._events.publish(UserRegistered(...), locale=current_locale)
   ```
   Never publish before commit; never publish from inside a `with session.begin()` block.
   `EventPublisher.publish` forwards `locale` to the Celery task as a **separate kwarg** — it is not stored on the event.
4. **Add listeners** in `app/workers/tasks/events_tasks.py` (or a domain-specific module). Naming: `on_<aggregate>_<verb>_<action>`, e.g. `on_user_registered_send_welcome_email`. Listener signature:
   ```python
   @celery_app.task(...)
   def on_user_registered_send_welcome_email(event_data: dict, *, locale: str = "en") -> None: ...
   ```
5. **Idempotency**:
   - Use `event_id` as Celery `task_id` to dedupe at the broker level (same `task_id` → no re-enqueue if not yet executed).
   - Add a unique constraint on `(event_id, handler_name)` in a `processed_events` table for at-most-once handler semantics, or `SETNX` on Redis with TTL.
6. **Tests**:
   - Unit: service test asserts publisher was called with the right event after a successful operation, **not** when the operation rolls back.
   - Integration: end-to-end test enqueues the event with `CELERY_TASK_ALWAYS_EAGER=true` and asserts the listener's side effect (e.g. email sent to MailHog).

## Anti-patterns

- ❌ Publishing **commands** ("send_welcome_email") instead of facts ("UserRegistered").
- ❌ Listeners reaching across aggregates by importing other services' private methods.
- ❌ Mutable event payloads.
- ❌ Publishing inside a transaction block — listener runs and discovers rolled-back state.
- ❌ Storing `locale` (or any rendering data: `display_name`, `currency_symbol`, etc.) on the event payload.
- ❌ Hardcoding strings inside listeners — listeners that send notifications use `Translator` + the `locale` kwarg.

## Linked rules

- `.cursor/rules/domain-events.mdc`
- `.cursor/rules/celery-tasks.mdc`
- `.cursor/rules/services-layer.mdc`
- `.cursor/rules/i18n-l10n.mdc`
