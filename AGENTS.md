# AGENTS.md

This file is the agent-tool–neutral mirror of [`CLAUDE.md`](CLAUDE.md). Cursor, Codex CLI, and other coding assistants that look for `AGENTS.md` should treat the two files as equivalent — both are kept in sync.

For the full guidance, **read [`CLAUDE.md`](CLAUDE.md)**. For file-scoped, version-specific rules, see [`.cursor/rules/*.mdc`](.cursor/rules) — they apply automatically based on globs in their frontmatter.

For efficient AI work: start with `CLAUDE.md`, then read only the `.cursor/rules/*.mdc` files matching the paths you will touch. Use the full architecture spec when changing cross-cutting behavior, locked stack/deploy choices, or anything the local rules do not cover.

## Quick links

- **Architecture spec (authoritative):** [`docs/tech-architecture-requirements.md`](docs/tech-architecture-requirements.md)
- **Top-level guidance for AI agents:** [`CLAUDE.md`](CLAUDE.md)
- **File-scoped rules:** [`.cursor/rules/`](.cursor/rules)
- **Repeatable workflows (Claude Code slash commands):** [`.claude/commands/`](.claude/commands)
- **Subagents (Claude Code):** [`.claude/agents/`](.claude/agents) — `code-reviewer`, `security-reviewer`
- **ADRs:** `docs/architecture-decisions/`
- **Runbooks:** `docs/runbooks/`

## Review before merge

Two independent AI review passes run before every PR; branch protection still requires at least one human approval per spec §16:

- **Code review** — architecture, DI, Pydantic v2, SQLAlchemy 2.0+ async, modern typing, i18n, testing, code quality.
  Rubric: [`.cursor/rules/code-review.mdc`](.cursor/rules/code-review.mdc) · Subagent: [`.claude/agents/code-reviewer.md`](.claude/agents/code-reviewer.md) · Slash command: `/review-code`
- **Security review** — authn/z, secrets, SQLi/SSRF/IDOR, CORS, rate limiting, container hardening, dependency CVEs, audit logging, PII/GDPR.
  Rubric: [`.cursor/rules/security-review.mdc`](.cursor/rules/security-review.mdc) · Subagent: [`.claude/agents/security-reviewer.md`](.claude/agents/security-reviewer.md) · Slash command: `/review-security`

Cursor users: open the rubrics and prompt `@code-review` / `@security-review` (Cursor will pull the rule into context). Claude Code users: invoke the subagents by name or run the slash commands.

## Single entry for environments

```bash
make setup ENV=local        # full dev stack (api, worker, beat, postgres, redis, mailpit)
make setup ENV=test         # isolated test stack (postgres_test, redis_test, mailpit_test) only
make setup ENV=production SERVICE_ROLE=web|worker|beat   # used by the container entrypoint on Render
```

Tests **never** target the dev database — `conftest.py` enforces a guardrail.

**Tooling:** Ruff, Black, mypy, pytest, Babel, `pip-audit`, `bandit`, and the drift scripts are executed **inside the dev image** built from [`docker/Dockerfile.dev`](docker/Dockerfile.dev) and referenced as the `dev` service in [`docker-compose.test.yml`](docker-compose.test.yml). Use `make install` to build that image, then e.g. `make lint` / `make test`. **Bitbucket Pipelines** uses the same Docker commands, not a host virtualenv. **Git hooks:** Templates in **`docker/.githooks/`** are copied to **`.git/hooks/`** by **`scripts/install_git_hooks.sh`** (end of **`make setup ENV=local|test`**, best-effort). The installed hooks run **`make git-hooks-commit`** (commit) and **`make git-hooks-push`** (pre-push, mirrors **`make ci-local`**; optional **`GIT_HOOKS_PUSH_QUICK=1`** skips pytest). **`make install-git-hooks`** (alias **`precommit-install`**) copies hooks only — no Docker build; **`make setup ENV=local|test`** triggers the same copy best-effort. The full pre-PR gate is **`make ci-local`**.

## Languages

The boilerplate ships with **English (`en`, default + fallback)** and **Arabic (`ar`, RTL)**. Locale handling is centralized in `app/core/i18n.py`; copy lives in `app/locales/<locale>/LC_MESSAGES/messages.po`. See [`tech-architecture-requirements.md`](docs/tech-architecture-requirements.md) §11 and [`.cursor/rules/i18n-l10n.mdc`](.cursor/rules/i18n-l10n.mdc).

```bash
make i18n-extract     # rebuild app/locales/messages.pot from sources
make i18n-update      # merge .pot into every per-locale .po
make i18n-compile     # .po → .mo (also runs in Docker builder stage)
make i18n-check       # CI gate: catalogs in sync, completeness ≥ threshold
make new-locale LOCALE=xx  # initialize a new locale (currently only en/ar are in scope)
```

The `/new-translation` Claude Code slash command walks through this workflow whenever you add a user-visible string.

## Do / Don't

**Do**
- Follow the layered architecture and DI hard rules in [`CLAUDE.md`](CLAUDE.md) §2.
- Keep routers out of repositories, integrations, and workers; services out of FastAPI; repositories out of transaction commits and cross-repository orchestration.
- Add/update tests, factories, and migrations in the same PR as the change.
- Use modern Python typing (`X | None`, `list[X]`, `Annotated[...]`).
- Keep every FastAPI dependency override-friendly for tests; never cache request-scoped dependencies with `lru_cache`.
- Wrap scheduled task bodies in a Redis distributed lock (Beat-singleton-agnostic).
- Use `EmailSender` Protocol; never call SMTP libraries directly from services. `EmailSender.send_template` takes a `locale` kwarg; templates live under `app/templates/email/<id>/<locale>/`.
- Wrap **every** user-visible string with `_("key")` / `Translator.gettext`. Translate `messages.po` for both `en` and `ar` in the same PR.
- Read `request.state.locale` (populated by `get_current_locale`) and pass `locale` as a separate kwarg to Celery tasks that send user-facing notifications.

**Don't**
- Don't import `fastapi.*` from a service or repository.
- Don't `commit()` from a repository.
- Don't return SQLAlchemy ORM objects from a route handler.
- Don't add `if APP_ENV == "test":` to business code.
- Don't introduce a new external dependency without an ADR and a §2 update.
- Don't hardcode user-visible strings (English **or** Arabic) in routers, services, schemas, or templates.
- Don't add `if locale == "ar":` (or any locale) branches to business code — locale-specific behavior belongs in catalogs and templates.
- Don't carry `locale` on a domain event payload — events are facts; locale is a rendering concern. Pass it as a Celery task kwarg.
- Don't translate `error.code` — only `error.message` is translated.
- Don't read `Accept-Language` directly anywhere except `get_current_locale`.
