---
description: Add a new HTTP endpoint that follows API design standards.
---

# /new-endpoint

Add a versioned endpoint under `/api/v1/...` that complies with the API design contract.

## Plan

1. **Decide the URL + method** (architecture spec §9.1):
   - Plural noun, kebab-case, `/api/v1/<resource>` (collection) or `/api/v1/<resource>/{id}`.
   - Idempotent reads: `GET`. State change: `POST` (create / RPC), `PATCH` (partial update), `PUT` (replace), `DELETE`.
2. **Schemas in `app/schemas/<resource>.py`**:
   - `XCreateRequest`, `XUpdateRequest`, `XResponse`, `XListResponse`.
   - `model_config = ConfigDict(extra="forbid")` on all request DTOs.
   - Use `Annotated[..., Field(...)]` for constraints; explicit `examples=`.
3. **Router** in `app/api/v1/<resource>s.py`:
   - One handler = one service method call.
   - Decorator includes `summary`, `description`, `response_model`, `responses={...}` for documented errors, `status_code=...`.
   - Auth via `Depends(require_scopes(...))` if needed (no inline checks).
   - Pagination via shared dep (`Depends(get_pagination)`) → caps `page_size` ≤ 100.
4. **Idempotency** for unsafe mutations: accept `Idempotency-Key` header via dep; service hashes + caches response for 24h.
5. **Errors**: do not raise `HTTPException`; let the global handler map `DomainError` → envelope. `DomainError.message` is the **gettext key**; the handler translates it using `request.state.locale`.
6. **Locale**:
   - Inject `locale: Annotated[str, Depends(get_current_locale)]` if the route returns localized text directly.
   - Never read `request.headers["accept-language"]`.
7. **Tests**:
   - `tests/api/test_<resource>.py` covers happy path + each documented error response.
   - Parameterize on `Accept-Language` (`en`, `ar`) for any user-visible message; assert on `error.code` and `Content-Language`, **not** on translated text.
   - Use factories/seeders, not inline literals.
8. **OpenAPI**: run `make openapi` and verify the diff is only the new route + schemas.
9. **i18n**: if the endpoint introduces new user-visible strings, follow `/new-translation` (extract → translate `en` + `ar` → compile → `make i18n-check`).

## API contract reminders (spec §9)

- Every response carries `X-Request-ID`, `X-API-Version`, and `Content-Language` headers (middleware).
- JSON only (`application/json`), 415 otherwise.
- Dates ISO 8601 UTC; user-visible date/number/currency formatting via `Translator.format_*`.
- Field names snake_case; URL paths kebab-case; collections plural.
- List response shape: `{ "items": [...], "page": { "number": 1, "size": 20, "total": 123 } }`.
- Error envelope: `{ "error": { "code", "message", "details", "request_id", "timestamp" } }` — `code` is locale-independent, `message` is translated.

## Status code crib

| Outcome | Status |
|---|---|
| Read or RPC success with body | 200 |
| Created | 201 (with `Location`) |
| Async accepted | 202 |
| No content | 204 |
| Validation | 422 (Pydantic default) |
| Auth missing | 401 |
| Forbidden | 403 |
| Not found | 404 |
| Conflict | 409 |
| Rate limited | 429 |
| Server error | 500 |
| Upstream | 502 / 504; not ready / draining | 503 |

## Linked rules

- `.cursor/rules/api-design.mdc`
- `.cursor/rules/fastapi-routers.mdc`
- `.cursor/rules/pydantic-v2.mdc`
- `.cursor/rules/security.mdc`
- `.cursor/rules/i18n-l10n.mdc`
