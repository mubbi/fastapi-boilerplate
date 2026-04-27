# Technical Architecture & Requirements

**Project:** FastAPI Backend Boilerplate
**Owner:** Architecture / Backend
**Status:** Authoritative spec — any AI/engineer should be able to bootstrap a **production-ready** and **local-dev-ready** backend service from this document alone.
**Scope:** This document defines the **backend architecture, project setup, engineering principles, and operational contract** only. Domain-specific data models, business APIs, and feature endpoints are **out of scope** and live in feature-specific PRDs. The boilerplate ships with only the platform-level endpoints (`/health`, `/ready`, `/metrics`).

---

## 1. System Overview

### 1.1 Purpose
A reusable, opinionated FastAPI backend boilerplate that codifies the team's architectural standards. Every new backend service starts from this skeleton with:
- Layered architecture (API → Service → Repository → Persistence).
- Dependency Injection at every seam.
- Production-grade observability, security, and resilience defaults.
- A one-command local dev environment.
- A reproducible CI/CD pipeline targeting render.com.

### 1.2 Architectural Principles
1. **Separation of Concerns** — Routers handle HTTP, Services handle business rules, Repositories handle persistence. No layer reaches across boundaries.
2. **Dependency Injection over instantiation** — Components receive their collaborators via constructor / FastAPI `Depends`. No hidden globals.
3. **Provider-agnostic core** — All external systems (DB, cache, message broker, third-party APIs) sit behind a `Protocol` / abstract interface so providers can be swapped via config.
4. **Stateless API** — All state lives in PostgreSQL, Redis, or object storage. Pods/containers are disposable.
5. **12-Factor App** — Config from env, logs to stdout, processes are disposable, dev/prod parity.
6. **Backward-compatible migrations** — Schema changes never break the previous deployment (additive → deprecate → drop, across two releases).
7. **Fail fast at startup** — Missing config, unreachable required deps, or invalid schema crash the process before serving traffic.
8. **Graceful degradation at runtime** — Optional dependencies (cache, non-critical integrations) failing must not take down core flows.
9. **Idempotency by default** — Mutating endpoints and background tasks accept idempotency keys or are designed to be safely retried.
10. **Observability is non-optional** — Every request has a `request_id`; every external call is timed; every error is structured.

### 1.3 High-Level Architecture

```
┌─────────────┐     ┌────────────────────────────────────────────────────┐
│  Client     │────▶│                  FastAPI Backend                    │
│ (Frontend / │     │                                                     │
│  Service)   │     │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
└─────────────┘     │  │   Routers    │─▶│   Services   │─▶│  Repos    │  │
                    │  │ (HTTP layer) │  │  (Business)  │  │ (Data)    │  │
                    │  └──────────────┘  └──────────────┘  └───────────┘  │
                    │         │                  │                │       │
                    │         ▼                  ▼                ▼       │
                    │  ┌────────────────────────────────────────────┐    │
                    │  │  DI Container  /  FastAPI Dependencies     │    │
                    │  └────────────────────────────────────────────┘    │
                    │         │                  │                │       │
                    │         ▼                  ▼                ▼       │
                    │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
                    │  │ Integrations │  │    Cache     │  │    DB     │  │
                    │  │  (Adapters)  │  │   (Redis)    │  │ (Postgres)│  │
                    │  └──────────────┘  └──────────────┘  └───────────┘  │
                    └────────────────────────────┬────────────────────────┘
                                                 │
                                  ┌──────────────▼──────────────┐
                                  │   Background Workers        │
                                  │   (Celery + Beat)           │
                                  └──────────────┬──────────────┘
                                                 │
                                       ┌─────────▼─────────┐
                                       │ Redis (broker +   │
                                       │ result + cache)   │
                                       └───────────────────┘
```

### 1.4 Cross-Cutting Concerns (handled centrally, not in each route)
- Request ID propagation, structured logging, tracing.
- Authentication / authorization.
- Rate limiting.
- Input validation & sanitization.
- Exception → HTTP error mapping.
- CORS, security headers.
- Metrics emission.
- Transactional email (`EmailSender` Protocol) and **domain events** dispatched to Celery (§10.3–10.4).
- **Locale resolution & translation** (`Translator` Protocol, gettext catalogs, locale-aware formatting and email templates) — see §11.
- Graceful shutdown of DB pool, Redis, HTTP clients, Celery workers.

---

## 2. Technology Stack (Locked Choices)

| Layer | Choice | Version (min) | Rationale |
|---|---|---|---|
| Language | Python | 3.14.4+ | Modern typing, performance, broad lib support |
| API Framework | FastAPI | 0.136.1+ | Async, Pydantic, OpenAPI built-in |
| ASGI Server | Uvicorn (dev) / Gunicorn + UvicornWorker (prod) | latest | Standard FastAPI runtime |
| Validation | Pydantic v2 | 2.13.3+ | Required by FastAPI, fast |
| Settings | pydantic-settings | latest | Typed env var loading |
| ORM | SQLAlchemy (async) | 2.0.49+ | Async support, mature |
| DB Driver | asyncpg | latest | Fastest async Postgres driver |
| Migrations | Alembic | 1.18.4+ | Standard for SQLAlchemy |
| Primary DB | PostgreSQL | 18.3+ | JSONB, full-text search, partitioning |
| Cache / Broker | Redis | 8.0.16+ | Cache + Celery broker + rate-limit store + idempotency keys |
| Task Queue | Celery | 5.6.3+ | Mature, Redis broker |
| Scheduler | Celery Beat | bundled | Periodic tasks |
| HTTP Client | httpx | 0.28.1+ | Async, retries via `tenacity` |
| Retries / Circuit Breaker | tenacity (+ purgatory or custom) | 9.1.4+ | Exponential backoff + breakers |
| Logging | structlog | 25.5.0+ | Structured JSON logs |
| Metrics | prometheus-client | 0.25.0+ | Standard scrape format |
| Tracing | OpenTelemetry SDK + auto-instrumentation | 1.24+ | Vendor-agnostic |
| Error tracking | Sentry SDK | latest | Production error visibility |
| Auth | python-jose (JWT) + passlib[bcrypt] | latest | Stateless tokens, secure hashing |
| Rate Limiting | slowapi | 0.1.9+ | Redis-backed |
| Email (async) | aiosmtplib | latest | SMTP for transactional mail; provider adapters optional |
| Email (templating) | Jinja2 | latest | HTML/text templates in `app/templates/email/` (per-locale subdirs, see §11) |
| i18n / l10n | Babel | 2.16+ | Locale negotiation, gettext catalogs, plural rules (incl. Arabic CLDR), date/number/currency formatting (see §11) |
| Testing | pytest, pytest-asyncio, pytest-cov, pytest-xdist, httpx, factory-boy, faker, freezegun | latest | Standard stack + parallel runs |
| Linting | Ruff | 0.15.12+ | Replaces Flake8 + isort |
| Formatting | Black | 26.3.1+ | Consistent style |
| Type Checking | mypy | 1.20.2+ | Strict mode |
| Security scanning | pip-audit, bandit, detect-secrets | latest | CI gates |
| Git hooks | `docker/.githooks/` → `.git/hooks/`; **`make git-hooks-commit`** / **`make git-hooks-push`** (`GIT_HOOKS_PUSH_QUICK=1` → lighter push) | — | **`git-hooks-push`** = **`make ci-local`**; Docker via Makefile (no Python `pre-commit` package) |
| Dependency manager | uv (preferred) or pip-tools | latest | Reproducible locks |
| Container | Docker | 29.4.1+ | Multi-stage build |
| Orchestration (local) | Docker Compose v2 | latest | Single-command dev env |
| Orchestration (prod) | render.com | — | Automated deployment |
| Secrets (prod) | Render Secret Manager | — | Never commit |
| CI/CD | Bitbucket Pipelines | — | Lint, test, build, deploy |

> **Decision rule:** If a library is not listed here, prefer the most-starred well-maintained option, document the choice in this file via PR.

---

## 3. Architectural Patterns & Engineering Principles

This section is **mandatory reading** for any contributor. The boilerplate exists to make these patterns the path of least resistance.

### 3.1 SOLID

| Principle | What it means here | How we enforce it |
|---|---|---|
| **S — Single Responsibility** | A class/module has one reason to change. Routers don't query DB. Services don't format HTTP. Repositories don't run business rules. | Layer boundaries enforced by directory structure and review. mypy + ruff `B` rules flag excessive complexity. |
| **O — Open/Closed** | Extend behavior via new implementations of an interface, not by editing existing code. | All external systems sit behind a `Protocol` (`LLMProvider`, `CacheClient`, `EventPublisher`, etc.); adding a new provider = new class, no edit of existing ones. |
| **L — Liskov Substitution** | Any implementation of an interface must be drop-in usable. | Contract tests run the same suite against every provider implementation (e.g., real Redis vs in-memory cache). |
| **I — Interface Segregation** | Clients depend on the smallest interface they need. | Protocols are split by capability (`Reader`, `Writer`, `HealthCheck`) rather than one fat interface. |
| **D — Dependency Inversion** | High-level modules depend on abstractions, not concretions. | Services accept Protocols in `__init__`; concrete implementations are wired in the composition root (`app/core/container.py` and FastAPI `Depends`). |

### 3.2 DRY, KISS, YAGNI

- **DRY (Don't Repeat Yourself)** — Shared logic lives in `app/core/`, `app/utils/`, or a base class. **But**: prefer duplication over a wrong abstraction; only extract after the third occurrence.
- **KISS (Keep It Simple, Stupid)** — Prefer obvious code. No metaclasses, no clever decorators, no magic. If a junior can't read it in 30 seconds, simplify.
- **YAGNI (You Aren't Gonna Need It)** — Don't build for hypothetical future needs. No empty interfaces "for later", no plugin systems until there are 2+ plugins, no config knobs without a current user.

### 3.3 Layered Architecture (strict)

```
HTTP Request
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  Router (app/api/v1/*.py)                            │
│  - Parses request, validates via Pydantic schema     │
│  - Calls a single service method                     │
│  - Maps service result/exception → HTTP response     │
│  - NO business logic, NO direct DB/cache calls       │
└──────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  Service (app/services/*.py)                         │
│  - Orchestrates business rules                       │
│  - Calls repositories + integrations                 │
│  - Manages transactions (unit of work)               │
│  - Raises domain exceptions, never HTTP exceptions   │
│  - Pure async functions, no FastAPI imports          │
└──────────────────────────────────────────────────────┘
    │                              │
    ▼                              ▼
┌─────────────────────┐   ┌──────────────────────────┐
│ Repository          │   │ Integration / Adapter    │
│ (app/repositories/) │   │ (app/integrations/*)     │
│ - DB access only    │   │ - Wraps external API     │
│ - Returns models or │   │ - Implements a Protocol  │
│   domain DTOs       │   │ - Handles retries/timeo. │
└─────────────────────┘   └──────────────────────────┘
```

**Hard rules:**
- A router NEVER imports `app.repositories.*` or `app.integrations.*`. It only imports services and schemas.
- A service NEVER imports `fastapi.*`, `Request`, `Response`, or HTTPException.
- A repository NEVER calls another repository (cross-aggregate joins live in services or read models).
- Integrations NEVER import services or repositories.

### 3.4 Repository Pattern

**Purpose:** Isolate persistence so business logic is testable without a database, and so the storage engine can change without touching services.

**Contract:**
```python
class PerfumeRepository(Protocol):
    async def get_by_id(self, entity_id: UUID) -> Entity | None: ...
    async def list(self, filters: Filters, page: Page) -> Paginated[Entity]: ...
    async def add(self, entity: Entity) -> Entity: ...
    async def update(self, entity: Entity) -> Entity: ...
    async def delete(self, entity_id: UUID) -> None: ...
```

**Rules:**
- One repository per **aggregate root**, not per table.
- Repositories accept and return **domain entities or DTOs**, not raw ORM rows leaking out of the boundary (when it adds friction to keep mapping; otherwise ORM models are fine for a small CRUD service — pick one stance per service and document it).
- A `BaseRepository[Model]` provides generic `get/list/add/update/delete` to keep concrete repos thin.
- The session/transaction is owned by the **service layer** (Unit of Work), passed into repos via DI.

### 3.5 Service Pattern

**Purpose:** Encapsulate business rules and orchestration; the only layer that knows what a use case means.

**Rules:**
- One service per **bounded context / use case cluster**.
- Public methods correspond to **use cases**, not CRUD verbs.
- Services raise typed `DomainError` subclasses; the global exception handler maps them to HTTP responses.
- Services are constructed with their dependencies (repos, integrations, clock, logger) — **no `from app.X import singleton`**.

```python
class ExampleService:
    def __init__(
        self,
        repo: ExampleRepository,
        cache: CacheClient,
        events: EventPublisher,
        clock: Clock,
    ) -> None:
        self._repo = repo
        self._cache = cache
        self._events = events
        self._clock = clock
```

### 3.6 Dependency Injection

**Mechanism:** FastAPI's `Depends` is the primary DI tool; a thin **composition root** (`app/core/container.py`) holds factory functions that wire concrete implementations to Protocols. No third-party DI framework — keep it boring.

**Wiring layers:**
1. **Settings** — `get_settings()` (cached) returns the validated `Settings` object.
2. **Infra clients** — `get_db_session()`, `get_redis()`, `get_http_client()` yield managed resources with proper teardown.
3. **Repositories** — `get_example_repo(session = Depends(get_db_session))` constructs a repo bound to the request's session.
4. **Services** — `get_example_service(repo = Depends(get_example_repo), ...)` wires repos + integrations into a service.
5. **Router** — `async def endpoint(svc: ExampleService = Depends(get_example_service))`.

**Rules:**
- Every dependency MUST be overridable in tests via `app.dependency_overrides`.
- No `lru_cache` on functions that hold per-request state (DB sessions, request-scoped contexts).
- The container module never imports routers (avoid cycles).
- Protocols live next to their default implementation in `app/integrations/<x>/base.py`.

### 3.7 Domain Exceptions & Error Mapping

- All non-HTTP errors raised inside services/repositories inherit from `app.core.exceptions.DomainError`.
- Standard subclasses: `NotFoundError`, `ConflictError`, `ValidationError`, `UnauthorizedError`, `ForbiddenError`, `RateLimitedError`, `ExternalServiceError`, `TimeoutError`.
- Each `DomainError` carries a stable machine-readable `code`, a default-English `message` that doubles as the **gettext key**, and a `details` mapping used as templating params for translated messages (see §11.5).
- A single `register_exception_handlers(app)` maps each domain exception to an `ErrorResponse` envelope (see §9.1) and **localizes** `message` via the `Translator` using `request.state.locale`.
- Routers MUST NOT raise `HTTPException` directly; raise the domain exception and let the handler translate.

### 3.8 Engineering Practices Checklist

- Type-annotate everything; mypy strict.
- Pure functions wherever possible; side effects pushed to edges.
- Async all the way down — no `requests`, no sync DB calls inside routes.
- Constants in `app/core/constants.py`; magic numbers/strings in code = review reject.
- Feature flags via env vars (`FEATURE_X_ENABLED=true`), never via code branches on `APP_ENV`.
- Public functions/classes documented with docstrings; private helpers don't need docs but need clear names.
- No TODO comments without a linked ticket ID.
- No commented-out code in PRs — delete; git remembers.

---

## 4. Project Structure

```
fastapi-boilerplate/
├── app/
│   ├── __init__.py
│   ├── main.py                      # App factory, middleware wiring, lifespan
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                  # Shared FastAPI dependencies (auth, pagination)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py            # Aggregates all v1 routers
│   │       └── system.py            # /health, /ready, /metrics
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Pydantic Settings (env)
│   │   ├── container.py             # Composition root: factory functions
│   │   ├── logging.py               # structlog config + processors
│   │   ├── tracing.py               # OpenTelemetry setup
│   │   ├── metrics.py               # Prometheus registry + custom metrics
│   │   ├── security.py              # JWT, password hashing, sanitization
│   │   ├── rate_limit.py            # slowapi setup
│   │   ├── exceptions.py            # DomainError hierarchy + handlers
│   │   ├── middleware.py            # Request ID, timing, CORS, security headers, locale resolution
│   │   ├── lifespan.py              # Startup/shutdown hooks
│   │   ├── constants.py             # Project-wide constants
│   │   ├── clock.py                 # Clock Protocol + SystemClock (for tests)
│   │   └── i18n.py                  # Translator Protocol, locale resolver, Babel setup (see §11)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py               # Async engine + session factory + UoW
│   │   ├── base.py                  # Declarative base, naming convention
│   │   └── mixins.py                # TimestampMixin, SoftDeleteMixin, UUIDMixin
│   ├── models/                      # SQLAlchemy ORM models (per service-defined)
│   │   └── __init__.py              # Empty in boilerplate; populated per project
│   ├── schemas/                     # Pydantic DTOs (request/response)
│   │   ├── __init__.py
│   │   ├── common.py                # Pagination, ErrorResponse, HealthResponse
│   │   └── system.py                # /health, /ready, /metrics schemas
│   ├── repositories/                # DB access layer
│   │   ├── __init__.py
│   │   └── base.py                  # Generic CRUD repository + Protocols
│   ├── services/                    # Business logic
│   │   ├── __init__.py
│   │   └── system_service.py        # Health/readiness checks orchestration
│   ├── integrations/                # External provider adapters
│   │   ├── __init__.py
│   │   ├── cache/
│   │   │   ├── base.py              # CacheClient Protocol
│   │   │   ├── redis_cache.py
│   │   │   └── in_memory_cache.py   # For tests / local fallback
│   │   ├── email/
│   │   │   ├── base.py              # EmailSender Protocol (send, send_template)
│   │   │   ├── smtp_sender.py       # aiosmtplib implementation
│   │   │   └── null_sender.py       # No-op for tests / local without SMTP
│   │   └── http/
│   │       ├── base.py              # HttpClient Protocol
│   │       └── httpx_client.py      # Shared retry/timeout/circuit-breaker config
│   ├── events/                      # Domain events → Celery (see §10.4)
│   │   ├── __init__.py
│   │   ├── types.py                 # Event dataclasses / Pydantic models (immutable)
│   │   ├── publisher.py             # EventPublisher: enqueue Celery tasks / fan-out
│   │   └── registry.py              # Map event type → task name + serializer
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── celery_app.py            # Celery factory
│   │   ├── beat_schedule.py         # Periodic tasks (Beat singleton + locks in prod)
│   │   └── tasks/
│   │       ├── __init__.py
│   │       └── events_tasks.py      # Generic handlers: dispatch_event, per-domain listeners
│   ├── locales/                     # gettext catalogs, one subdir per locale (see §11.4)
│   │   ├── en/
│   │   │   └── LC_MESSAGES/
│   │   │       ├── messages.po
│   │   │       └── messages.mo      # generated; committed or built in CI/Docker
│   │   ├── ar/
│   │   │   └── LC_MESSAGES/
│   │   │       ├── messages.po
│   │   │       └── messages.mo
│   │   └── messages.pot             # generated by `make i18n-extract`
│   ├── templates/
│   │   └── email/                   # one subdir per template; per-locale variants
│   │       └── <name>/
│   │           ├── en/{html.j2,txt.j2,subject.j2}
│   │           └── ar/{html.j2,txt.j2,subject.j2}
│   └── utils/
│       ├── __init__.py
│       ├── pagination.py
│       ├── ids.py                   # UUID v7 generator, slug helpers
│       └── async_utils.py           # gather_with_concurrency, etc.
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── babel.cfg                          # Babel extraction config (see §11.4)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Fixtures: test settings, isolated DB/Redis URLs
│   ├── factories/                   # factory_boy: per-model Factory classes (see §15.3)
│   │   ├── __init__.py
│   │   └── base.py                  # BaseFactory, SQLAlchemyModelFactory hooks
│   ├── seeders/                     # Composed test data (orchestrates factories)
│   │   ├── __init__.py
│   │   └── database_seeder.py       # seed_minimal(), seed_integration_scenario_*()
│   ├── fakes/                     # In-memory Protocol implementations
│   ├── unit/
│   ├── integration/
│   ├── api/
│   └── contract/                    # Provider contract tests
├── scripts/
│   ├── setup_env.sh                 # Invoked by `make setup` (ENV + SERVICE_ROLE branching)
│   ├── install_git_hooks.sh         # copy-only: docker/.githooks → .git/hooks (setup + make install-git-hooks)
│   ├── seed_dev_data.py
│   └── healthcheck.py
├── docker/
│   ├── Dockerfile                   # Multi-stage (api + worker share image)
│   ├── Dockerfile.dev               # CI / local tooling image (`dev` compose service)
│   ├── .githooks/                   # Git hook templates (`git-hooks-commit`; `git-hooks-push`) → copied to `.git/hooks`
│   ├── docker-entrypoint.sh
│   └── healthcheck.sh
├── .bitbucket/
│   └── pipelines/                   # Bitbucket Pipelines configs (split by env)
├── bitbucket-pipelines.yml
├── render.yaml                      # Render Blueprint (services, env, jobs)
├── docs/
│   ├── tech-architecture-requirements.md  # ← this file (authoritative architecture spec)
│   ├── architecture-decisions/      # ADRs (numbered, immutable once merged)
│   └── runbooks/                    # Operational runbooks
├── docker-compose.yml               # Default: local dev (api, worker, beat, postgres, redis, mail)
├── docker-compose.override.yml      # Dev-only overrides (hot reload, debug ports)
├── docker-compose.test.yml          # Test stack ONLY: postgres_test, redis_test, mailhog (see §15.4)
├── docker-compose.prod.yml          # Optional: prod-like local (external DB URLs)
├── .env.example
├── .env.test                        # URLs pointing at *_test containers / CI services
├── .gitignore
├── .dockerignore
├── .editorconfig
├── .python-version
├── pyproject.toml                   # Deps + ruff + black + mypy + pytest config
├── uv.lock                          # (or requirements.lock) - reproducible lock
├── alembic.ini
├── Makefile
├── README.md
└── AGENTS.md                        # AI assistant guidance (optional)
```

**Why some folders are empty in the boilerplate:** `models/`, `repositories/` (besides `base.py`), `services/` (besides `system_service.py`), and `workers/tasks/` ship empty so each project clones the boilerplate and adds its own domain artifacts without deleting examples.

---

## 5. Configuration & Environment Variables

All config via env vars, loaded by `app/core/config.py` using `pydantic-settings`. **No secrets in code.** A complete `.env.example` MUST exist, listing every variable with a safe default or empty string.

### 5.1 Settings Class Rules
- Single `Settings(BaseSettings)` class; nested settings via `BaseModel` sub-classes (e.g., `DatabaseSettings`, `RedisSettings`).
- `model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", extra="forbid")`.
- All required fields fail fast at startup with a clear error.
- `get_settings()` is `@lru_cache`-wrapped; reset in tests via `get_settings.cache_clear()`.
- Sensitive fields use `SecretStr`; `__repr__` redacts them.

### 5.2 Required Variables

```ini
# ── Application ──────────────────────────────────────────────
APP_NAME=fastapi-boilerplate
APP_ENV=local                       # local | dev | staging | production
APP_VERSION=0.1.0                   # injected at build time from git SHA
APP_DEBUG=true
APP_LOG_LEVEL=INFO                  # DEBUG | INFO | WARNING | ERROR
APP_LOG_FORMAT=json                 # json | console (console only for local)
APP_HOST=0.0.0.0
APP_PORT=8000
APP_API_V1_PREFIX=/api/v1
APP_CORS_ORIGINS=["http://localhost:3000"]
APP_CORS_ALLOW_CREDENTIALS=true
APP_REQUEST_TIMEOUT_SECONDS=30
APP_GRACEFUL_SHUTDOWN_SECONDS=20
APP_DOCS_ENABLED=true               # auto-disabled when APP_ENV=production unless overridden
APP_TRUSTED_HOSTS=["*"]             # restrict in prod
# Process role (production / containers): which command the image runs
# web | worker | beat — see §17.7 and §18.2
SERVICE_ROLE=web

# ── Security ─────────────────────────────────────────────────
SECRET_KEY=change-me-min-32-chars-random-string
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=14
AUTH_ENABLED=false
PASSWORD_MIN_LENGTH=12
RATE_LIMIT_DEFAULT=60/minute
RATE_LIMIT_AUTH=10/minute

# ── PostgreSQL ───────────────────────────────────────────────
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=app_db
POSTGRES_USER=app
POSTGRES_PASSWORD=app
DATABASE_URL=postgresql+asyncpg://app:app@postgres:5432/app_db
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE_SECONDS=1800
DATABASE_ECHO=false                 # SQL logging - never true in prod
DATABASE_STATEMENT_TIMEOUT_MS=15000

# ── Test isolation (local + CI) — NEVER point at dev/prod DB ──
# Used when APP_ENV=test or pytest; docker-compose.test.yml provides these hosts
DATABASE_URL_TEST=postgresql+asyncpg://app_test:app_test@postgres_test:5432/app_test
REDIS_URL_TEST=redis://redis_test:6379/0
CELERY_BROKER_URL_TEST=redis://redis_test:6379/1
CELERY_RESULT_BACKEND_TEST=redis://redis_test:6379/2

# ── Redis ────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5
CACHE_DEFAULT_TTL_SECONDS=300

# ── Celery ───────────────────────────────────────────────────
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
CELERY_TASK_ALWAYS_EAGER=false      # true only in tests
CELERY_TASK_TIME_LIMIT=300
CELERY_TASK_SOFT_TIME_LIMIT=240
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_PREFETCH_MULTIPLIER=1
CELERY_TASK_ACKS_LATE=true
# Beat / cron safety (see §10.5)
CELERY_BEAT_SCHEDULE_FILENAME=              # empty = default; optional persistent file for dev only
CELERY_CRON_LOCK_PREFIX=celery_cron
CELERY_CRON_LOCK_TTL_SECONDS=300
# Optional: Redis-backed beat scheduler so schedule state is not filesystem-bound (leader + overlap policy still §10.5)
# CELERY_BEAT_SCHEDULER=redbeat.RedBeatScheduler
# REDBEAT_REDIS_URL=redis://redis:6379/3

# ── Email ────────────────────────────────────────────────────
EMAIL_ENABLED=false
EMAIL_FROM_ADDRESS=noreply@example.com
EMAIL_FROM_NAME=FastAPI Boilerplate
# SMTP (aiosmtplib)
SMTP_HOST=mailhog
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_USE_TLS=false
SMTP_USE_STARTTLS=false
# Transactional provider (optional alternative to raw SMTP): leave empty to use SMTP
# EMAIL_PROVIDER=sendgrid | ses | postmark | smtp
# SENDGRID_API_KEY=
# AWS_REGION=eu-west-1

# ── HTTP Client (outbound) ───────────────────────────────────
HTTP_CLIENT_TIMEOUT_SECONDS=10
HTTP_CLIENT_MAX_KEEPALIVE=20
HTTP_CLIENT_MAX_CONNECTIONS=100
HTTP_CLIENT_RETRY_ATTEMPTS=3
HTTP_CLIENT_RETRY_BACKOFF_BASE=0.5

# ── Observability ────────────────────────────────────────────
SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=0.1
OTEL_EXPORTER_OTLP_ENDPOINT=
OTEL_SERVICE_NAME=fastapi-boilerplate
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1
PROMETHEUS_ENABLED=true
METRICS_ENDPOINT_AUTH_TOKEN=        # if set, /metrics requires Bearer header

# ── i18n / l10n (see §11) ────────────────────────────────────
LOCALES_ENABLED=["en","ar"]         # JSON list of BCP-47 codes; first allowlisted, others rejected
LOCALE_DEFAULT=en                   # used when negotiation produces no match
LOCALE_FALLBACK=en                  # used when a translation key is missing in the resolved locale
LOCALE_QUERY_PARAM=lang             # ?lang=ar override; empty string disables this hop
LOCALE_HEADER_NAME=Accept-Language  # standard BCP-47 header
LOCALE_DOMAIN=messages              # gettext text-domain (matches messages.po / messages.mo)
LOCALE_DIR=app/locales              # path to gettext catalogs
RTL_LOCALES=["ar"]                  # locales requiring dir="rtl" in HTML emails
LOCALE_TRANSLATION_COMPLETENESS_MIN=0.95  # CI gate; below = pipeline fails

# ── Feature Flags (examples) ─────────────────────────────────
FEATURE_X_ENABLED=false
```

### 5.3 Rules
- `.env` is **gitignored**; `.env.example` is committed and stays in sync (CI check fails the build if drift is detected).
- `.env.test` is committed with safe test defaults and **must** use `DATABASE_URL_TEST`, `REDIS_URL_TEST`, and mail sink hostnames (`mailhog` / `localhost`) so no developer accidentally runs pytest against the dev database.
- Application code under `app/` **never** branches on "am I in a test" via globals; tests inject settings and override dependencies. Optional `APP_ENV=test` is allowed only for disabling external side effects in integration tests (e.g. skip real SMTP), not for changing business logic.
- Production secrets come from Render Secret Manager and are injected as env at runtime — **never** baked into images.
- Settings class must validate types at startup; missing required vars fail fast with the offending field name.
- All settings printed at startup at INFO level **except** `SecretStr` fields (which print as `***`).

---

## 6. Database & Migrations

### 6.1 Connection Management
- One async engine per process, created in the lifespan startup hook.
- `AsyncSession` per request, yielded by `get_db_session()` dep, closed in `finally`.
- Pool sizing tuned per environment (see env vars). Prod: `pool_pre_ping=true`, `pool_recycle=1800`.
- Read-only endpoints can use a separate read-replica engine when introduced (Open/Closed: add a `get_read_session()` dep, don't change existing one).

### 6.2 Naming Convention (SQLAlchemy)
A consistent constraint naming convention MUST be configured on `MetaData`:
```
ix_%(table_name)s_%(column_0_N_label)s         # indexes
uq_%(table_name)s_%(column_0_N_name)s          # unique constraints
ck_%(table_name)s_%(constraint_name)s          # check constraints
fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s
pk_%(table_name)s
```
This makes Alembic autogenerate stable and review diffs deterministic.

### 6.3 Model Conventions
- Primary keys: UUID v7 (sortable) generated app-side, or `BIGSERIAL` for high-write tables — choose per project, document in ADR.
- Every table has: `id`, `created_at`, `updated_at` (via `TimestampMixin`).
- Soft-delete (`deleted_at` via `SoftDeleteMixin`) only when business requires; otherwise hard delete.
- Use JSONB for flexible / non-queried metadata only; first-class columns for anything queried or constrained.
- All FKs declare `ON DELETE` / `ON UPDATE` explicitly.
- All columns NOT NULL unless nullability is intentional.

### 6.4 Migrations (Alembic)
- One migration per PR that changes the schema. Filename includes ticket ID and short slug.
- Migrations are **forward-only in production**; downgrade scripts exist for staging/local.
- Migrations are **backward-compatible** with the previous deploy:
  1. Add new column nullable / with default.
  2. Deploy code that writes both old and new.
  3. Backfill.
  4. Deploy code that reads new only.
  5. Drop old in a later release.
- Long-running migrations (data backfills, index builds on large tables) run as **separate jobs**, not in the deploy hook.
- `alembic upgrade head` runs as a Render pre-deploy job; deploy is gated on its success.
- CI runs `alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` against a fresh DB to verify both directions.

### 6.5 Transactions & Unit of Work
- Services own transaction boundaries via an explicit `async with uow:` block.
- Repositories never call `commit()`; they call `flush()` only when needed for ID assignment.
- Default isolation level: `READ COMMITTED`. Use `REPEATABLE READ` or `SERIALIZABLE` only with documented justification.

---

## 7. Caching Strategy (Redis)

### 7.1 Key Conventions
- Format: `<service>:<entity>:<id>:<version>` — e.g., `boilerplate:user:profile:v1`.
- TTL is mandatory. No keys without TTL (set sensible default, override per use case).
- Versioning via key suffix lets us invalidate atomically by changing the suffix.

### 7.2 Patterns Supported
- **Cache-aside** (default): read cache → miss → load from source → set cache.
- **Idempotency keys**: `idempotency:<endpoint>:<key>` storing response hash, TTL = 24h.
- **Distributed locks**: `lock:<resource>:<id>` via SET NX with auto-expiry; only used inside services, never in routes.
- **Rate limiting**: managed by slowapi against the same Redis.

### 7.3 Rules
- `CacheClient` Protocol abstracts Redis; tests use `InMemoryCache` implementation.
- Cache failures **never** fail the request; log + metric + serve from source.
- No caching of authenticated user data without a per-user cache key.

---

## 8. Resilience Patterns

### 8.1 Outbound HTTP
- All outbound HTTP via the shared `httpx.AsyncClient` configured in the container with:
  - Connection + read timeouts (`HTTP_CLIENT_TIMEOUT_SECONDS`).
  - Connection pool limits.
  - Default headers (User-Agent = `<APP_NAME>/<APP_VERSION>`).
- Retries via `tenacity`: max 3 attempts, exponential backoff with jitter, retry only on idempotent methods + retryable status codes (408, 429, 5xx).
- Circuit breaker per upstream: open after 5 consecutive failures in 30s, half-open after 30s, close on first success.
- Every outbound call: timed metric, structured log (URL host + status + duration, never the body), trace span.

### 8.2 Background Tasks
- `acks_late=true`, `max_retries=5`, exponential backoff (`2^n * 30s`), jitter.
- Idempotent by design (re-running yields the same state).
- Dead-letter queue for permanent failures, surfaced via an internal admin task or log alert.
- Prefetch multiplier = 1 for tasks that hit rate-limited APIs.

### 8.3 Graceful Shutdown
- Signal handler (SIGTERM/SIGINT) flips a "draining" flag → `/ready` returns 503.
- Load balancer stops sending new traffic.
- App finishes in-flight requests within `APP_GRACEFUL_SHUTDOWN_SECONDS`.
- Lifespan teardown closes DB engine, Redis pool, HTTP client, OTel exporters.
- Celery workers stop accepting new tasks, finish current ones, then exit.

### 8.4 Timeouts (defense in depth)
- Per-route soft timeout via dependency.
- DB statement timeout (`DATABASE_STATEMENT_TIMEOUT_MS`).
- HTTP client per-request timeout.
- Celery task soft + hard limits.

---

## 9. API Design Standards

### 9.1 Conventions
- All business endpoints are versioned under `/api/v{N}` (initial: `/api/v1`). Platform endpoints (`/health`, `/ready`, `/metrics`) are unversioned.
- Response envelope for errors:
  ```json
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Human-readable summary",
      "details": { "field": "reason" },
      "request_id": "uuid",
      "timestamp": "2026-04-27T19:00:00Z"
    }
  }
  ```
- Success responses return the resource directly; lists use `{ "items": [...], "page": {...} }`.
- Every response carries `X-Request-ID` and `X-API-Version` headers.
- Pagination: `?page=&page_size=` (cursor-based for high-cardinality lists, documented per endpoint). `page_size` capped at 100.
- Filtering / sorting: `?filter[field]=value`, `?sort=field,-other_field`. Document allowed fields per endpoint.
- Idempotency: mutating endpoints accept `Idempotency-Key` header; key + response cached for 24h.
- Content negotiation: JSON only (`application/json`); `415` on anything else.
- **Locale negotiation:** clients may send `Accept-Language: ar, en;q=0.9` or `?lang=ar`. The server resolves a locale via §11.2 priority, echoes it back as `Content-Language`, and uses it to translate `error.message`, validation messages, and any user-facing payload text. The error envelope shape is unchanged; `error.code` is **always** locale-independent.
- Dates / times: RFC 3339 / ISO 8601 with timezone, UTC. **User-facing** date/number/currency formatting uses the resolved locale via Babel; raw API dates remain ISO 8601.
- Naming: snake_case for JSON fields, kebab-case for URL paths, lowercase plural nouns for collections.

### 9.2 HTTP Status Code Discipline
| Code | Use |
|---|---|
| 200 | Success with body |
| 201 | Resource created (Location header points to it) |
| 202 | Accepted (async work queued) |
| 204 | Success, no body (e.g., DELETE) |
| 400 | Malformed request (rare; usually Pydantic catches first) |
| 401 | Authentication missing/invalid |
| 403 | Authenticated but not authorized |
| 404 | Resource not found |
| 409 | Conflict (duplicate, version mismatch) |
| 422 | Validation failed (Pydantic default) |
| 429 | Rate limit exceeded |
| 500 | Unexpected server error |
| 502 / 503 / 504 | Upstream failure / not ready / upstream timeout |

### 9.3 OpenAPI
- Auto-generated; every route has `summary`, `description`, `response_model`, and explicit error responses.
- `/docs` (Swagger) and `/redoc` enabled in non-prod; in prod, gated behind admin auth or fully disabled per `APP_DOCS_ENABLED`.
- OpenAPI schema is exported as a build artifact (`openapi.json`) in CI for downstream consumers.

### 9.4 Boilerplate Endpoints (the only ones shipped)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | none | Liveness — process is up. Always 200 if app is running. |
| GET | `/ready` | none | Readiness — checks all required deps (DB, Redis); returns 503 if any are unhealthy or shutdown is draining. Cached 5–10s. |
| GET | `/metrics` | optional bearer | Prometheus scrape format. Protected by `METRICS_ENDPOINT_AUTH_TOKEN` if set. |
| GET | `/api/v1/health` | none | Same as `/health` but versioned (for clients that pin to `/api/v1`). |
| GET | `/api/v1/ready` | none | Same as `/ready` but versioned. |

> Domain endpoints are added per project. The boilerplate intentionally ships **only** the platform endpoints above.

### 9.5 `/ready` Contract
- Checks executed in parallel with timeouts (1s each):
  - PostgreSQL: `SELECT 1`.
  - Redis: `PING`.
  - Each registered integration's `health()` (Open/Closed: services register checks at startup).
- Response shape:
  ```json
  {
    "status": "ok" | "degraded" | "unhealthy",
    "checks": {
      "database": { "status": "ok", "latency_ms": 3 },
      "redis":    { "status": "ok", "latency_ms": 1 }
    },
    "version": "0.1.0",
    "uptime_seconds": 1234
  }
  ```
- Status mapping: all required ok → 200; any required failing → 503; optional dep failing → 200 with `degraded`.

---

## 10. Background Jobs (Celery), Domain Events & Email

### 10.1 Conventions
- Tasks live in `app/workers/tasks/<context>_tasks.py`, one module per bounded context.
- Task names are explicit: `@celery_app.task(name="context.action")`.
- Tasks accept primitive arguments only (IDs, not ORM objects); fetch state inside the task.
- Tasks construct services via the same container (`get_*_service`) — the same DI graph as the API.
- Tasks log start/finish with `task_id`, args (sanitized), and duration.

### 10.2 Reliability
- Idempotent by design.
- `acks_late=true`, `max_retries=5`, exponential backoff with jitter.
- Time limits configured (`CELERY_TASK_TIME_LIMIT`, `CELERY_TASK_SOFT_TIME_LIMIT`).
- Failure → Sentry + structured log + DLQ via routing key.

### 10.3 Domain events → Celery (listener pattern)

**Goal:** Application code dispatches **domain events** after successful commits; **listeners** run as Celery tasks so HTTP latency stays low and retries are centralized.

**Components:**
- **`app/events/types.py`** — Immutable event payloads (`dataclass(frozen=True)` or Pydantic models with `model_config = frozen`). Include `event_id`, `occurred_at`, `aggregate_type`, `aggregate_id`, and a version (`schema_version`).
- **`app/events/registry.py`** — Maps `EventType` (string or enum) → Celery task name + optional routing key (queue).
- **`app/events/publisher.py`** — `EventPublisher` Protocol:
  - `publish(event: DomainEvent) -> None` — serializes event to JSON-safe dict and calls `celery_app.send_task(...)` with `task_id` derived from `event_id` when deduplication is required.
  - Default implementation is **thin**: no business logic; only enqueue.
- **Listeners** — Ordinary Celery tasks registered in `app/workers/tasks/events_tasks.py` (and domain-specific modules). Naming: `on_<aggregate>_<past_tense_verb>` e.g. `on_user_registered_send_welcome_email`.
- **Dispatch point** — Services call `await self._events.publish(UserRegistered(...))` **after** the Unit of Work commits (or inside `uow` commit hook) so listeners never see rolled-back state.

**Rules:**
- Events are **facts that already happened** (past tense), not commands.
- Listeners must be **idempotent** (same `event_id` processed twice must be safe); use DB unique constraint on `(event_id, handler_name)` or Redis `SETNX` for dedupe when needed.
- Cross-aggregate workflows chain by publishing new events from listeners, not by calling other services' private methods.
- For **high-volume** domains, route to dedicated queues (`celery -Q events,default`) and scale workers per queue.

### 10.4 Email

**Abstraction:** `EmailSender` Protocol in `app/integrations/email/base.py`:
- `send(message: EmailMessage) -> None` — plain recipients, subject, text/html body.
- `send_template(template_id: str, to: list[str], context: dict, locale: str | None = None) -> None` — renders Jinja2 from `app/templates/email/<template_id>/<locale>/`.

**Implementations:**
- **`SmtpEmailSender`** — `aiosmtplib` to `SMTP_HOST:SMTP_PORT`; used in staging and when no SaaS provider is configured.
- **`NullEmailSender`** — no-op; used when `EMAIL_ENABLED=false` or in unit tests.
- Optional SaaS adapters (SendGrid, SES, Postmark) implement the same Protocol behind `EMAIL_PROVIDER`.

**Per-locale templates (see §11.6):** Each email has a directory `app/templates/email/<template_id>/`, with one subdirectory per enabled locale (`en/`, `ar/`) containing `subject.j2`, `html.j2`, and `txt.j2`. The renderer:
- Resolves the locale (explicit arg → caller-provided context → `LOCALE_DEFAULT`).
- Falls back to `LOCALE_FALLBACK` (and emits a `email_locale_fallback_total` counter) if a locale-specific template is missing.
- For **RTL locales** (`RTL_LOCALES`), the HTML template inherits a base layout that sets `<html lang="..." dir="rtl">` and right-aligns the body; LTR locales get `dir="ltr"`.

**Local / dev:** MailHog or Mailpit (Docker) on port 1025 (SMTP) and UI on 8025; `docker-compose.yml` includes `mailhog` or `mailpit` so developers can inspect messages without sending real mail.

**Prod:** TLS + authenticated SMTP or provider API keys from secrets; **never** log bodies or recipient lists at INFO; audit sends at DEBUG with redaction.

**Testing:** Integration tests assert against MailHog API or use `NullEmailSender` / captured `list` fake; never send real mail in CI. Email tests parameterize over `LOCALES_ENABLED` and assert subject + body + `dir=` attribute (see §11.11).

### 10.5 Celery Beat: single scheduler, multi-worker safe, no overlapping runs

Production runs **many API replicas** and **many Celery workers**, but **scheduled work must run on exactly one schedule tick globally**, and **two workers must not execute the same cron body concurrently**.

**Beat process (scheduler):**
- Exactly **one** Beat process is active in production (`SERVICE_ROLE=beat`). On Render, define a **Background Worker** (or equivalent) with **instance count fixed to 1** and start command `celery -A app.workers.celery_app beat ...`.
- API containers (`SERVICE_ROLE=web`) and Celery worker containers (`SERVICE_ROLE=worker`) **must not** start Beat.
- Schedule definitions live in `app/workers/beat_schedule.py` and are reviewed like migrations.

**Multi-region / multi-server agnostic (misconfiguration-resistant):**
- If a platform mistake ever runs **two** Beat processes, **periodic task handlers** still acquire a **distributed lock** in Redis before doing work:
  - Key: `{CELERY_CRON_LOCK_PREFIX}:{task_name}:{rounded_minute_or_slot}` (or use Celery's `task.request.delivery_info` + stable window).
  - Implement with `SET key NX EX TTL` where `TTL ≥` max expected task duration (`CELERY_CRON_LOCK_TTL_SECONDS`).
  - If lock not acquired, the task **returns immediately** (log at INFO: "cron skipped, leader elsewhere").
- Optional **RedBeat** (`CELERY_BEAT_SCHEDULER=redbeat.RedBeatScheduler`) stores the schedule in Redis so Beat is stateless on disk; it does **not** replace the need for per-task locks — it complements ops.

**Overlap of long-running crons:** Even with one Beat, the next tick can fire if the previous run exceeded the interval. Locks above prevent concurrent execution; alternatively use `celery.schedules` with `relative=True` or track `last_run_at` in Redis.

**Local dev:** Beat may run in the same Compose stack as workers; locks still enabled so behavior matches prod.

---

## 11. Internationalization (i18n) & Localization (l10n)

### 11.1 Scope & Goals

- Backend supports multiple **content locales** for user-facing text. Initial enabled set: **English (`en`)** and **Arabic (`ar`)**.
- Translatable surfaces:
  - API error messages (`error.message` in the §9.1 envelope).
  - Pydantic validation messages.
  - Pagination labels and any server-rendered text.
  - Email subjects and bodies (HTML + text).
  - Audit/notification copy that reaches users (push, SMS adapters when added).
- Locale-aware formatting via Babel: dates, times, numbers, currencies, plural rules.
- **Architecture is unchanged**: i18n is a cross-cutting concern threaded through DI (a `Translator` Protocol), never a domain-layer detail. No `if locale == "ar":` branches in services.
- **Frontend RTL UI rendering is out of scope** (frontend's responsibility). Backend supplies the right `Content-Language`, locale-correct copy, and `dir`-aware HTML email bodies.

### 11.2 Locale Resolution (priority)

Resolved by `LocaleMiddleware` (request scope) and `get_current_locale` dependency. First match wins:

1. **Explicit query parameter** — `?{LOCALE_QUERY_PARAM}=ar` (e.g. `?lang=ar`). Useful for testing and shareable URLs. Disabled by setting `LOCALE_QUERY_PARAM=""`.
2. **Authenticated user preference** — `User.locale` column (introduced per project; the boilerplate ships only the resolver hook + interface).
3. **`Accept-Language` header** — RFC 5646 BCP-47, quality-weighted negotiation against `LOCALES_ENABLED`.
4. **`LOCALE_DEFAULT`** fallback.

The resolved locale is:
- Stored in `request.state.locale`.
- Bound to structlog `contextvars` (`locale=...`) so every log line is locale-tagged.
- Echoed in the response as `Content-Language: <locale>`.
- Available via `Annotated[str, Depends(get_current_locale)]` for routers and inner deps.
- Propagated **explicitly as a primitive kwarg** to every Celery task that produces user-facing output.

### 11.3 Translator Protocol & DI

Defined in `app/core/i18n.py`:

```python
class Translator(Protocol):
    def gettext(self, key: str, *, locale: str | None = None, **params) -> str: ...
    def ngettext(self, singular: str, plural: str, n: int, *, locale: str | None = None, **params) -> str: ...
    def format_datetime(self, dt: datetime, *, locale: str | None = None, format: str = "medium") -> str: ...
    def format_number(self, value: int | float | Decimal, *, locale: str | None = None) -> str: ...
    def format_currency(self, amount: Decimal, currency: str, *, locale: str | None = None) -> str: ...
    def is_rtl(self, locale: str) -> bool: ...
```

- **Default impl:** `BabelTranslator` backed by `babel.support.Translations.load(LOCALE_DIR, [locale, fallback], LOCALE_DOMAIN)`.
- **Test impl:** `EchoTranslator` (returns the key unchanged) — lets unit tests assert "this code path used translation key X" without depending on catalog content.
- **DI:** registered in `app/core/container.py` as `get_translator()` (`@lru_cache(maxsize=1)`); injected into services via constructor and into Celery tasks via the same DI factories.

### 11.4 Translation catalogs (gettext)

Layout:

```
app/locales/
  messages.pot                       # source template, regenerated by extract
  en/LC_MESSAGES/messages.po         # editable source, committed
  en/LC_MESSAGES/messages.mo         # binary, generated; built in Docker / committed per project policy
  ar/LC_MESSAGES/messages.po
  ar/LC_MESSAGES/messages.mo
babel.cfg                            # extraction patterns (Python + Jinja2)
```

Workflow:

1. **Mark strings** with `_("key")` (alias for `translator.gettext`) or `N_("key")` for deferred translation; in Jinja2 templates use `{{ _("key") }}`.
2. **Extract** to `messages.pot`: `pybabel extract -F babel.cfg -o app/locales/messages.pot app/`.
3. **Update** per-locale catalogs: `pybabel update -i app/locales/messages.pot -d app/locales/`.
4. **Translate** by hand or via translation tool — write into `.po` files.
5. **Compile** to binary: `pybabel compile -d app/locales/`.

CI runs steps 2 and 5 and asserts:
- No untranslated keys above `LOCALE_TRANSLATION_COMPLETENESS_MIN` for any enabled locale.
- All catalogs compile cleanly.
- `messages.pot` is in sync with the source (no drift).

### 11.5 Domain errors → translated messages

- `DomainError.message` is treated as the **gettext key** (English source serves as both default and key).
- `DomainError.details` is the templating params dict used by the translator (e.g., `gettext("Widget %(widget_id)s does not exist", widget_id=...)`).
- The exception handler in `app/core/exceptions.py` translates at the boundary:
  ```
  envelope.error.message = translator.gettext(error.message, locale=request.state.locale, **error.details)
  ```
- `error.code` is **always** locale-independent (`WIDGET_NOT_FOUND`); clients programmatic-match on `code`, humans read `message`.
- Pydantic validation errors are localized by mapping known error types (`type=greater_than`, `type=string_pattern_mismatch`, …) to translated templates in the same handler.

### 11.6 Email per locale (see also §10.4)

- Layout: `app/templates/email/<template_id>/<locale>/{subject.j2, html.j2, txt.j2}`.
- The renderer resolves locale → loads the correct subdir → falls back to `LOCALE_FALLBACK` if missing (with metric).
- HTML emails extend a base layout that sets `lang="..." dir="rtl|ltr"` based on `Translator.is_rtl(locale)`.
- Subject is its own template so it's localizable independently of body and never contains PII.

### 11.7 Celery task locale propagation

- Domain **events** are facts and do **not** carry locale (rendering context is not a property of the fact).
- The **task wrapper** that produces user-facing output accepts an explicit `locale` kwarg.
- Publisher passes the **resolver's locale** at publish time as a separate task arg (e.g., `celery_app.send_task("events.on_user_registered_send_welcome_email", kwargs={"event": payload, "locale": locale})`).
- Workers bind `locale` to structlog contextvars and Translator at task entry; clear on exit.
- For tasks **not** producing user output (data backfills, cron cleanups), no locale is passed.

### 11.8 Pluralization

- Use `ngettext` for cardinality-sensitive copy. Never construct plural strings via `%s` and string concatenation.
- **Arabic has 6 plural forms** (zero, one, two, few, many, other). Babel ships CLDR plural rules; never hand-roll them.
- `messages.po` for `ar` MUST declare `Plural-Forms: nplurals=6; plural=(...)` (Babel writes this when the catalog is created).

### 11.9 RTL responsibilities (backend only)

- `Content-Language` response header set so frontends can flip layout.
- HTML emails: base layout switches `dir` and `lang`; CSS provides RTL-friendly defaults (right-aligned text, mirrored padding).
- Plain-text emails: text is rendered as-is by the recipient's MUA.
- Backend never tries to "RTL-ify" arbitrary user-supplied content.

### 11.10 Hard rules

- ❌ NEVER hardcode user-visible strings in routes or services. Use translator keys.
- ❌ NEVER format user-visible numbers/dates/currencies with f-strings. Use `Translator.format_*`.
- ❌ NEVER concatenate translated fragments with `+`/`%s`; use a single key with named params so plural rules and word order remain correct.
- ❌ NEVER read `Accept-Language` directly inside a handler. Go through `get_current_locale`.
- ❌ NEVER carry locale on a domain event payload. Pass it as a separate task kwarg.
- ❌ NEVER `compile` `.po` files in the request path. Compile at build/deploy time.
- ❌ NEVER add `if locale == "ar":` branches to business code. All locale-specific behavior lives in catalogs and templates.
- ✅ Adding a new locale = add to `LOCALES_ENABLED`, copy the catalog, translate, ship — no app code changes.

### 11.11 Testing

- **Unit:** inject `EchoTranslator`; assert that user-facing code paths called the translator with the expected key and params.
- **Integration / API:** parameterize over `LOCALES_ENABLED`; assert `Content-Language`, `error.message`, and email body per locale.
- **Catalog hygiene (CI gate `make i18n-check`):**
  - Every key in `messages.pot` exists in every catalog.
  - Translation completeness ≥ `LOCALE_TRANSLATION_COMPLETENESS_MIN`.
  - All catalogs compile cleanly (`pybabel compile`).
  - `messages.pot` is in sync with the source (re-extract → no diff).

### 11.12 Operational notes

- `.po` files are committed; `.mo` files are generated (and either committed or built in the Dockerfile — pick one stance per project, document in ADR).
- Catalog edits are reviewed like code (PR diff on `.po`). Translations submitted by non-engineers go through a review PR.
- Production never recompiles catalogs from request data; catalogs are immutable per build.
- Monitoring: `i18n_missing_key_total{locale,key}` counter for any miss; alert when sustained.

---

## 12. Security Requirements

1. **Input validation** — all bodies via Pydantic; reject extra fields (`extra='forbid'`).
2. **Output validation** — `response_model` on every route; never return raw ORM objects.
3. **Authentication** — JWT bearer tokens when `AUTH_ENABLED=true`; refresh-token flow with rotation.
4. **Authorization** — role / scope checks via dependency (`require_scopes("admin")`); never inline in handlers.
5. **Password hashing** — bcrypt via `passlib`, cost factor ≥ 12.
6. **CORS** — explicit origin allowlist from `APP_CORS_ORIGINS`. No wildcard in production.
7. **Trusted hosts** — `TrustedHostMiddleware` in production with `APP_TRUSTED_HOSTS`.
8. **Security headers** — `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Strict-Transport-Security` in prod, `Content-Security-Policy` (strict on `/docs`).
9. **Rate limiting** — global default + stricter per-route on auth/sensitive endpoints; Redis-backed.
10. **Secrets** — env vars only; never logged. Logger redactor masks `*_KEY`, `*_SECRET`, `password`, `token`, `authorization`.
11. **Input sanitization** — strip control characters; reject suspicious payloads at the edge.
12. **SQL injection** — only parameterized queries via SQLAlchemy; raw SQL allowed only with `text()` + bound params, reviewed.
13. **Mass assignment** — Pydantic schemas explicitly enumerate writable fields; never construct ORM objects from raw dicts.
14. **TLS** — terminated at Render's load balancer; HTTP→HTTPS redirect; HSTS in production.
15. **Dependency scanning** — `pip-audit` and `bandit` in CI; fail on high-severity CVEs.
16. **Secret detection** — `detect-secrets` in Git **pre-push** hook (Docker `dev`) + CI.
17. **Container hardening** — non-root user, read-only root FS where possible, minimal base image, no shell tools in final stage.
18. **Audit logging** — security-sensitive actions (login, role change, admin action) logged to a dedicated audit logger with non-redacted user ID + IP.
19. **Data retention** — defined per data class; PII retention < 90 days unless required.
20. **Compliance posture** — assume GDPR-style requirements: support data export and deletion via service methods (added per project).

---

## 13. Observability

### 13.1 Logging
- **Format:** JSON via `structlog`; one log = one JSON line on stdout. (`console` renderer allowed in local only.)
- **Required fields on every log:** `timestamp`, `level`, `logger`, `message`, `request_id`, `trace_id`, `span_id`, `app_env`, `app_version`, `service`.
- **Levels:** DEBUG only outside production; INFO default; ERROR includes stack trace; CRITICAL pages on-call.
- **No PII / secrets** — explicit redactor processor.
- **Sampling:** DEBUG sampled at 10% in staging; never sampled in local.
- **Correlation:** `request_id` generated by middleware (or accepted from `X-Request-ID`); propagated to all downstream calls and Celery tasks.

### 13.2 Metrics (Prometheus)
- HTTP: request count, latency histogram, in-flight gauge, error rate per route + status class.
- DB pool: active / idle / total connections, checkout wait time, statement duration histogram.
- Redis: command count, latency, error rate.
- Outbound HTTP per host: request count, latency, error rate, circuit breaker state.
- Celery: task count by name + state, queue depth, processing duration, retry count.
- Process: CPU, RSS, FDs, GC counts.
- Custom business metrics: registered via `app/core/metrics.py`; documented in code.

### 13.3 Tracing
- OpenTelemetry auto-instrumentation for FastAPI, SQLAlchemy, asyncpg, httpx, Redis, Celery.
- Manual spans around significant business operations.
- Sampler: parent-based, ratio configurable per env (default 10% in prod).
- Exporter: OTLP to configured collector.

### 13.4 Error Tracking
- Sentry with `release = APP_VERSION`, `environment = APP_ENV`.
- `before_send` hook strips PII and request bodies.
- Failed Celery tasks captured.
- Performance tracing tied to OTel via Sentry's W3C trace-context support.

### 13.5 Health & Readiness
- `/health` — always 200 if process is alive (Render liveness probe).
- `/ready` — 200 only when all required deps healthy AND not draining (Render readiness probe).
- Probes configured in `render.yaml` with appropriate `initialDelaySeconds`, `periodSeconds`, `timeoutSeconds`, `failureThreshold`.

### 13.6 Alerting (must exist before prod traffic)
- 5xx rate > 1% for 5m → page.
- p95 latency > SLO for 10m → ticket.
- DB pool saturation > 80% for 5m → ticket.
- Celery queue depth > N for 10m → ticket.
- Failed deploy / failed migration → page.

---

## 14. Performance Requirements (boilerplate baselines)

| Metric | Target |
|---|---|
| Cold start (container ready → `/ready` 200) | ≤ 5s |
| `/health` p95 | ≤ 5ms |
| `/ready` p95 | ≤ 50ms |
| Idle memory footprint | ≤ 200 MB |
| DB pool checkout p95 | ≤ 10ms |

> Domain endpoint SLOs are defined per project in its own PRD.

### 14.1 Tactics
- Singleton infra clients (DB engine, Redis pool, HTTP client) reused across requests.
- Connection pooling everywhere; no per-request client construction.
- Cache-aside on read-heavy lookups.
- Pagination required on all list endpoints; `page_size` ≤ 100.
- N+1 detection in tests via SQLAlchemy event hook; eager-load relationships explicitly.
- Async all the way down — no sync I/O on the request path.
- Avoid synchronous JSON serialization of huge payloads; stream when > 1 MB.

---

## 15. Testing Strategy

### 15.1 Layers
- **Unit** — services, repositories (with in-memory fakes), utils. Target: 85%+ coverage on `services/`. **No** real network, **no** dev database.
- **Integration** — DB + Redis + MailHog via **dedicated test containers** (`docker-compose.test.yml`); tests use `DATABASE_URL_TEST` / `REDIS_URL_TEST` only.
- **API** — `httpx.AsyncClient` against the FastAPI app with `app.dependency_overrides` for external integrations; database sessions point at the **test** engine when persistence is involved.
- **Contract** — every Protocol implementation runs the same test suite (Liskov check). For external APIs, recorded fixtures (vcrpy / saved JSON).
- **Smoke** — post-deploy hits `/ready` and a small set of canary endpoints.

### 15.2 Fixtures & Tooling (no touching dev data)
- **`conftest.py`** loads settings from `.env.test` (or env vars set by CI) so `DATABASE_URL` for pytest is **always** the test database URL — never reuse `DATABASE_URL` from `.env` meant for local dev.
- **Guardrail:** At session start, assert the DB host/name contains `_test` or matches an allowlist (e.g. `app_test`, `postgres_test`) so misconfiguration fails fast before truncating the wrong schema.
- DB fixture: create schema once per session (`alembic upgrade head` against test URL), then **transactional** or **truncation** strategy per test (savepoint + rollback preferred for speed).
- `Clock` Protocol injected so time-dependent code is deterministic.
- Fake implementations of every external Protocol live in `tests/fakes/`.
- `client` fixture applies dependency overrides and binds the app to the test session factory.

### 15.3 Factory-based seeders (mandatory pattern)

**Factories (`tests/factories/`):**
- Use **factory_boy** with `SQLAlchemyModelFactory` (or plain `Factory` for Pydantic DTOs) per aggregate.
- Subclass a project-wide `BaseFactory` that sets:
  - `Meta.sqlalchemy_session_factory` or session persistence strategy consistent with pytest fixtures.
  - Default **Faker** providers for names, emails, etc.
- Use **`factory.Trait`** and **`factory.Sequence`** for variants (e.g. `admin=True`, `email_verified=False`).
- Factories **never** import Flask/FastAPI; they only build models or dicts.
- **Lazy attributes** and **`RelatedFactory`** / **`SubFactory`** express graph creation (user → organization → membership).

**Seeders (`tests/seeders/`):**
- **Seeders orchestrate factories** into coherent scenarios — they are not a second ORM layer.
- Public functions: `seed_minimal(session)`, `seed_user_with_orders(session, n=3)`, etc.; return **typed dataclasses** or **named tuples** of created IDs for assertions.
- Seeders are used by **integration tests**, **API tests**, and optionally **local smoke scripts** — but **not** by production code.
- **Idempotent dev seed** (`scripts/seed_dev_data.py`) may call the same factory definitions with a different session factory (dev DB), keeping one source of truth for "what realistic rows look like."

**Rules:**
- Prefer **explicit** `build()` vs `create()` in unit tests: `build()` keeps tests free of DB when possible.
- Integration tests use `create()` / `create_batch()` after the DB fixture is active.
- Never duplicate field lists across tests — if five tests need a "paid invoice", add `seed_paid_invoice()` once.

### 15.4 Isolated test infrastructure (separate servers)

**Principle:** The **main application codebase** (`app/`) is unchanged for tests; only **configuration** (env vars) and **test-only modules** (`tests/`, `docker-compose.test.yml`) differ. No `if TESTING:` branches in business logic.

**`docker-compose.test.yml` defines:**
- `postgres_test` — separate volume, credentials, database name (`app_test`), non-conflicting host port (e.g. `5433:5432`).
- `redis_test` — separate logical DB indexes / port (e.g. `6380:6379`).
- `mailhog` (or Mailpit) — captures outbound mail for assertions.
- **No** `api` or `worker` service required for pytest; tests run **inside the `dev` service** (`docker/Dockerfile.dev`) via `docker compose -f docker-compose.test.yml run … dev pytest`, with DB/Redis reached using Compose service hostnames (`postgres_test`, `redis_test`). Local developer workflows may still load `.env.test` on the host for editor tooling only—the supported execution path is Docker.

**Workflow:**
1. `make setup ENV=test` (see §17.2) starts **only** the test stack.
2. CI runs the same Compose file: Bitbucket Pipelines builds `Dockerfile.dev` and runs `docker compose … run dev` for lint, security, i18n, and pytest (no `pip install` on the pipeline host).
3. pytest uses `DATABASE_URL_TEST` / `REDIS_URL_TEST`; workers use `CELERY_TASK_ALWAYS_EAGER=true` for unit layers or a dedicated `redis_test` broker for Celery integration tests.

**Result:** Developers can run the dev stack (`postgres`, `redis`, full app) and the test stack side by side without collisions; running tests **never** truncates or migrates the dev database.

### 15.5 Required CI Gates
- `ruff check` + `ruff format --check`.
- `black --check`.
- `mypy app` (strict).
- `bandit -r app`.
- `pip-audit`.
- `detect-secrets scan --baseline .secrets.baseline`.
- `pytest -m "not slow"` on every PR; full suite on `main`.
- Coverage gate: 80% global, 85% on `services/`.
- Migration round-trip test (`upgrade head` → `downgrade -1` → `upgrade head`).
- `.env.example` drift check.
- OpenAPI schema diff comment on PR.
- **Test isolation check:** pipeline fails if `DATABASE_URL` used in test job equals production patterns (e.g. contains `rds.amazonaws.com` without an explicit override flag).
- **i18n catalog check (`make i18n-check`, runs in the `dev` Docker image)** — `messages.pot` is in sync with sources, every catalog compiles, and translation completeness ≥ `LOCALE_TRANSLATION_COMPLETENESS_MIN` for every locale in `LOCALES_ENABLED`.

---

## 16. Code Quality

- **Black** line length 100.
- **Ruff** rules: `E,F,I,B,UP,SIM,N,RUF,ASYNC,S,PL,PT,TID,TCH`. `--fix` allowed locally (`make format`); CI runs `ruff check` + `ruff format --check`.
- **mypy** in strict mode for `app/` (no untyped defs, no implicit Optional, `--warn-redundant-casts`, `--warn-unused-ignores`).
- **Docstrings** — Google style; required on public APIs of services, repositories, and core modules.
- **Git hooks** (`docker/.githooks/` copied to `.git/hooks/`): **commit hook** runs **`make git-hooks-commit`** (lint + **`check-env`**); **pre-push hook** runs **`make git-hooks-push`** (same sequence as **`make ci-local`** — lint, audit, **`check-env`**, **`i18n-check`**, **`test`**). **`GIT_HOOKS_PUSH_QUICK=1`** runs **`git-hooks-push-quick`** (no pytest). No third-party **pre-commit** Python package or `.pre-commit-config.yaml`.
- **Conventional Commits** for messages (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `perf:`, `build:`, `ci:`) — enforced via PR title check.
- **Branching** — short-lived feature branches off `main`; squash-merge; protected `main`.
- **Code review** — at least one approval; CODEOWNERS for sensitive paths (`app/core/`, `alembic/`, `render.yaml`).
- **PR template** with: change summary, motivation, screenshots if API change, migration note, rollback plan, observability impact.
- **ADRs** (Architecture Decision Records) — `docs/architecture-decisions/NNNN-title.md` for any decision that's hard to reverse.

---

## 17. Local Development Setup

### 17.1 Prerequisites
- Docker + Docker Compose v2
- Make (Git Bash / WSL on Windows)
- Optional local Python 3.14 for IDE / editor resolution only; **all** supported developer and CI commands for `pytest`, `ruff`, `mypy`, Babel, and security scanners go through **`make` → Docker** (`docker/Dockerfile.dev` + `docker-compose.test.yml` service `dev`)
- Optional: `uv` on the host only if you maintain `uv.lock` manually; `make install` builds the dev image from the lockfile without a host venv

### 17.2 Unified DX: one command for dev, test, and production roles

**Canonical entrypoint:** every environment is prepared through **`make setup`** (single command). `make bootstrap` remains an **alias** for `make setup ENV=local` for backwards compatibility.

```bash
# Local development — full stack on your machine (Postgres, Redis, MailHog, API, workers, Beat)
make setup ENV=local

# Automated tests — isolated Postgres/Redis/Mail; pytest runs in the dev tool container (not the production app image)
make setup ENV=test

# Production process — does not start Docker Compose on a laptop; selects container command by role
make setup ENV=production SERVICE_ROLE=web      # in Render Web Service start command
make setup ENV=production SERVICE_ROLE=worker   # in Render Background Worker (Celery worker)
make setup ENV=production SERVICE_ROLE=beat     # in Render Background Worker (Celery Beat, replicas=1)
```

**Behavior matrix**

| `ENV` | What runs locally | App / infra touched |
|---|---|---|
| `local` | `docker compose` **default** file: `postgres`, `redis`, `mailhog` (or Mailpit), `api`, `worker`, `beat` | Uses `.env`; **main code unchanged** |
| `test` | `docker compose -f docker-compose.test.yml up -d` → `postgres_test`, `redis_test`, `mailhog` (+ `dev` image for `make test`) | `make test` runs `pytest` **in the `dev` container** with Compose-scoped DB URLs; **never** uses dev DB URLs |
| `production` | No Compose (on Render: platform already provides managed Postgres + Redis) | `docker-entrypoint.sh` reads `SERVICE_ROLE` and execs **only** `gunicorn` (web), `celery worker` (worker), or `celery beat` (beat). Migrations run in a **pre-deploy job**, not in the web container startup unless explicitly allowed. |

**`make setup` implementation checklist (Makefile + `scripts/setup_env.sh`):**
1. Validate `ENV` ∈ {`local`, `test`, `production`}.
2. Verify `docker` / `docker compose` when `ENV≠production` or when `CI=true` with Compose-based services.
3. Copy `.env.example` → `.env` if missing (**local** only); never overwrite existing.
4. **local:** `docker compose build` → up infra → wait for health → `alembic upgrade head` (dev DB) → optional seed → up `api worker beat mailhog`.
5. **test:** ensure `.env.test` exists → `docker compose -f docker-compose.test.yml up -d` → wait for health → run **pytest inside the `dev` service** (`make test` / same in CI); document that host `pytest` is not a supported path.
6. **local** and **test:** after stack is ready, run `scripts/install_git_hooks.sh` (best-effort, **copy-only** — no Docker build): copy **`docker/.githooks/pre-commit`** and **`docker/.githooks/pre-push`** into **`.git/hooks/`** (executable). Installed hooks invoke **`make git-hooks-commit`** / **`make git-hooks-push`** from the repo root (**`make install`** separately builds the `dev` image for when those hooks run). **no host Python** for quality tools. Does not block setup if not a Git repo or templates missing; **`make install-git-hooks`** enforces a successful copy.
7. **production:** validate required secrets / `SERVICE_ROLE` → print the command line Render should use (no-op locally) **or** in the container entrypoint, branch on `SERVICE_ROLE` only — **application business code stays identical** across roles.

**Rule:** No developer should need to remember three different setup stories; documentation and README only advertise `make setup ENV=…`.

### 17.3 First-Run (equivalent invocations)
```bash
make setup ENV=local
# same as: make bootstrap
```

Steps performed for **`ENV=local`** (see `scripts/setup_env.sh` for the exact sequence in this repo):
1. Verify required tools (`docker`, `docker compose`, `make`).
2. Copy `.env.example` → `.env` if missing.
3. `docker compose build` and bring the stack up; wait for Postgres; `alembic upgrade head` against the dev DB.
4. **Git hooks:** run `scripts/install_git_hooks.sh` — copy **`docker/.githooks`** → **`.git/hooks`** only; skipped if not a clone (no `.git`) or templates missing (does not fail setup).
5. Print accessible URLs (API, MailHog).

### 17.4 Standard Make Targets (required)

All targets below that run application or quality tools are implemented with **Docker** (`docker compose` + `Dockerfile.dev` for linters/tests, `docker/Dockerfile` for the local app stack). `make` is a thin wrapper so documentation stays one line per action.

```
make setup ENV=local|test|production   # unified entry (see §17.2)
make install / make build-dev          # build the `dev` image (Dockerfile.dev)
make up / make down / make logs        # local dev stack (docker-compose.yml)
make run / make worker / make beat     # hints or tail worker/beat logs
make api-shell                         # sh in the api container
make migrate / make migration MSG=… / make downgrade   # alembic via `api` (dev stack up)
make test / make test-all / make test-unit / make test-int / make cov   # pytest in `dev` + test stack
make lint / make format / make typecheck                 # ruff + black + mypy in `dev` (--no-deps)
make audit                             # pip-audit, bandit, detect-secrets in `dev`
make check-env / make openapi          # drift + OpenAPI dump in `dev`
make i18n-extract|update|compile|check # Babel / i18n_check in `dev`
make new-locale LOCALE=xx              # pybabel init in `dev`
make install-git-hooks / precommit-install   # copy docker/.githooks → .git/hooks only; no Docker (required success; alias)
make ci-local                          # lint + audit + i18n-check + test (all Docker)
make build                             # production image (docker/Dockerfile)
make test-up / make test-down          # test compose only
make clean                             # dev + test compose down -v
```

### 17.5 docker-compose.yml Services (development)
- `api` — FastAPI (Uvicorn, `--reload` in local via override file); `SERVICE_ROLE=web` inside container.
- `worker` — Celery worker (concurrency=2 in local); `SERVICE_ROLE=worker`.
- `beat` — Celery Beat; `SERVICE_ROLE=beat`.
- `postgres` — Postgres 18 with named volume + `pg_stat_statements` enabled.
- `redis` — Redis 8 with appendonly persistence.
- `mailhog` or `mailpit` — SMTP sink (1025) + UI (8025) for email development.
- (optional, behind `--profile observability`) `prometheus`, `grafana`, `otel-collector`, `jaeger`.

All services share a bridge network, declare healthchecks, depend on each other with `condition: service_healthy`, and use `restart: unless-stopped`.

### 17.6 Developer Endpoints (local)
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json
- Health / Ready / Metrics: http://localhost:8000/health , `/ready`, `/metrics`
- Postgres: localhost:5432 (app/app)
- Redis: localhost:6379
- MailHog UI: http://localhost:8025 (or Mailpit equivalent)
- Test Postgres (when test stack up): localhost:5433 (example mapping)
- Test Redis: localhost:6380 (example mapping)
- (optional) Grafana: http://localhost:3001 , Jaeger: http://localhost:16686

### 17.7 Developer Experience
- VS Code devcontainer config (`.devcontainer/`) optional but recommended.
- `.editorconfig` enforces line endings, indentation, charset.
- **Commit / pre-push hooks:** `make setup ENV=local|test` runs `scripts/install_git_hooks.sh` (best-effort copy only). Templates: **`docker/.githooks/`** → **`.git/hooks/`**. Hooks execute **`make git-hooks-commit`** (commit) and **`make git-hooks-push`** (pre-push; mirrors **`make ci-local`**). **`make install-git-hooks`** (alias **`precommit-install`**) performs the same copy with required success — **no** **`make install`**. **CI** uses the same **Makefile**-backed commands.
- `AGENTS.md` documents AI assistant conventions for the repo.
- `make i18n-extract && make i18n-compile` runs as part of `make setup ENV=local` so a fresh clone has compiled `.mo` catalogs ready (idempotent; no-op when up to date).
- README has a "5-minute quickstart" section that mentions **only** `make setup ENV=local` + a "common pitfalls" section (wrong `ENV`, pytest pointing at dev DB, missing `.mo` after editing `.po`).

---

## 18. Production Deployment (render.com)

### 18.1 Build
- Multi-stage Dockerfile:
  1. `builder` — installs runtime deps from `uv.lock` via `uv export --frozen` + `pip install -r`; compiles gettext catalogs (`pybabel compile -d app/locales/`) so `.mo` files are deterministic per build. A separate **`Dockerfile.dev`** image (same lockfile, all extras) is used for local and CI tooling only.
  2. `runtime` — slim base image, non-root user `app`, copies installed deps from the builder to `/usr/local`, plus `app/` (including compiled `app/locales/**/messages.mo`), `app/templates/`, `alembic/`, `pyproject.toml`, and entrypoint scripts.
- Image labels: `org.opencontainers.image.revision = <git_sha>`, `version = <APP_VERSION>`.
- Same image runs `api`, `worker`, `beat` — entry command differs.
- Image scanned (`trivy` or Render's built-in scan) — fail on high-severity CVEs.

### 18.2 Runtime Topology (defined in `render.yaml`)

**Application processes in production** — only **FastAPI (web)** and **Celery** workloads run as your code. **PostgreSQL** and **Redis** are **managed platform services** (not containers in your Compose file): connection strings come from Render / Upstash secrets.

| Render service type | `SERVICE_ROLE` | Scale | Start command (conceptual) |
|---|---|---|---|
| **Web Service** | `web` | ≥ 2 | `make setup ENV=production SERVICE_ROLE=web` → `gunicorn` + `UvicornWorker` |
| **Background Worker** | `worker` | ≥ 1 | `celery -A … worker` |
| **Background Worker** | `beat` | **exactly 1** | `celery -A … beat` |

All three use the **same container image**; only `SERVICE_ROLE` (and Render's start command) differ. This matches the requirement that **horizontal scaling adds web + worker replicas only**, while **Beat never scales beyond one instance** (see §10.5 for Redis locks if misconfigured).

- **PostgreSQL**: Render Managed Postgres, automated backups, PITR.
- **Redis**: Render Managed Redis (or Upstash) — broker, result backend, cache, cron locks, optional RedBeat.
- **Pre-deploy job**: `alembic upgrade head` — deploy gated on success.
- **Render Cron Jobs** — avoid duplicating Celery Beat schedules here; use Beat + locks as the single source of truth for in-app periodic tasks unless an ADR documents an exception (e.g. one-off maintenance that must not touch the app image).

### 18.3 Deploy Pipeline (Bitbucket Pipelines → Render)
1. **CI on PR**: lint → typecheck → security scan → test → build (no push).
2. **Main merge**: build → push image → trigger Render deploy → Render runs pre-deploy migration → rolling deploy → smoke test `/ready` → mark release in Sentry.
3. **Migration step** is idempotent and backward-compatible (see §6.4).
4. **Rollback**: redeploy previous tagged image; migrations are forward-only and backward-compatible so the old image keeps working. Document rollback in the runbook.
5. **Release tagging**: git tag `v<APP_VERSION>` on every prod deploy.

### 18.4 Configuration in Prod
- All `*_API_KEY`, `SECRET_KEY`, DB credentials from Render Secret Manager, injected as env at runtime.
- `APP_DEBUG=false`, `APP_LOG_LEVEL=INFO`, `APP_DOCS_ENABLED=false` (or admin-gated).
- CORS restricted to known frontend origins.
- `APP_TRUSTED_HOSTS` set to known domains.
- `/metrics` protected by `METRICS_ENDPOINT_AUTH_TOKEN`.

### 18.5 Operational Runbooks (must exist in `docs/runbooks/`)
- DB outage / failover.
- Redis outage.
- Failed deploy / failed migration rollback.
- Re-running a failed background job.
- Rotating a leaked secret.
- Scaling up/down.
- Restoring from backup.
- Incident response template (severity, comms, post-mortem).

### 18.6 Backups & DR
- DB: daily full + PITR 7 days (Render-managed).
- Quarterly restore drill — documented.
- RTO target: ≤ 1 hour. RPO target: ≤ 15 minutes.

### 18.7 Environments
- `local` — developer machines via Docker Compose.
- `dev` — shared, auto-deploy from `develop` (optional).
- `staging` — auto-deploy from `main`, mirrors prod config, used for final smoke + load tests.
- `production` — manual promote from staging or auto on green main, depending on release policy.

---

## 19. Definition of Done (for the boilerplate)

The boilerplate is "production-ready" when **all** of the following are true:

1. `make setup ENV=local` (and alias `make bootstrap`) works on a clean Mac/Linux/Windows-WSL machine and yields a running dev stack including MailHog/Mailpit.
2. `make setup ENV=test` brings up isolated `postgres_test` / `redis_test` / mail sink; `make test` never targets the dev database (guardrail in `conftest.py`).
3. `GET /health`, `/ready`, `/metrics`, `/api/v1/health`, `/api/v1/ready` all behave per spec.
4. CI pipeline is green and enforces every gate listed in §15.5 (including test DB isolation checks).
5. Production deploy via Bitbucket Pipelines → render.com succeeds with zero manual steps; **only** Web + Celery worker + Celery Beat (replica 1) run application code; DB/Redis are managed.
6. `/ready` returns 200 only when all required deps are healthy and not draining.
7. Logs are JSON, metrics scrape, traces export to a configured backend.
8. `.env.example` is complete; `.env` is gitignored; no secrets in git history (verified by `detect-secrets` and `gitleaks`-equivalent scan).
9. SOLID / DRY / KISS / YAGNI documented and reflected in code: a sample service, repository, and integration demonstrate the patterns end-to-end.
10. Dependency Injection is used for every external dependency; tests prove every dep is overridable.
11. **Factory + seeder** modules exist under `tests/factories/` and `tests/seeders/` with at least one reference scenario used by integration tests.
12. **Domain events** can be published from a service and consumed by a Celery listener task without importing FastAPI in the worker path.
13. **Email** can be sent via `EmailSender` in dev (MailHog) and disabled or stubbed in tests without code changes to business logic (config + DI only).
14. Celery Beat schedules use **Redis distributed locks** so duplicate schedulers or overlapping ticks do not double-run cron bodies (§10.5).
15. **i18n / l10n is end-to-end functional (§11):** `LOCALES_ENABLED=["en","ar"]` works without code changes; `Accept-Language` and `?lang=` resolve correctly; `Content-Language` echoed; `error.message` and at least one email template are translated for both `en` and `ar`; HTML emails for Arabic render with `dir="rtl"`; `make i18n-check` passes; CI fails on translation completeness below `LOCALE_TRANSLATION_COMPLETENESS_MIN`.
16. Graceful shutdown verified by integration test.
17. Runbooks exist for every external dependency failure mode.
18. ADRs exist for every locked technology choice in §2.

---

## 20. Out of Scope (boilerplate)

- Domain data models, schemas, repositories, services, and endpoints (added per project).
- Frontend / UI.
- **Frontend RTL UI rendering** — backend ships `Content-Language`, locale-correct copy, and `dir`-aware HTML email bodies (§11.9); flipping the web/mobile UI layout is the frontend's responsibility.
- **Translation tooling / TMS integration** (e.g., Crowdin, Lokalise, Phrase) — boilerplate ships `.po` files committed in git; integrate with a TMS per project if needed.
- **Locales beyond English and Arabic** — the architecture supports adding more locales (just add to `LOCALES_ENABLED` + a catalog), but only `en` and `ar` are enabled out of the box.
- **Per-locale content moderation / language detection on user input** — added per project if needed.
- Multi-region active-active deployment.
- Multi-tenant isolation primitives (added per project if needed).
- gRPC / GraphQL layers (HTTP/REST + JSON only by default).
- Native mobile SDKs.
- ML training pipelines.

---

## 21. Open Decisions (finalized)

1. **ORM model layer vs domain entity layer** — does the project need a separate domain model distinct from ORM models, or are ORM models the domain? Default: ORM-as-domain for simple CRUD services; separate layer when business logic is rich.
2. **Primary-key strategy** — UUID v7 vs BIGSERIAL — decide per service based on write volume and external exposure.
3. **Auth provider** — in-house JWT vs OIDC (Auth0 / Clerk / Cognito). Default in this doc: in-house JWT, AUTH_ENABLED=false until needed.
4. **Cache layer** — Redis only vs Redis + in-process LRU. Default: Redis only.
5. **Tracing backend** — Jaeger / Tempo / Sentry / Datadog. Default: OTel collector → vendor-agnostic.
6. **Queue technology** — Celery (default) vs Arq vs Dramatiq vs RQ. Default: Celery for parity with existing infra.
