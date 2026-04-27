# CLAUDE.md — Claude Code Guidance

This file is auto-loaded by **Claude Code** at the start of every session. It is the short, authoritative checklist that every change in this repository must follow. The full architecture spec lives in [`docs/tech-architecture-requirements.md`](docs/tech-architecture-requirements.md) — read it whenever a change touches an unfamiliar area.

> **Cursor users:** This same file is mirrored as `AGENTS.md`; both are kept in sync.
> **Detailed rules:** See `.cursor/rules/*.mdc` — those are scoped to file globs and contain version-specific best practices. Claude Code treats them as additional guidance and follows them when editing matching files.

---

## 1. Project at a glance

- **What:** Production-grade FastAPI backend boilerplate. Domain code is added per project; the boilerplate ships only platform endpoints (`/health`, `/ready`, `/metrics`) and the architectural skeleton.
- **Stack (locked, see §2 of the spec):** Python 3.14+, FastAPI 0.136+, Pydantic v2 (2.13+), SQLAlchemy 2.0+ (async + asyncpg), Alembic 1.18+, PostgreSQL 18+, Redis 8+, Celery 5.6+, structlog 25.5+, OpenTelemetry 1.24+, httpx 0.28+, tenacity 9.1+, **Babel 2.16+ (i18n/l10n; English + Arabic)**.
- **Deploy:** Bitbucket Pipelines → render.com. App image runs three roles via `SERVICE_ROLE`: `web`, `worker`, `beat`.
- **DX:** `make setup ENV=local|test|production` is the **single** entrypoint. Tests use an isolated stack (`docker-compose.test.yml`); never the dev DB.
- **Languages:** English (`en`, default + fallback) and Arabic (`ar`, RTL). Locale resolution is centralized; copy lives in `app/locales/<locale>/LC_MESSAGES/messages.po` (compiled to `.mo` at build time). See spec §11 and `.cursor/rules/i18n-l10n.mdc`.

## 2. Hard rules (non-negotiable)

These are review-rejecting violations:

1. **Layered architecture** — Router → Service → Repository → Persistence. No layer skips boundaries:
   - Router NEVER imports `app.repositories.*` or `app.integrations.*`.
   - Service NEVER imports `fastapi.*`, `Request`, `Response`, or raises `HTTPException`.
   - Repository NEVER calls another repository or commits transactions (services own UoW).
   - Integrations NEVER import services or repositories.
2. **Dependency Injection at every seam.** Every external collaborator is a `Protocol` injected via constructor or FastAPI `Depends`. No hidden globals, no `from app.X import singleton`.
3. **Async all the way down.** No `requests`, no sync DB, no blocking I/O on the request path.
4. **Type-annotate everything.** mypy strict; no untyped defs, no implicit `Optional`. Use modern syntax: `X | None` (not `Optional[X]`), `list[X]` (not `List[X]`).
5. **Pydantic v2 only.** `model_config = ConfigDict(extra="forbid")` on request/response schemas. Never return raw ORM objects from a route.
6. **Domain exceptions.** Services raise `DomainError` subclasses; the global handler maps to HTTP. Routers do not raise `HTTPException`.
7. **No code branching on test mode.** `if APP_ENV == "test":` in business logic = reject. Tests inject settings + override deps.
8. **Tests never touch the dev database.** `conftest.py` enforces a guardrail on the DB URL.
9. **Celery Beat = exactly one replica + Redis lock per scheduled task** (multi-server agnostic).
10. **Backward-compatible migrations only.** Add → backfill → switch → drop, across two releases.
11. **No hardcoded user-visible strings.** Every string returned to a user (HTTP responses, validation messages, email templates, log fields that surface in UI) goes through `Translator.gettext` / `_(...)`. `DomainError.message` **is** the gettext key. Translate at the boundary (handler / template), never inside services or repositories.
12. **Locale is a request-scoped concern, not a domain concern.** It is resolved once per request from `?lang=` → user pref → `Accept-Language` → `LOCALE_DEFAULT`, lives on `request.state.locale`, and propagates to Celery tasks as a **separate kwarg** (never a field on a domain event). No `if locale == "ar":` branches in business code — locale-specific behavior lives in catalogs and templates.

## 3. The "I'm about to change X" cheat sheet

| You're touching… | Read first | Do |
|---|---|---|
| A route in `app/api/v1/*` | `.cursor/rules/api-design.mdc`, `fastapi-routers.mdc`, `security.mdc` | Validate via Pydantic, call **one** service method, let exception handler map errors. |
| A service in `app/services/*` | `services-layer.mdc`, `domain-exceptions.mdc`, `dependency-injection.mdc` | Constructor-injected deps, `async with uow:` for transactions, raise `DomainError`. |
| A repository in `app/repositories/*` | `repositories-layer.mdc`, `sqlalchemy-async.mdc` | One repo per aggregate root, no commits, return entities/DTOs. |
| A SQLAlchemy model in `app/models/*` | `sqlalchemy-async.mdc`, `alembic-migrations.mdc` | `Mapped[...]`, `mapped_column(...)`, mixins for timestamps/UUID, generate migration in same PR. |
| A Pydantic schema in `app/schemas/*` | `pydantic-v2.mdc` | `extra="forbid"`, explicit field lists, no `from_attributes` in request DTOs. |
| Settings in `app/core/config.py` | `environment-config.mdc`, `pydantic-v2.mdc` | `BaseSettings`, `SecretStr` for secrets, fail-fast validation. |
| A Celery task in `app/workers/tasks/*` | `celery-tasks.mdc`, `celery-beat.mdc`, `domain-events.mdc` | Primitive args (IDs only), idempotent, named `context.action`. |
| A scheduled task | `celery-beat.mdc` | Add to `beat_schedule.py`, wrap body in distributed Redis lock. |
| A domain event | `domain-events.mdc` | Past-tense event name, immutable, dispatched **after** UoW commit. |
| Email | `email-integration.mdc`, `i18n-l10n.mdc` | Use `EmailSender` Protocol with `locale` kwarg, per-locale Jinja2 templates under `app/templates/email/<id>/<locale>/`, tests use `NullEmailSender` or MailHog. |
| A migration | `alembic-migrations.mdc` | Backward-compatible only, naming-convention metadata applied, `downgrade()` implemented for staging. |
| A test | `testing.mdc`, `test-factories-seeders.mdc` | Use factories/seeders; never inline literal data; never target dev DB; never assert on translated copy — assert on `error.code` / structured fields. |
| Docker / compose / render | `docker.mdc`, `deployment-render.mdc` | Multi-stage build, non-root user, `SERVICE_ROLE` selects entrypoint, `pybabel compile` runs in builder stage. |
| `Makefile` / `scripts/setup_env.sh` | `dx-makefile.mdc` | `make setup ENV=…` must remain the single entry. |
| A user-visible string anywhere | `i18n-l10n.mdc` | Wrap with `_("key")`, run `make i18n-extract && make i18n-update`, translate `messages.po` for `en` **and** `ar`, run `make i18n-compile`, run `make i18n-check`. Use `/new-translation` slash command to follow the full workflow. |

## 4. Workflow expectations

- **Plan before editing.** For any non-trivial change, list the files you intend to touch and the layer each belongs to. Confirm the change does not violate Section 2.
- **Update migrations + tests in the same PR** as the model change.
- **Update `.env.example`** when you add a new setting; CI will fail otherwise.
- **Update an ADR** (`docs/architecture-decisions/NNNN-title.md`) for any irreversible decision.
- **Never** introduce new top-level dependencies without justifying in the PR description and updating §2 of the spec.
- **Slash commands** live in `.claude/commands/` — use them for repeatable workflows (`/setup-local`, `/new-service`, `/new-migration`, `/new-translation`, `/review-code`, `/review-security`, etc.).
- **Adding a user-visible string?** Use `/new-translation`. It walks through extraction, translating both `en` and `ar` catalogs, compilation, and the CI completeness check.
- **Before opening a PR** (or after addressing review comments), run **`/review-code`** for technical correctness and **`/review-security`** for security. The two reviewers are intentionally independent: `code-reviewer` covers architecture / DI / Pydantic / SQLAlchemy / async / typing / i18n / testing / quality; `security-reviewer` covers authn/z / secrets / SQLi/SSRF/IDOR / containers / supply chain / audit logging / PII. Their rubrics live in `.cursor/rules/code-review.mdc` and `.cursor/rules/security-review.mdc`; the subagent definitions live in `.claude/agents/`.

## 5. What "done" means for a change

- Mypy strict passes.
- Ruff + Black pass.
- New code is unit-tested; if it touches DB/Redis, it's integration-tested via the test stack.
- Logs are structured, request-scoped, and contain no secrets. Every log line on the request path includes `locale`.
- If the change has runtime cost, a Prometheus metric and OTel span are added.
- If the change is user-visible, the OpenAPI diff is reviewed **and** every new user-visible string has entries in `messages.po` for both `en` and `ar`. `make i18n-check` passes.
- If the change touches deploy, the runbook is updated.
- **`/review-code` returns `APPROVE` or `COMMENT` (no blockers, no required-change majors).**
- **`/review-security` returns `APPROVE` (no findings above LOW).** Any CRITICAL or §20 escalation trigger blocks merge until remediated.

## 6. When you're unsure

- Default to the **simpler** option (KISS).
- Default to **explicit dependency injection**, not magic.
- Default to **fewer abstractions** (YAGNI). Wait for the third occurrence before extracting.
- If a rule in `.cursor/rules/*.mdc` conflicts with a generic best practice, **the rule wins** — it encodes a deliberate project decision.
- If the architecture spec is silent, raise it as an open question in the PR rather than guessing.
