---
description: Add or update a user-visible string with full i18n workflow (English + Arabic), keeping gettext catalogs in sync and CI green.
---

# /new-translation

Use this whenever you introduce or change a **user-visible string** anywhere in the codebase: API responses (incl. `DomainError.message` keys), Pydantic validation messages surfaced to clients, email subjects/bodies, log fields that surface in user-facing UIs, etc.

The boilerplate ships **English (`en`, default + fallback)** and **Arabic (`ar`, RTL)**. Every key must exist (and be translated) in both. CI fails otherwise.

> Rules of engagement live in `.cursor/rules/i18n-l10n.mdc` and `docs/tech-architecture-requirements.md` §11.

---

## 0. Decide what to translate

| You're adding… | Treat as |
|---|---|
| New `DomainError` (e.g. `InvoiceAlreadyPaid`) | `code` is locale-independent (`INVOICE_ALREADY_PAID`); `message` is the **gettext key/source** (e.g. `"errors.invoice.already_paid"` or `"Invoice %(invoice_id)s is already paid"`). |
| Pydantic `Field(description=...)` for OpenAPI | **Not** translated — `description=` is documentation, not user-visible UI text. |
| Pydantic validator that raises a user-facing message | Raise `DomainError` (or convert at the handler) — never inline English in the schema. |
| Email subject / body | Lives in per-locale Jinja2 template under `app/templates/email/<id>/<locale>/{subject.j2,html.j2,txt.j2}`. Shared snippets inside templates may still use `_(...)` and be extracted to `messages.po`. |
| Log field that surfaces in a UI dashboard | Translate the **rendered** string at the boundary, log the gettext key in structured logs. |
| Internal log message / engineering metric | **Do not translate.** English-only is fine for operator-facing text. |

If unsure, default to translating it.

## 1. Use the gettext key in code

```python
# routers / handlers
return MessageResponse(message=translator.gettext("user.welcome", name=user.name))

# services (raise — never translate here)
raise InvoiceAlreadyPaidError(
    message="errors.invoice.already_paid",   # gettext key
    params={"invoice_id": str(invoice.id)},  # named params for the catalog
)

# emails
EmailSender.send_template(
    template_id="welcome",
    to=user.email,
    locale=locale,                  # resolved from request.state.locale or task kwarg
    context={"name": user.name},
)
```

**Hard checks before continuing:**

- [ ] Key follows `<area>.<entity>.<state>` — kebab-free, snake-case (e.g. `errors.user.email_already_taken`).
- [ ] All interpolations use **named parameters** (`%(name)s`), never positional or f-string.
- [ ] No string concatenation across translatable fragments.
- [ ] No `if locale == "ar":` anywhere — locale-specific behavior belongs in the catalog.
- [ ] You did **not** add a `locale` field to a domain event (pass it as a Celery task kwarg instead).

## 2. Extract → update → translate → compile

```bash
# (a) Rebuild the .pot template from sources (Babel walks app/ via babel.cfg)
make i18n-extract

# (b) Merge new keys into every per-locale .po (preserves existing translations)
make i18n-update
```

Now edit the translation files:

- `app/locales/en/LC_MESSAGES/messages.po` — add the **English** translation. (Note: even though `en` is the source, we still ship a real `.po` so the gettext lookup is uniform and CLDR plural rules apply.)
- `app/locales/ar/LC_MESSAGES/messages.po` — add the **Arabic** translation.

Example block:

```po
#: app/services/invoice_service.py:142
msgid "errors.invoice.already_paid"
msgstr "Invoice %(invoice_id)s is already paid."
```

Arabic counterpart:

```po
#: app/services/invoice_service.py:142
msgid "errors.invoice.already_paid"
msgstr "تم دفع الفاتورة %(invoice_id)s بالفعل."
```

### Plurals (use `ngettext`, never hand-rolled)

Arabic has **6 plural forms** (CLDR: `zero`, `one`, `two`, `few`, `many`, `other`). Babel handles this automatically — never write `if n == 1: ...` in code or split keys per count.

```python
translator.ngettext(
    "cart.items.singular",
    "cart.items.plural",
    n=count,
    count=count,
)
```

In `messages.po` for Arabic the plural header sets `nplurals=6` and you fill all 6 `msgstr[0..5]`.

### RTL note

Arabic is right-to-left. **Don't** hardcode `dir="rtl"` in code; emails read `dir` from `Translator.is_rtl(locale)` or the template helper. If you're adding a new HTML email template, ensure `dir="{{ 'rtl' if rtl else 'ltr' }}"` is on `<html>` / the root container.

```bash
# (c) Compile catalogs — produces .mo files used at runtime
make i18n-compile
```

## 3. Validate

```bash
# Catalog hygiene: pot-vs-source drift, every locale compiles, completeness ≥ threshold
make i18n-check
```

Expected outcome:

- `messages.pot` has zero diff vs. extraction from sources.
- Every `.po` compiles (`pybabel compile`).
- Translation completeness for `en` and `ar` ≥ `LOCALE_TRANSLATION_COMPLETENESS_MIN` (no untranslated entries, no `#, fuzzy` markers on shipped keys).

## 4. Tests

Add at least one test that proves **both** locales are wired end-to-end. Assert on `error.code` / structured response fields, **never** on translated text.

```python
@pytest.mark.parametrize("lang", ["en", "ar"])
async def test_invoice_already_paid_returns_localized_message(client, lang):
    resp = await client.post(
        "/api/v1/invoices/INV-1/mark-paid",
        headers={"Accept-Language": lang},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "INVOICE_ALREADY_PAID"
    assert resp.headers["content-language"] == lang
    assert body["error"]["message"]   # non-empty; do not assert exact copy
```

For email:

```python
@pytest.mark.parametrize("locale", ["en", "ar"])
async def test_welcome_email_renders_per_locale(email_sender_fake, locale):
    await welcome_user_service.register(..., locale=locale)
    sent = email_sender_fake.last_sent
    assert sent.locale == locale
    assert sent.template_id == "welcome"
    # Assert structural locale behavior, not translated copy.
    expected_dir = {"en": "ltr", "ar": "rtl"}[locale]
    assert f'dir="{expected_dir}"' in sent.html_body
```

## 5. Commit checklist

- [ ] Code uses `_(...)` / `Translator.*` only — no hardcoded user-visible English or Arabic.
- [ ] `app/locales/messages.pot` updated (committed).
- [ ] `app/locales/en/LC_MESSAGES/messages.po` updated and translated (committed).
- [ ] `app/locales/ar/LC_MESSAGES/messages.po` updated and translated (committed).
- [ ] `.mo` files **not** committed if they're built artifacts (per `.gitignore`); they're produced by `make i18n-compile` and the Docker builder stage.
- [ ] `make i18n-check` passes locally.
- [ ] Tests cover both `en` and `ar` for any user-visible behavior.
- [ ] No `if locale == "ar":` in `app/services/**`, `app/repositories/**`, or `app/integrations/**`.
- [ ] No `locale` field added to a domain event (`app/events/types.py`).
- [ ] `EmailSender.send_template(...)` calls pass an explicit `locale=`.

## Anti-patterns (review-rejecting)

- ❌ `f"Hello {name}, welcome!"` returned to users.
- ❌ `_("hello") + ", " + name` (concatenation across translatable fragments).
- ❌ `_("welcome.email.subject_en")` / `_("welcome.email.subject_ar")` — one key per locale instead of one key with two translations.
- ❌ Translating `error.code` (codes are stable contract identifiers — only `message` is translated).
- ❌ Hand-rolling Arabic plural rules with `if n == 1: ...`.
- ❌ Reading `request.headers["accept-language"]` outside `get_current_locale`.
- ❌ Adding the new key only to `en` and pushing — CI completeness gate will reject.
- ❌ Compiling `.po` files in the request path or at app startup (compile at build/deploy time).
- ❌ Carrying `locale` on a domain event payload.

## Linked rules

- `.cursor/rules/i18n-l10n.mdc` (canonical)
- `.cursor/rules/domain-exceptions.mdc`
- `.cursor/rules/email-integration.mdc`
- `.cursor/rules/celery-tasks.mdc`
- `.cursor/rules/domain-events.mdc`
- `.cursor/rules/api-design.mdc`
- `.cursor/rules/testing-pytest.mdc`

## Spec reference

- `docs/tech-architecture-requirements.md` §11 — Internationalization (i18n) & Localization (l10n)
- `docs/tech-architecture-requirements.md` §17.4 — Make targets (`i18n-extract`, `i18n-update`, `i18n-compile`, `i18n-check`, `new-locale`)
