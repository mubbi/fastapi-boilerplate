---
description: Bring up the isolated test stack (postgres_test, redis_test, mailpit_test) and run pytest in Docker.
---

# /setup-test

Start **only** the isolated test infrastructure and execute the test suite **inside the `dev` container** (same as CI).

## Steps

1. Bring up the test stack and build the dev image if needed:
   ```bash
   make install          # once: docker compose … build dev
   make setup ENV=test   # test stack + install_git_hooks.sh (copy hooks, best-effort)
   ```
2. Run tests (pytest never runs on the host in the supported path):
   ```bash
   make test                # quick suite (excludes `slow`)
   make test-all
   make test-unit           # pytest -m unit
   make test-int            # pytest -m integration
   ```
3. Tear down when done:
   ```bash
   make test-down
   # or: docker compose -f docker-compose.test.yml down -v
   ```

## Hard guarantees (architecture spec §15.2 and §15.4)

- Tests use `DATABASE_URL_TEST` and `REDIS_URL_TEST` **only**; inside the `dev` container these resolve to `postgres_test` and `redis_test` on the Compose network.
- `conftest.py` asserts the DB URL matches a `_test` allowlist; misconfig fails fast before any schema change.
- The dev stack (`docker-compose.yml`) is untouched and can run in parallel.
- No application code branches on "am I in a test"; only configuration and dependency overrides differ.

## i18n during tests

- If you add user-visible strings, run `make i18n-extract` / `make i18n-check` (both use the `dev` image).
- Tests **never assert on translated copy**. Assert on `error.code`, `Content-Language`, or structured fields. See `.cursor/rules/testing-pytest.mdc`.

## When to extend

- New domain models → add a Factory in `tests/factories/` (see `.cursor/rules/test-factories-seeders.mdc`).
- New scenario shared across tests → add a seeder function in `tests/seeders/`.
- New external integration → add a fake under `tests/fakes/` and a contract test under `tests/contract/`.
- New user-visible string → run `/new-translation` and ensure both `en` and `ar` `messages.po` are updated.
