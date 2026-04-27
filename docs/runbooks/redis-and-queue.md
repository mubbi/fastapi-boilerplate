# Runbook — Redis and Celery queue

Symptoms that lead here: `/ready` returning 503 with `cache: down`, queue depth alert, scheduled task missing for >1 cycle, worker count == 0.

## 1. Quick checks

```bash
# Is Redis up?
docker compose exec redis redis-cli ping

# Connection count and memory
docker compose exec redis redis-cli info clients
docker compose exec redis redis-cli info memory

# Celery queue depth (per queue)
docker compose exec redis redis-cli llen celery
docker compose exec redis redis-cli llen system

# Workers currently consuming
docker compose exec worker celery -A app.workers.celery_app inspect active
docker compose exec worker celery -A app.workers.celery_app inspect ping
```

## 2. Common causes & responses

### A. Redis OOM (`OOM command not allowed when used memory > 'maxmemory'`)

- Symptom: writes failing, queue empty but tasks not enqueueing.
- Mitigation: raise `maxmemory` on the platform; verify `maxmemory-policy=allkeys-lru` for cache, `noeviction` for the broker DB.
- Follow-up: split broker and cache into separate Redis instances (or DBs with isolated eviction).

### B. Stuck queue / no workers consuming

- `inspect ping` returns `{}` → workers are dead. Check Render worker service logs and recent deploys.
- Workers replying but queue not draining → a single task is failing fast and re-queuing. Inspect with `inspect active`. Mitigate by acking the poison message and filing a bug:

```bash
# Manually acknowledge a poison task by purging the queue (DESTRUCTIVE — last resort)
celery -A app.workers.celery_app purge -Q <queue>
```

### C. Beat skipped a tick

- Beat runs as exactly one replica (see ADR-0003). A redeploy briefly takes Beat offline; a single missed tick is expected.
- If multiple consecutive ticks miss:
  1. Verify the Beat service is `live` in Render.
  2. Check that the per-task Redis lock isn't stuck (`KEYS lock:*` then `TTL` on each).
  3. Manually release a stuck lock only if the corresponding task is confirmed not running:
     ```bash
     redis-cli del lock:<task-name>
     ```

### D. Scheduled task ran twice (Beat overlap during deploy)

- Should not happen because tasks acquire a Redis lock, but verify by reading the task's structured logs — only one invocation should report `acquired_lock=true`.

## 3. Recovery checklist

- [ ] `redis-cli ping` returns `PONG`.
- [ ] Queue depth trending down.
- [ ] At least one worker `inspect ping` reply per worker service.
- [ ] Beat service running and last heartbeat within the schedule period.
- [ ] No stuck locks in Redis.
