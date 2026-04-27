---
description: Bootstrap the full local development stack (API, workers, Beat, Postgres, Redis, MailHog).
---

# /setup-local

Run the unified DX entrypoint for **local development**.

## Steps

1. Verify prerequisites: `docker --version`, `docker compose version`, `make --version`.
2. Run:
   ```bash
   make setup ENV=local
   ```
3. Confirm services are healthy:
   ```bash
   curl -s http://localhost:8000/ready | jq
   ```
4. Open the local endpoints listed in `docs/tech-architecture-requirements.md` §17.6.

## What this does (per the architecture spec §17.3)

- Copies `.env.example` → `.env` if missing.
- Builds images, brings up `postgres`, `redis`, `mailhog` first.
- Runs `alembic upgrade head` against the dev DB.
- Compiles gettext catalogs (`pybabel compile -d app/locales`) so translations are available at runtime.
- Optionally seeds via `scripts/seed_dev_data.py`.
- Starts `api`, `worker`, `beat`.

## Common pitfalls

- **Wrong `ENV`** — only `local` brings up the full app stack.
- **Port conflicts** — make sure 8000/5432/6379/8025 are free, or update `.env`.
- **Stale `.env`** — if you added new vars to `.env.example`, copy them over manually; `make setup` does not overwrite an existing `.env`.
