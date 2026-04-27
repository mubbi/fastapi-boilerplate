---
description: Run a structured code review against the architecture spec. Delegates to the code-reviewer subagent for a focused, citation-backed review of layered architecture, DI, Pydantic v2, SQLAlchemy 2.0+, async, typing, i18n, testing, and code-quality gates.
---

# /review-code

Run a structured **technical** code review of the current change set against the project's architecture rules.

> Pair with `/review-security` for a security pass. The two reviewers are intentionally independent — different rubrics, different blind spots.

## What this does

1. Spawns the `code-reviewer` subagent (defined in `.claude/agents/code-reviewer.md`) with a fresh context window.
2. The subagent identifies the diff scope (PR / branch / files), reads the relevant rules in `.cursor/rules/code-review.mdc`, walks the rubric, and produces severity-ordered findings.
3. You get back a structured report: blockers / majors / nits / missing artifacts / verdict.

## Usage

The subagent will pick up the diff scope automatically from `git diff`, but you can be explicit:

```
/review-code                            # review staged + unstaged changes vs origin/main
/review-code HEAD~3..HEAD               # review last 3 commits
/review-code app/services/invoice_service.py app/api/v1/invoices.py  # review specific files
/review-code PR-123                     # if a PR number is supplied (resolved via gh)
```

## Rubric (mirrors `.cursor/rules/code-review.mdc`)

The reviewer walks every section. Highlights:

| § | Topic | Severity |
|---|---|---|
| §1 | Layer boundaries — Router → Service → Repository → Persistence | BLOCKER |
| §2 | Dependency Injection at every seam | BLOCKER |
| §3 | SOLID / DRY / KISS / YAGNI | MAJOR |
| §4 | Domain modeling & exceptions (`DomainError`, gettext key as message) | BLOCKER |
| §5 | Pydantic v2 (`extra="forbid"`, `model_config: ClassVar[ConfigDict]`) | MAJOR |
| §6 | SQLAlchemy 2.0 async, no N+1, repo doesn't commit | BLOCKER |
| §7 | Alembic — backward-compatible migrations only | BLOCKER |
| §8 | Async correctness (no sync I/O on request path) | BLOCKER |
| §9 | Modern Python typing (`X \| None`, `list[X]`, `Annotated[...]`) | MAJOR |
| §10 | Settings / config (`SecretStr`, `.env.example` drift) | BLOCKER |
| §11 | Domain events (past-tense, no `locale` field) | BLOCKER |
| §12 | Celery (idempotent, primitive args, Redis lock for Beat) | BLOCKER |
| §13 | Caching (versioned keys, TTLs, single-flight) | MAJOR |
| §14 | HTTP client (`httpx`, tenacity, no `verify=False`) | MAJOR |
| §15 | Email (`EmailSender` Protocol, per-locale templates) | MAJOR |
| §16 | i18n / l10n (no hardcoded strings, `en` + `ar` translated) | BLOCKER |
| §17 | Logging (structlog, request-scoped, no PII) | MAJOR |
| §18 | Observability (Prometheus + OTel + Sentry) | MAJOR |
| §19 | Testing (markers, factories, isolation guardrail) | BLOCKER |
| §20 | Code quality (mypy strict, ruff, black) | BLOCKER |
| §21 | Project artifacts (OpenAPI, ADRs, runbooks) | MAJOR |

## Output

The reviewer returns:

```
## [BLOCKER] / [MAJOR] / [MINOR / NIT]
- <path>:<line> — <rule short name> (<rule file>)
  Issue: ...
  Fix:   ...

## Missing artifacts
- ...

## Spec-gap callouts
- ...

## Summary
- Blockers: n
- Majors:   n
- Minors:   n
- Verdict:  APPROVE | REQUEST CHANGES | COMMENT
```

Verdict semantics:

- **APPROVE** — no blockers, no majors that require change.
- **REQUEST CHANGES** — at least one blocker, or majors that materially affect the design.
- **COMMENT** — only nits / praise; no required changes.

## Linked artifacts

- Subagent: `.claude/agents/code-reviewer.md`
- Rubric: `.cursor/rules/code-review.mdc`
- Hard rules: `CLAUDE.md` §2
- Pair with: `/review-security`

## When to run

- Before opening any PR.
- After resolving review comments (re-run to confirm clean).
- Whenever you ask Claude to "look this over" or "check this against the spec".
- Routine cadence on long-lived branches (`/review-code` weekly catches drift).

## What this does NOT cover

- Security findings → use `/review-security` (separate rubric, separate severity ladder).
- Runtime behavior / debugging → run tests; the reviewer is static-only.
- Performance profiling → out of scope; spec §14 covers SLOs and you should profile against them directly.
