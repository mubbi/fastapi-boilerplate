#!/usr/bin/env bash
# Container HEALTHCHECK command. Behavior depends on SERVICE_ROLE.
#   web    -> HTTP GET /health
#   worker -> celery inspect ping (cheap)
#   beat   -> always healthy (no socket; rely on TTL on the Beat lock)
set -euo pipefail

ROLE="${SERVICE_ROLE:-web}"
PORT="${APP_PORT:-8000}"

case "${ROLE}" in
  web)
    curl --fail --silent --show-error --max-time 5 "http://127.0.0.1:${PORT}/health" >/dev/null
    ;;
  worker)
    # ``celery inspect ping`` returns 0 when at least one worker responds.
    celery -A app.workers.celery_app inspect ping --timeout 3 >/dev/null
    ;;
  beat)
    # Keep healthy; the cron lock TTL is the real liveness signal for Beat.
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
