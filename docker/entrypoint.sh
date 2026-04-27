#!/usr/bin/env bash
# Single entrypoint for all SERVICE_ROLE values.
#   web    -> gunicorn + uvicorn workers (FastAPI)
#   worker -> celery worker
#   beat   -> celery beat (exactly one replica per environment)
#   migrate-> run alembic upgrade head and exit
set -euo pipefail

ROLE="${SERVICE_ROLE:-web}"
PORT="${APP_PORT:-8000}"

echo "[entrypoint] role=${ROLE} env=${APP_ENV:-?} version=${APP_VERSION:-?}"

case "${ROLE}" in
  web)
    WORKERS="${GUNICORN_WORKERS:-2}"
    THREADS="${GUNICORN_THREADS:-1}"
    TIMEOUT="${GUNICORN_TIMEOUT:-60}"
    GRACEFUL_TIMEOUT="${GUNICORN_GRACEFUL_TIMEOUT:-30}"
    exec gunicorn app.main:app \
      --bind "0.0.0.0:${PORT}" \
      --worker-class uvicorn.workers.UvicornWorker \
      --workers "${WORKERS}" \
      --threads "${THREADS}" \
      --timeout "${TIMEOUT}" \
      --graceful-timeout "${GRACEFUL_TIMEOUT}" \
      --access-logfile - \
      --error-logfile -
    ;;
  worker)
    QUEUES="${CELERY_QUEUES:-default,events}"
    CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-4}"
    exec celery -A app.workers.celery_app worker \
      --queues "${QUEUES}" \
      --concurrency "${CONCURRENCY}" \
      --loglevel "${APP_LOG_LEVEL:-INFO}"
    ;;
  beat)
    SCHEDULE_PATH="${CELERY_BEAT_SCHEDULE_FILENAME:-/tmp/celerybeat-schedule}"
    exec celery -A app.workers.celery_app beat \
      --schedule "${SCHEDULE_PATH}" \
      --loglevel "${APP_LOG_LEVEL:-INFO}"
    ;;
  migrate)
    echo "[entrypoint] running alembic upgrade head"
    exec alembic upgrade head
    ;;
  shell)
    exec python -m IPython
    ;;
  *)
    echo "[entrypoint] Unknown SERVICE_ROLE='${ROLE}'." >&2
    exit 64
    ;;
esac
