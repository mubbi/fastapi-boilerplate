---
description: Bootstrap the full local development stack (API, workers, Beat, Postgres, Redis, Mailpit).
---

# /setup-local

Run the unified DX entrypoint for **local development**.

## Steps

1. Verify prerequisites: `docker --version`, `docker compose version`, **`make --version`** (hooks invoke **`make git-hooks-commit`** / **`make git-hooks-push`**). **Git hooks:** `docker/.githooks/` → **`.git/hooks`** via **`install_git_hooks.sh`** (no **`pre-commit`** Python package).
2. Run:
   ```bash
   make setup ENV=local
   ```
   This also runs `scripts/install_git_hooks.sh` (best-effort, copy-only). If hooks were skipped, run **`make install-git-hooks`**. Build the dev image with **`make install`** before the first commit that runs hook checks.
3. Confirm services are healthy:
   ```bash
   curl -s http://localhost:8000/ready | jq
   ```
4. Open the local endpoints listed in `docs/tech-architecture-requirements.md` §17.6.

## What this does (per the architecture spec §17.3)

- Copies `.env.example` → `.env` if missing.
- Builds images, brings up `postgres`, `redis`, `mailpit` first.
- Runs `alembic upgrade head` **via the `api` container** against the dev DB.
- Compiled `.mo` files come from the image build and Babel; use `make i18n-compile` in the `dev` container if you need to refresh catalogs from `.po` files on disk.
- Optionally seeds via `scripts/seed_dev_data.py`.
- Starts `api`, `worker`, `beat`.
- Copies **`docker/.githooks/`** to **`.git/hooks/`** via `install_git_hooks.sh` — hooks run **`make git-hooks-commit`** (commit) and **`make git-hooks-push`** (pre-push; **`GIT_HOOKS_PUSH_QUICK=1`** skips pytest).

## Common pitfalls

- **Wrong `ENV`** — only `local` brings up the full app stack.
- **Port conflicts** — make sure 8000/5432/6379/8025 are free, or update `.env`.
- **Stale `.env`** — if you added new vars to `.env.example`, copy them over manually; `make setup` does not overwrite an existing `.env`.
