---
description: Create a backward-compatible Alembic migration following the deploy-safe playbook.
---

# /new-migration

Author an Alembic migration that can deploy alongside the **previous** image without breaking it.

## Steps

1. Update SQLAlchemy models under `app/models/`.
2. Generate a draft migration (the test stack must be up so `--autogenerate` reads a real DB):
   ```bash
   make migration m="<ticket-id>: short slug"
   ```
3. **Review the generated script.** Autogenerate is a starting point, not a finished product.
4. Apply the migration locally and against the test DB:
   ```bash
   make migrate
   ```
5. Verify the round trip:
   ```bash
   make migrate-down
   make migrate
   ```
6. Add the migration to the same PR as the model change.

## Backward-compatibility playbook (architecture spec §6.4)

| Change | Two-step path |
|---|---|
| Add a column | Add nullable / with default → backfill → make `NOT NULL` in a later release. |
| Rename a column | Add new column → dual-write → backfill → switch reads → drop old. |
| Drop a column | Stop writing → release → drop in a later release. |
| Change type | Add new column with new type → dual-write/migrate → switch reads → drop old. |
| Add an index | Use `CREATE INDEX CONCURRENTLY` (raw `op.execute(...)`) on hot tables. |

## Hard rules

- **Forward-only in production**; downgrade is for staging/local only.
- **No data migrations inside DDL migrations** if backfill is large. Do it as a Celery task or a one-shot Render job.
- **Naming convention is enforced** (`MetaData(naming_convention=...)`); never bypass it.
- Filename includes ticket ID + short slug. Conventional Commit message: `feat(db): ...` or `chore(db): ...`.
- CI runs `upgrade head → downgrade -1 → upgrade head` against a fresh DB; both directions must succeed.

## Linked rules

- `.cursor/rules/alembic-migrations.mdc`
- `.cursor/rules/sqlalchemy-async.mdc`
