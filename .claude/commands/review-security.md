---
description: Run a structured security review of the current change set. Delegates to the security-reviewer subagent — authn/z, secrets, SQLi/SSRF/IDOR, CORS, rate limiting, container hardening, dependency CVEs, audit logging, GDPR/PII.
---

# /review-security

Run a structured **security-only** review of the current change set against the project's threat model and security baseline.

> Pair with `/review-code` for technical correctness. The two reviewers are intentionally independent — different rubrics, different blind spots.

## What this does

1. Spawns the `security-reviewer` subagent (defined in `.claude/agents/security-reviewer.md`) with a fresh context window.
2. The subagent threat-models the change, reads `.cursor/rules/security-review.mdc`, walks the rubric, runs the banned-patterns sweep, and produces findings on the CRITICAL / HIGH / MEDIUM / LOW severity ladder.
3. You get back a structured report including escalation triggers and concrete remediations with CWE / OWASP references.

## Usage

```
/review-security                                            # review staged + unstaged changes vs origin/main
/review-security HEAD~3..HEAD                               # review last 3 commits
/review-security app/api/v1/auth.py app/core/security.py    # review specific files
/review-security --deps                                     # focused dependency / lockfile sweep
/review-security --infra                                    # focused Dockerfile / compose / render / pipelines sweep
```

`--deps` and `--infra` are scope hints for the reviewer, not flags for a standalone binary.

## Rubric (mirrors `.cursor/rules/security-review.mdc`)

The reviewer walks every section. Highlights:

| § | Topic | Floor severity if violated |
|---|---|---|
| §1  | Authentication — JWT alg pinning, refresh rotation, bcrypt cost ≥ 12 | CRITICAL |
| §2  | Authorization — scope deps, IDOR, deny-by-default | CRITICAL |
| §3  | Input validation — `extra="forbid"`, allowlists, no mass-assignment | HIGH |
| §4  | Output handling — `response_model`, no ORM leakage, error envelope | HIGH |
| §5  | SQL safety — parameterized only, no f-string SQL, ORDER BY allowlist | CRITICAL |
| §6  | SSRF — outbound URL allowlist, no metadata-server fetches | HIGH |
| §7  | Secrets — `SecretStr`, redactor coverage, no image/log leaks | CRITICAL |
| §8  | Crypto — no homemade KDF/cipher, `secrets.token_urlsafe` for tokens | HIGH |
| §9  | CORS / Trusted hosts / TLS — explicit allowlist, `verify=True` | HIGH |
| §10 | Security headers — HSTS, nosniff, frame-deny, CSP | MEDIUM |
| §11 | Rate limiting — per-IP + per-account on auth | HIGH |
| §12 | Cookies / sessions (only if cookie auth used) — Secure, HttpOnly, SameSite | HIGH |
| §13 | Containers — non-root, multi-stage, scanned, healthcheck | CRITICAL |
| §14 | Supply chain — pinned lockfile, pip-audit, bandit, detect-secrets, Trivy | HIGH |
| §15 | Audit logging — login, role change, admin action, secret rotation | HIGH |
| §16 | PII / GDPR — data class registry, retention, delete/export | MEDIUM |
| §17 | Idempotency / replay — `Idempotency-Key`, webhook HMAC + skew | MEDIUM |
| §18 | Banned patterns — `eval`, `exec`, `pickle.loads`, `shell=True`, `verify=False`, … | CRITICAL |
| §19 | Render / deploy surface — secret-marked env vars, private network only | HIGH |
| §20 | Escalation triggers — leaked secret, auth bypass, RCE primitive, … | BLOCK + ESCALATE |

## Output

```
## Threat model
- Attacker: ...
- Asset:    ...
- Entry:    ...

## [CRITICAL] / [HIGH] / [MEDIUM] / [LOW / NIT]
- <path>:<line> — <issue title>
  Risk: <impact + likelihood>
  Fix:  <concrete change>
  Ref:  <CWE-XXX / OWASP A0X:2021 / rule / spec §>

## Missing controls
- ...

## Escalation
- <only present if a §20 trigger fired>

## Summary
- Critical: n
- High:     n
- Medium:   n
- Low:      n
- Verdict:  APPROVE | REQUEST CHANGES | BLOCK + ESCALATE
```

## Verdict semantics

- **APPROVE** — clean. No findings above LOW.
- **REQUEST CHANGES** — one or more findings at MEDIUM / HIGH that need fixes before merge.
- **BLOCK + ESCALATE** — at least one CRITICAL or any `security-review.mdc` §20 escalation trigger fired. Do not merge. Notify on-call. May require secret rotation, branch quarantine, or history rewrite.

## Escalation triggers (auto-BLOCK)

1. Leaked secret in any branch (even unmerged).
2. Auth bypass / broken JWT verification.
3. RCE primitive (`eval`, `exec`, `pickle.loads`, `subprocess shell=True`) reachable from a request handler / Celery task.
4. SQL injection on a real query path.
5. Production credentials in non-production environment.
6. Container running as root in deployed image.
7. Plaintext password storage / logging.
8. CORS wildcard + `allow_credentials=True` in production config.

If any of these fires, the reviewer returns `Verdict: BLOCK + ESCALATE` and lists the recommended on-call action (rotate secret, force-push removal + history rewrite, revoke deploy, etc.).

## Linked artifacts

- Subagent: `.claude/agents/security-reviewer.md`
- Rubric: `.cursor/rules/security-review.mdc`
- Baseline: `.cursor/rules/security.mdc`
- Spec: `docs/tech-architecture-requirements.md` §12
- Pair with: `/review-code`

## When to run

- Before opening any PR that touches: `app/api/**`, `app/core/security.py`, `app/core/middleware.py`, `app/core/config.py`, `app/integrations/**`, `app/repositories/**`, `Dockerfile`, `docker-compose*.yml`, `render.yaml`, `bitbucket-pipelines.yml`, dependency manifests / lockfiles (`pyproject.toml`, `uv.lock`, `requirements*.txt`, etc.), `.env.example`, `.pre-commit-config.yaml`.
- Whenever you add a new dependency (run with `--deps`).
- Whenever you change auth, session, password, JWT, CSRF, or rate-limit logic.
- After dependency upgrades (CVE delta).
- Quarterly on a clean main as a posture check.

## What this does NOT cover

- Architectural / design review → use `/review-code`.
- Live penetration testing → out of scope for an AI reviewer; engage a human pen tester for production launches.
- Compliance certification (SOC 2, ISO 27001) → out of scope; use this review as evidence, not as the certification itself.
- Frontend XSS analysis → out of scope; this is a backend boilerplate. Provide guidance on token storage if frontend integration is in the diff.
