---
description: Audit a change set against the layered architecture, DI, and Pydantic/SQLAlchemy hard rules.
---

# /check-architecture

Run a structured review against the project's hard rules before opening a PR. Report violations as a checklist with file:line references.

> This is the **lightweight pre-flight checklist** — useful for a quick self-check while you're still iterating. For a **full review**, run **`/review-code`** (delegates to the `code-reviewer` subagent with the complete rubric in `.cursor/rules/code-review.mdc`) and **`/review-security`** (delegates to `security-reviewer` with `.cursor/rules/security-review.mdc`). Use this command for fast triage; use the `/review-*` commands for the gating, citation-backed review.

## Checklist (mirrors `CLAUDE.md` §2)

### Layer boundaries
- [ ] No `app/api/**` file imports `app.repositories.*` or `app.integrations.*`.
- [ ] No `app/services/**` file imports `fastapi.*`, `Request`, `Response`, or raises `HTTPException`.
- [ ] No `app/repositories/**` file calls `.commit()` or imports another repository.
- [ ] No `app/integrations/**` file imports services or repositories.

### Dependency Injection
- [ ] Every external collaborator is a `Protocol` injected via constructor or FastAPI `Depends`.
- [ ] No `from app.X import some_singleton_instance` outside the composition root.
- [ ] Every injected dep has an override-friendly factory in `app/core/container.py` or `app/api/deps.py`.

### Async + typing
- [ ] No `import requests`, `time.sleep` (use `asyncio.sleep`), `psycopg2`, or sync `sqlalchemy.create_engine` on the request path.
- [ ] All public functions and class methods are typed; no `Any` without justification.
- [ ] Modern syntax: `X | None`, `list[X]`, `Annotated[...]`. No `Optional`, no `List`/`Dict` from `typing`.

### Pydantic v2
- [ ] Request/response schemas set `model_config = ConfigDict(extra="forbid")`.
- [ ] No `BaseSettings` outside `app/core/config.py`; secrets use `SecretStr`.
- [ ] No `from_attributes=True` on request DTOs (only on response when reading ORM objects).

### SQLAlchemy 2.0+
- [ ] Models use `Mapped[...]` + `mapped_column(...)`.
- [ ] Sessions are async (`AsyncSession`, `async_sessionmaker`).
- [ ] Naming convention applied on `MetaData`.
- [ ] No raw `Session.query(...)`; use `select(...)` with `await session.execute(...)`.

### Domain exceptions
- [ ] Services raise `DomainError` subclasses, never `HTTPException`.
- [ ] Routers do not catch and re-raise as `HTTPException` (handler maps automatically).

### Tests
- [ ] New tests use factories from `tests/factories/`; no inline literal DB rows.
- [ ] Integration tests use the test DB; `conftest.py` guardrail untouched.
- [ ] No `if APP_ENV == "test":` in `app/`.

### Celery
- [ ] Tasks declared with `acks_late=True`, `max_retries=...`, primitive args only.
- [ ] Scheduled tasks wrap their body in a Redis distributed lock.
- [ ] Beat schedule changes are reviewed in PR; Beat replica count remains 1.

### Migrations
- [ ] One migration per model change; backward-compatible.
- [ ] Naming convention preserved.

### Config / env
- [ ] New env vars added to `.env.example` (and `.env.test` if relevant).
- [ ] No secrets logged; redactor processor unchanged.

### Observability
- [ ] New significant operations have a Prometheus metric and an OTel span.
- [ ] Structured logs include `request_id` (HTTP) or `task_id` (Celery), and `locale` on the request path.

### i18n / l10n
- [ ] No hardcoded user-visible strings. Every string returned to a user is wrapped with `_(...)` / `Translator.gettext`.
- [ ] No `if locale == "ar":` (or any locale) branches in `app/services/**`, `app/repositories/**`, or `app/integrations/**`.
- [ ] No raw `Accept-Language` parsing outside `get_current_locale` in `app/api/deps.py`.
- [ ] Domain events in `app/events/types.py` do **not** carry a `locale` field; `EventPublisher.publish` accepts `locale` as a separate kwarg.
- [ ] `EmailSender.send_template` is called with an explicit `locale=` argument; matching templates exist in `app/templates/email/<id>/{en,ar}/`.
- [ ] New user-visible strings are present in `app/locales/messages.pot` and have non-fuzzy translations in `app/locales/{en,ar}/LC_MESSAGES/messages.po`.
- [ ] `make i18n-check` passes (catalog drift + completeness threshold).
- [ ] No assertions on translated copy in tests — tests assert `error.code` or structured fields.

## Output format

For each violation found:

```
- [VIOLATION] <rule short name> — <file:line>
  Why: <one-sentence explanation>
  Fix: <concrete action>
```

If everything passes, reply: `Architecture audit: clean.`

## When this is enough — and when it isn't

- ✅ **Use `/check-architecture` for**: quick self-check while iterating, "does this look broadly OK?" on a small change.
- ❌ **Do NOT rely on it for merge gating.** Use `/review-code` and `/review-security` before opening a PR — they have the full rubric, severity ladder, and explicit `APPROVE / REQUEST CHANGES / BLOCK` verdicts that the merge process keys off of.
