# Runbook — incident response (general)

This is the entry-point runbook. Use it to triage **any** alert; jump to the topical runbook for the specific failure mode.

## 0. Severity definitions

| SEV | Meaning | Examples |
|-----|---------|----------|
| 1 | Customer-facing total outage. | API returning 5xx for >2 min, DB down, Redis down. |
| 2 | Significant degradation. | Error rate >2%, P99 latency >1 s sustained, queue stuck >5 min. |
| 3 | Background degradation. | One scheduled task failing, alerting noise, partial integration outage. |

## 1. Triage checklist (first 5 minutes)

1. **Acknowledge the alert** in the on-call channel; nominate an Incident Commander (IC).
2. **Confirm the symptom** from the user's side:
   - Is `/health` returning 200?
   - Is `/ready` returning 200?
   - Hit a known endpoint with `curl` from outside the platform.
3. **Check the obvious dashboards** in this order:
   - HTTP error rate + P99 latency
   - DB connections / WAL / replication lag
   - Redis ops/sec + memory
   - Celery queue depth + worker count
   - Recent deploy timeline (Render or Bitbucket)
4. **If a deploy happened in the last 30 minutes**, presume it is the cause until proven otherwise. Roll back via Render dashboard or `git revert`.
5. **Pick a topical runbook** (see below) and follow it end-to-end. Keep notes in the incident channel.

## 2. Topical runbooks

- `db-connectivity.md` — Postgres outage / pool exhaustion / migration jam.
- `redis-and-queue.md` — Redis outage, queue backlog, stuck Beat.
- (Add per-domain runbooks here as the project grows.)

## 3. Communication template

```
[SEV-X] <one-line symptom>
Started: <UTC time>
Customer impact: <yes/no, % traffic, regions>
IC: @<person>
Status: investigating | mitigated | resolved
Next update: in <N> minutes
```

## 4. Postmortem requirement

Every SEV-1 and SEV-2 requires a postmortem within 5 business days, using the template in `docs/runbooks/postmortem-template.md` (added per project).

The postmortem MUST include: timeline, root cause, contributing factors, what worked, what didn't, action items with owners + due dates.
