# ──────────────────────────────────────────────────────────────────
# Single-entrypoint developer experience. Tooling uses Docker only
# (locked dev image: docker/Dockerfile.dev + docker-compose.test.yml `dev` service).
#
#   make setup ENV=local       # full dev stack (api, worker, beat, postgres, redis, mailhog)
#   make setup ENV=test        # isolated test infra (see also: make test)
#   make setup ENV=production  # entrypoint hint for Render
#
# Production workloads run the image from docker/Dockerfile; quality gates use Dockerfile.dev.
# Git hooks: docker/.githooks → .git/hooks (copy-only via scripts/install_git_hooks.sh;
# also runs at end of make setup ENV=local|test). Hooks invoke Make → Docker when executed.
# ──────────────────────────────────────────────────────────────────

.SHELLFLAGS = -eu -o pipefail -c
SHELL := /bin/bash

ENV ?= local
LOCALE ?= en
COMPOSE_LOCAL := docker compose -f docker-compose.yml
COMPOSE_TEST  := docker compose -f docker-compose.test.yml
# dev image: all extras from uv.lock, repo mounted at /workspace
DEV  := $(COMPOSE_TEST) run --rm
DEV0 := $(COMPOSE_TEST) run --rm --no-deps dev
# $(1) = extra pytest arguments (e.g. -m unit). Empty runs the full suite.
dev-pytest = $(DEV) dev sh -ec 'APP_ENV=test pytest$(if $(strip $(1)), $(strip $(1)))'

.DEFAULT_GOAL := help

.PHONY: help
help:
	@grep -E '^[a-zA-Z0-9_-]+:.*?##' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS = ":.*?##"}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Environment bootstrap ──────────────────────────────────────────

.PHONY: setup
setup: ## Bootstrap an environment (ENV=local|test|production); local/test also copy Git hooks (best-effort)
	bash scripts/setup_env.sh $(ENV)

.PHONY: install
install: ## Build the dev tool image (Dockerfile.dev; frozen uv.lock)
	$(COMPOSE_TEST) build dev

.PHONY: install-git-hooks precommit-install
install-git-hooks: ## Copy docker/.githooks → .git/hooks only (no Docker build). Same files as end of make setup ENV=local|test
	INSTALL_GIT_HOOKS_REQUIRED=1 bash scripts/install_git_hooks.sh
precommit-install: install-git-hooks ## Alias for install-git-hooks
	@:

# ── Run / serve (stack is always Docker) ──────────────────────────

.PHONY: run
run: ## Reminder: the API is the `api` Compose service after make setup ENV=local
	@echo "Local API (Docker): http://localhost:8000/docs  — use: make up   or   make logs"
	@echo "Troubleshooting: docker compose -f docker-compose.yml ps"

.PHONY: worker
worker: ## Tail Celery worker logs (dev stack must be up)
	$(COMPOSE_LOCAL) logs -f worker

.PHONY: beat
beat: ## Tail Celery Beat logs (dev stack must be up)
	$(COMPOSE_LOCAL) logs -f beat

.PHONY: api-shell
api-shell: ## Open a shell in the api container
	$(COMPOSE_LOCAL) exec -it api sh

# ── Quality (Docker: dev service, no DB) ───────────────────────────
# Git hooks aggregate targets here — edit `git-hooks-commit` / `git-hooks-push` to tune DX vs parity.

.PHONY: git-hooks-commit
git-hooks-commit: lint check-env ## Fast gate before commit (Git pre-commit hook)

.PHONY: git-hooks-push-quick
git-hooks-push-quick: lint audit check-env i18n-check ## Lighter pre-push (no pytest); use if GIT_HOOKS_PUSH_QUICK=1

.PHONY: git-hooks-push
git-hooks-push: ci-local ## Default pre-push: full local CI (opt out: GIT_HOOKS_PUSH_QUICK=1 or git push --no-verify)

.PHONY: lint
lint: ## Run ruff + black --check + mypy in the dev container (also part of git-hooks-commit)
	$(DEV0) sh -ec 'ruff check app tests && black --check app tests && mypy app'

.PHONY: format
format: ## Auto-format with ruff + black in the dev container
	$(DEV0) sh -ec 'ruff check app tests --fix && black app tests'

.PHONY: typecheck
typecheck: ## mypy strict in the dev container
	$(DEV0) mypy app

# ── Tests (Docker: dev + test network; DB URLs use compose service names) ──

.PHONY: test
test: ## Run the test suite in the dev container (starts test DBs if needed)
	$(call dev-pytest,-m "not slow")

.PHONY: test-all
test-all: ## Run every test, including slow markers, in the dev container
	$(call dev-pytest,)

.PHONY: test-unit
test-unit: ## pytest -m unit
	$(call dev-pytest,-m unit)

.PHONY: test-int
test-int: ## pytest -m integration
	$(call dev-pytest,-m integration)

.PHONY: cov
cov: ## Run tests with coverage in the dev container
	$(call dev-pytest,--cov=app --cov-report=term-missing)

# ── Database / migrations (against dev DB via api service) ─────────

.PHONY: migration
migration: ## Autogenerate Alembic revision: make migration MSG="add users"
	@test -n "$(MSG)" || (echo "Set MSG, e.g. make migration MSG=\"add users table\""; exit 1)
	$(COMPOSE_LOCAL) exec -T api alembic revision --autogenerate -m "$(MSG)"

.PHONY: migrate
migrate: ## Apply migrations to head (dev database)
	$(COMPOSE_LOCAL) exec -T api alembic upgrade head

.PHONY: downgrade
downgrade: ## Roll back one revision (dev database; staging use only)
	$(COMPOSE_LOCAL) exec -T api alembic downgrade -1

# ── Translations (Babel) ──────────────────────────────────────────

.PHONY: i18n-extract
i18n-extract: ## Rebuild app/locales/messages.pot from sources
	$(DEV0) pybabel extract -F babel.cfg -o app/locales/messages.pot --no-location app

.PHONY: i18n-update
i18n-update: ## Merge .pot into every per-locale .po
	$(DEV0) pybabel update -i app/locales/messages.pot -d app/locales -D messages

.PHONY: i18n-compile
i18n-compile: ## Compile .po → .mo (also in Docker app/build stages)
	$(DEV0) pybabel compile -d app/locales -D messages

.PHONY: i18n-check
i18n-check: ## CI gate: catalogs in sync, completeness ≥ threshold
	$(DEV0) python scripts/i18n_check.py

.PHONY: check-env
check-env: ## Validate Settings and .env.example coverage (Git pre-commit hook via git-hooks-commit)
	$(DEV0) python scripts/check_env.py

.PHONY: new-locale
new-locale: ## Init a new locale: make new-locale LOCALE=xx
	$(DEV0) pybabel init -i app/locales/messages.pot -d app/locales -D messages -l $(LOCALE)

# ── Docker stack ───────────────────────────────────────────────────

.PHONY: build
build: ## Build the production image
	docker build -t fastapi-boilerplate:local -f docker/Dockerfile .

.PHONY: build-dev
build-dev: install ## Alias: build the dev tool image

.PHONY: up
up: ## Bring the local dev stack up
	$(COMPOSE_LOCAL) up -d --build

.PHONY: down
down: ## Tear down the local dev stack (data preserved)
	$(COMPOSE_LOCAL) down

.PHONY: clean
clean: ## Tear down + drop volumes (DESTRUCTIVE)
	$(COMPOSE_LOCAL) down -v
	$(COMPOSE_TEST) down -v

.PHONY: logs
logs: ## Tail logs from the local stack
	$(COMPOSE_LOCAL) logs -f

# ── Test infrastructure ───────────────────────────────────────────

.PHONY: test-up
test-up: ## Up isolated test DB/redis/mail (tests use make test / dev container)
	$(COMPOSE_TEST) up -d postgres_test redis_test mailhog_test
	@echo "Waiting for postgres_test..."
	@until docker exec fb_postgres_test pg_isready -U app_test -d app_test >/dev/null 2>&1; do sleep 1; done
	@echo "Test infra ready."

.PHONY: test-down
test-down: ## Tear down the test infra
	$(COMPOSE_TEST) down -v

# ── OpenAPI / security ────────────────────────────────────────────

.PHONY: openapi
openapi: ## Write openapi.json (from mounted tree)
	$(DEV0) python scripts/dump_openapi.py > openapi.json

.PHONY: audit
audit: ## Run pip-audit, bandit, and detect-secrets (part of ci-local / git-hooks-push)
	$(DEV0) sh -ec 'pip-audit --strict && bandit -q -r app && detect-secrets scan --baseline .secrets.baseline'

# PR gates: same tools as bitbucket-pipelines.yml (sequential; CI runs lint/security/i18n/check-env in parallel).
.PHONY: ci-local
ci-local: ## lint → audit → check-env → i18n-check → test (same as git-hooks-push / Bitbucket default pipeline intent)
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory audit
	@$(MAKE) --no-print-directory check-env
	@$(MAKE) --no-print-directory i18n-check
	@$(MAKE) --no-print-directory test
