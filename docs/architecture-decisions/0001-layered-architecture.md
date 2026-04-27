# 0001 — Layered architecture with strict imports

- **Status:** Accepted
- **Date:** 2026-04-27
- **Decision drivers:** spec §3, [`CLAUDE.md`](../../CLAUDE.md) §2

## Context

The boilerplate must remain readable and reviewable as the codebase grows. Without a structural rule, FastAPI projects drift into "router-knows-everything" or "service-imports-FastAPI" anti-patterns, which makes testing painful and makes future migrations (e.g. swapping cache, queue, or HTTP transports) effectively impossible.

## Decision

We enforce four layers and disallow upward / sideways imports:

```
Router (app/api/**) → Service (app/services/**) → Repository (app/repositories/**) → DB
                                ↓
                        Integration (app/integrations/**)
```

Hard rules:

- Routers MUST NOT import `app.repositories.*`, `app.integrations.*`, or `app.workers.*`.
- Services MUST NOT import `fastapi.*` or raise `HTTPException`.
- Repositories MUST NOT call `commit`/`rollback` or import other repositories.
- Integrations MUST NOT import services or repositories.

Every collaborator is a `Protocol` injected via constructor or `Depends`.

## Consequences

- Tests inject fakes for every collaborator without resorting to monkey-patching.
- Cross-cutting concerns (caching, retries, tracing) live in dedicated layers.
- New transports (e.g. swap Celery for Temporal, swap Redis for Memcached) are localised to one folder.
- We pay a small upfront cost in indirection for a much lower long-term cost in change.

## Alternatives considered

- **Hexagonal / clean architecture with explicit ports/adapters per use case.** Too heavy for this size of project; we converge on the same boundaries with less ceremony.
- **MVC with services as anemic helpers.** Rejected — it pushes business logic into routers, blocking real testing.
