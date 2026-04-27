# FastAPI Boilerplate

Production-grade FastAPI backend boilerplate with a strict layered architecture, full async stack, dependency injection, internationalisation (English + Arabic), and a single-command developer experience.

> **Read first:** [`docs/tech-architecture-requirements.md`](docs/tech-architecture-requirements.md) is the authoritative spec. The non-negotiable rules and the "I'm about to change X" cheat sheet live in [`CLAUDE.md`](CLAUDE.md) / [`AGENTS.md`](AGENTS.md). File-scoped guidance lives in [`.cursor/rules/*.mdc`](.cursor/rules).

---

## What you get

- **API layer**: FastAPI 0.115+ with strict Pydantic v2 schemas, structured exception envelope, OpenAPI docs.
- **Service layer**: business logic only; collaborators arrive via `Protocol` + DI.
- **Repository layer**: SQLAlchemy 2.0+ async (`asyncpg`), Alembic migrations, Postgres 16+.
- **Caching / locking**: Redis 7+, connection pool, distributed lock with safe-DEL Lua.
- **Background jobs**: Celery 5.4+ with Redis broker, multi-Beat-safe scheduled tasks.
- **HTTP client**: shared `httpx.AsyncClient` with `tenacity` retries.
- **Email**: per-locale Jinja2 templates, async SMTP (MailHog locally), `NullEmailSender` for tests.
- **Internationalisation**: Babel + gettext catalogs; English (default + fallback) and Arabic (RTL) ship enabled.
- **Observability**: structlog JSON logs (with redaction + OTel trace correlation), Prometheus metrics, OpenTelemetry tracing, optional Sentry.
- **Security**: bcrypt passwords, JWT helpers, rate limiting (slowapi), CORS, trusted hosts, security headers.
- **DX:** `make setup ENV=…` for every environment; **all** lint, typecheck, tests, i18n, and security checks run in **Docker** (locked `uv.lock` + `docker/Dockerfile.dev`). Bitbucket Pipelines uses the same pattern—no `pip install` on the runner.
- **Deploy:** multi-stage [`docker/Dockerfile`](docker/Dockerfile) (non-root runtime), [`bitbucket-pipelines.yml`](bitbucket-pipelines.yml) (Docker-based CI), [Render.com](https://render.com) blueprint in [`render.yaml`](render.yaml).

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
- [GNU Make](https://www.gnu.org/software/make/) (Git Bash / WSL on Windows)

> Optional: a local Python 3.14+ install is only for IDE / editor tooling. The supported path for `pytest`, `ruff`, `mypy`, and Babel is always the **dev** container: `make install` builds it; `make` targets run inside it.

## Quick start

```bash
# 1) Full dev stack: Postgres, Redis, MailHog, API, worker, Beat
make setup ENV=local

# 2) Open the app
open http://localhost:8000/docs    # Swagger
open http://localhost:8000/health    # Liveness
open http://localhost:8025           # MailHog UI
```

**Run tests (isolated test DB + dev tool image):**

```bash
make test          # or: make setup ENV=test  &&  make test
```

**Code quality (no host venv):**

```bash
make install       # build the dev image once (Dockerfile.dev + uv.lock)
make lint
make test
```

> Use Git Bash, WSL, or another environment where `make` and `bash scripts/setup_env.sh` behave like Unix. Pure PowerShell is not a supported `make` target shell.

## Project structure

```
app/
  api/v1/            # Routers (HTTP only)
  core/              # Config, logging, i18n, container, middleware, ...
  db/                # Engine, session, declarative base, mixins
  models/            # SQLAlchemy ORM (one file per aggregate root)
  schemas/           # Pydantic DTOs (request/response)
  repositories/      # Persistence layer
  services/          # Business logic / use cases
  integrations/      # External adapters (cache, email, http)
  events/            # Domain event types, registry, publisher
  workers/           # Celery app, beat schedule, tasks
  locales/           # gettext catalogs per locale
  templates/email/   # Per-template, per-locale Jinja2 emails
  utils/             # Pure helpers
alembic/             # Migrations
docker/              # Dockerfile, Dockerfile.dev, entrypoint, healthcheck
docs/                # Spec, ADRs, runbooks
tests/               # unit, integration, api, contract + factories/seeders/fakes
```

## Architecture rules (non-negotiable)

1. Strict layering: **Router → Service → Repository → Persistence**.
2. Routers never import repositories, integrations, or workers.
3. Services never import `fastapi.*` or raise `HTTPException`.
4. Repositories never `commit`/`rollback` and never call other repositories.
5. Every collaborator is a `Protocol` injected via constructor or `Depends`.
6. Async all the way down — no sync DB or HTTP on the request path.
7. Mypy strict; Pydantic v2 with `extra="forbid"` on requests.
8. Domain exceptions only; the global handler maps them to HTTP.
9. No hardcoded user-visible strings — every string flows through `Translator.gettext`.
10. Tests never touch the dev database; isolated stack only.
11. Migrations are backward-compatible (add → backfill → switch → drop).

## Common commands (all via `make` → Docker)

| Goal | Command |
|------|--------|
| Build dev image (linters, pytest, Babel) | `make install` |
| Local stack | `make setup ENV=local` / `make up` / `make down` |
| Tests | `make test`, `make test-all`, `make cov` |
| Migrations (dev DB, `api` service must be up) | `make migrate`, `make migration MSG="…"`, `make downgrade` |
| i18n | `make i18n-extract`, `make i18n-update`, `make i18n-compile`, `make i18n-check` |
| Security | `make audit` |
| Prod image | `make build` |

`make precommit-install` is the one exception: Git hooks run on your machine so the hook manager can read `.git`.

## Deploy

- **Render.com:** [`render.yaml`](render.yaml). Three services share one image; `SERVICE_ROLE` selects the entrypoint (`web` / `worker` / `beat`). Beat runs as exactly one replica. Migrations run in a pre-deploy job on the platform, not in ad-hoc shells.
- **CI:** [`bitbucket-pipelines.yml`](bitbucket-pipelines.yml) — `docker compose … run dev` for quality gates and tests; production image build for release.

## Documentation

- [`docs/tech-architecture-requirements.md`](docs/tech-architecture-requirements.md) — architecture spec
- [`docs/architecture-decisions/`](docs/architecture-decisions/) — ADRs (irreversible decisions)
- [`docs/runbooks/`](docs/runbooks/) — incident-response runbooks

## License

Proprietary. See `LICENSE` if/when added per project.
