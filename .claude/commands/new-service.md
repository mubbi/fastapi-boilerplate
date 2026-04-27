---
description: Scaffold a new feature following the layered architecture (router → service → repository).
---

# /new-service

Add a new feature end-to-end while respecting the layered architecture and DI rules.

## Required inputs (ask the user if missing)

- **Aggregate name** (singular, e.g. `Invoice`).
- **Use cases** to expose (e.g. `create_invoice`, `mark_paid`, `list_invoices`).
- **Endpoints** to expose, if any (default: same as use cases under `/api/v1/<plural>`).
- **External dependencies** (other services, integrations, cache, events, email).

## Plan (do not write code until plan is confirmed)

1. **Domain shape**
   - SQLAlchemy model in `app/models/<aggregate>.py` (mixins for `id`, timestamps; `Mapped[...]`).
   - Pydantic schemas in `app/schemas/<aggregate>.py` (request, response, internal DTO).
2. **Repository**
   - `app/repositories/<aggregate>_repo.py` exposing a `Protocol` + concrete impl.
   - Inherits from `BaseRepository[Model]` for generic CRUD.
3. **Service**
   - `app/services/<aggregate>_service.py` taking repo + cache + events + clock via constructor.
   - Public methods are use-case names (not CRUD verbs).
   - Raises `DomainError` subclasses from `app/core/exceptions.py`. `DomainError.message` is a **gettext key** (e.g. `"errors.invoice.already_paid"`), not English text. Translation happens at the handler boundary.
   - **Never** branches on locale and **never** hardcodes user-visible strings. If a notification is sent, accept `locale` as a method parameter (or read from request context) and forward to `EmailSender.send_template(locale=...)` / `EventPublisher.publish(..., locale=...)`.
4. **DI wiring**
   - `app/core/container.py` adds `get_<aggregate>_repo`, `get_<aggregate>_service` factories using FastAPI `Depends`.
5. **Router (only if endpoints are needed)**
   - `app/api/v1/<plural>.py`, mounted via `app/api/v1/router.py`.
   - Router validates input, calls **one** service method, returns a `response_model`.
6. **Events (if state-changing)**
   - Define `<Aggregate><PastTenseVerb>` event in `app/events/types.py`.
   - Register handler task name in `app/events/registry.py`.
   - Service publishes after UoW commit.
7. **Tests**
   - Factory in `tests/factories/<aggregate>_factory.py`.
   - Seeder helpers in `tests/seeders/` if a scenario is shared.
   - Unit tests for service (with fakes), integration tests for repo, API tests for router.
   - For each user-visible error, add an API test parameterized on `Accept-Language` (`en`, `ar`) asserting on `error.code` (not message).
8. **Migration** for the new model — see `/new-migration`.
9. **OpenAPI** — verify `make openapi` diff is the expected addition only.
10. **i18n catalogs** — for every new `DomainError.message` key and every other user-visible string introduced, run `/new-translation` to update `messages.pot`, translate `en` and `ar` `messages.po`, and compile.

## Hard rules to verify before merge

- Router has **no** repo / integration imports.
- Service has **no** `fastapi.*` imports and never raises `HTTPException`.
- Repository never calls `commit()`.
- Every external dep is constructor-injected.
- Each public service method has a unit test using fakes.
- mypy strict passes; ruff + black pass.

## Linked rules

- `.cursor/rules/architecture-principles.mdc`
- `.cursor/rules/services-layer.mdc`
- `.cursor/rules/repositories-layer.mdc`
- `.cursor/rules/fastapi-routers.mdc`
- `.cursor/rules/dependency-injection.mdc`
- `.cursor/rules/domain-events.mdc`
- `.cursor/rules/test-factories-seeders.mdc`
- `.cursor/rules/i18n-l10n.mdc`
