# Runbook — Database connectivity

Symptoms that lead here: `/ready` returning 503 with `db: down`, surge of `OperationalError` / `asyncpg.PostgresConnectionError` in logs, P99 latency spike on every endpoint, alembic upgrade failing to acquire lock.

## 1. Quick checks

```bash
# 1. Is the DB actually reachable from the API container?
docker compose exec api python -c "import asyncio, asyncpg, os; \
  asyncio.run(asyncpg.connect(os.environ['DATABASE_URL']).then(lambda c: c.close()))"

# 2. Active connections vs configured pool
psql "$DATABASE_URL" -c "select count(*) from pg_stat_activity;"
psql "$DATABASE_URL" -c "show max_connections;"

# 3. Long-running / blocked queries
psql "$DATABASE_URL" -c "
  select pid, now() - query_start as runtime, state, query
  from pg_stat_activity
  where state <> 'idle' and now() - query_start > interval '10 seconds'
  order by runtime desc;
"

# 4. Lock contention
psql "$DATABASE_URL" -c "
  select blocked_locks.pid as blocked_pid, blocking_locks.pid as blocking_pid,
         blocked_activity.query as blocked_query, blocking_activity.query as blocking_query
  from pg_locks blocked_locks
  join pg_stat_activity blocked_activity on blocked_locks.pid = blocked_activity.pid
  join pg_locks blocking_locks
    on blocking_locks.locktype = blocked_locks.locktype
   and blocking_locks.granted
   and blocking_locks.pid <> blocked_locks.pid
  join pg_stat_activity blocking_activity on blocking_locks.pid = blocking_activity.pid
  where not blocked_locks.granted;
"
```

## 2. Common causes & responses

### A. Pool exhaustion under load

- Symptom: `pg_stat_activity` count near `max_connections`, app logs `TimeoutError: pool exhausted`.
- Mitigation: scale up the API service; cap `DB_POOL_SIZE` so total cluster connections stay below ~80% of `max_connections`.
- Long-term: add an external pool (PgBouncer in transaction mode) on the platform side.

### B. Long-running query holding a lock

- Symptom: `pg_locks` shows blocked PIDs.
- Mitigation: `SELECT pg_cancel_backend(<blocking_pid>);` (gentle) or `pg_terminate_backend(<blocking_pid>);` (forceful).
- Follow-up: file a ticket against the originating query/migration.

### C. Stuck Alembic migration

- Symptom: `alembic upgrade head` hung, `pg_locks` shows AccessExclusive on a target table, `alembic_version` row locked.
- Mitigation:
  1. Identify the offending PID via the lock query above.
  2. Cancel it (`pg_cancel_backend`).
  3. Re-run the migration after fixing the cause (typically a long-running default backfill — split into add → backfill → switch).

### D. Provider-side outage (managed Postgres down)

- Symptom: TCP refusing connections from anywhere.
- Mitigation: post a SEV-1 status, wait for the provider, ensure the API serves cached `/ready=503` cleanly so load balancers don't loop.

## 3. Recovery checklist

- [ ] `/ready` returns 200 from API.
- [ ] Error rate back to baseline (<0.5% over 5 min).
- [ ] No backlog in queues caused by failed DB writes.
- [ ] Postmortem opened (SEV-1/SEV-2).
