"""Domain events: types, registry, publisher.

Spec §10.2; rules in ``.cursor/rules/domain-events.mdc``.

Hard rules:
- Events are immutable past-tense facts (``UserRegistered``).
- ``locale`` is **not** a field on the event payload — pass it as a separate
  ``EventPublisher.publish(..., locale=...)`` kwarg, which is forwarded to the
  Celery task.
- Events are dispatched **after** the UoW commits, never inside it.
"""
