# 0003 — Celery Beat: single replica + Redis locks per scheduled task

- **Status:** Accepted
- **Date:** 2026-04-27
- **Decision drivers:** spec §7, [`.cursor/rules/celery-beat.mdc`](../../.cursor/rules/celery-beat.mdc)

## Context

Render free/standard plans run multiple worker replicas, but Celery Beat is process-based and cannot natively coordinate. Running multiple Beats causes duplicate scheduled tasks; running one Beat is a single point of failure for cron-style work. Render restarts can also briefly overlap an "old" Beat with a "new" one.

## Decision

- `beat` runs as **exactly one** Render service replica (declared in `render.yaml`).
- Every scheduled task body acquires a **Redis distributed lock** (`SET NX EX`) keyed on the task name before doing work, releasing it via the safe-DEL Lua script.
- Tasks are idempotent and accept primitive arguments only.

## Consequences

- A brief Beat overlap during deploys cannot cause double execution — the lock holds.
- Tasks remain safe even if a future operator accidentally scales `beat` to >1.
- Operators do not need to coordinate Beat redeploys with worker redeploys.

## Alternatives considered

- **`celery-redbeat`.** Rejected for the boilerplate baseline — adds another moving piece and a Redis schema we'd have to operate, while Beat-singleton + per-task locks already solves the problem.
- **Postgres-based scheduler.** Rejected — adds DB load and migration ceremony for a problem that Redis solves cleanly.
