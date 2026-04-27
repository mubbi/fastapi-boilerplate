# 0002 — Default locales: English (default + fallback) and Arabic (RTL)

- **Status:** Accepted
- **Date:** 2026-04-27
- **Decision drivers:** spec §11, [`CLAUDE.md`](../../CLAUDE.md) §2 item 11–12

## Context

The boilerplate ships internationalisation built in. We need to commit to specific default locales that:

1. cover the largest target audience for the projects this boilerplate serves;
2. exercise the i18n machinery beyond a "single language" sanity check;
3. force the entire stack — schemas, exceptions, emails, logs — to be locale-aware from day one.

## Decision

- `LOCALES_ENABLED = ["en", "ar"]`.
- `LOCALE_DEFAULT = "en"` and `LOCALE_FALLBACK = "en"`.
- `RTL_LOCALES = ["ar"]`.
- Locale resolution priority is: `?lang=` → authenticated user preference → `Accept-Language` (RFC 7231 quality-weighted) → default.
- Locale is request-scoped: it lives on `request.state.locale`, propagates to Celery via a separate `locale` kwarg, and is included in every log line on the request path.
- `error.code` is **never** translated; only `error.message`.
- No locale branching in business code — locale-specific behaviour lives in catalogs and templates.

## Consequences

- Every user-visible string flows through `Translator.gettext` / `_("...")`. Hardcoded strings are review-blockers.
- Email templates require a per-locale subdirectory (`<id>/en/`, `<id>/ar/`).
- HTML emails set `dir="rtl"` for Arabic via `Translator.is_rtl(locale)`.
- CI gates (`make i18n-check`) enforce catalog completeness ≥ 95% per locale.

## Alternatives considered

- **English only.** Rejected — RTL semantics need to be exercised as part of the boilerplate, otherwise teams "discover" them at the worst time.
- **Per-project locale list with no defaults.** Rejected — projects always start before they know their locale set; shipping `en/ar` gives them a working baseline.
