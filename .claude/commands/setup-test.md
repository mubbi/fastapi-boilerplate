---
description: Bring up the isolated test stack (postgres_test, redis_test, mailhog) and run pytest.
---

# /setup-test

Start **only** the isolated test infrastructure and execute the test suite.

## Steps

1. Bring up the test stack (no app containers):
   ```bash
   make setup ENV=test
   ```
   This runs `docker compose -f docker-compose.test.yml up -d` and waits for healthchecks.
2. Run tests:
   ```bash
   make test                # full suite, loads .env.test
   make test-unit           # pytest -m unit
   make test-int            # pytest -m integration
   ```
3. Tear down when done:
   ```bash
   docker compose -f docker-compose.test.yml down -v
   ```

## Hard guarantees (architecture spec §15.3)

- Tests use `DATABASE_URL_TEST` and `REDIS_URL_TEST` **only**.
- `conftest.py` asserts the DB URL matches a `_test` allowlist; misconfig fails fast before any schema change.
- The dev stack (`docker-compose.yml`) is untouched and can run in parallel.
- No application code branches on "am I in a test"; only configuration and dependency overrides differ.

## i18n during tests

- `make setup ENV=test` runs `pybabel compile -d app/locales` so translations are available to integration / API tests.
- Tests **never assert on translated copy**. Assert on `error.code`, `Content-Language`, or structured fields. See `.cursor/rules/testing-pytest.mdc`.
- Run `make i18n-check` locally before pushing if you added user-visible strings.

## When to extend

- New domain models → add a Factory in `tests/factories/` (see `.cursor/rules/test-factories-seeders.mdc`).
- New scenario shared across tests → add a seeder function in `tests/seeders/`.
- New external integration → add a fake under `tests/fakes/` and a contract test under `tests/contract/`.
- New user-visible string → run `/new-translation` and ensure both `en` and `ar` `messages.po` are updated.
