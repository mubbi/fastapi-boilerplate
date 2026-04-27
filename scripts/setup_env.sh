#!/usr/bin/env bash
# Single entry point for environment setup. Called by `make setup ENV=...`.
set -euo pipefail

ENV="${1:-local}"

case "${ENV}" in
  local)
    echo "[setup] Bootstrapping local stack..."
    if [[ ! -f .env ]]; then
      cp .env.example .env
      echo "[setup] Created .env from .env.example. Review before running."
    fi
    docker compose -f docker-compose.yml up -d --build
    echo "[setup] Waiting for postgres..."
    until docker exec fb_postgres pg_isready -U app -d app_db >/dev/null 2>&1; do
      sleep 1
    done
    docker compose -f docker-compose.yml exec api alembic upgrade head
    echo "[setup] Local stack is up. API: http://localhost:8000  MailHog: http://localhost:8025"
    ;;

  test)
    echo "[setup] Bringing up isolated test infra..."
    docker compose -f docker-compose.test.yml up -d
    echo "[setup] Waiting for postgres_test..."
    until docker exec fb_postgres_test pg_isready -U app_test -d app_test >/dev/null 2>&1; do
      sleep 1
    done
    echo "[setup] Test infra ready. Run \`make test\` (pytest runs in the dev Docker image)."
    ;;

  production)
    echo "[setup] Production setup is handled by the container entrypoint."
    echo "[setup] Set SERVICE_ROLE=${SERVICE_ROLE:-web} and let the entrypoint take over."
    ;;

  *)
    echo "[setup] Unknown ENV='${ENV}'. Expected one of: local, test, production." >&2
    exit 64
    ;;
esac
