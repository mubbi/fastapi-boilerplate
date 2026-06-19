"""Internationalization & localization.

Provides:
- ``Translator`` Protocol with ``gettext`` / ``ngettext`` / ``format_*`` / ``is_rtl``.
- ``BabelTranslator`` — production impl backed by gettext catalogs at ``LOCALE_DIR``.
- ``EchoTranslator`` — test impl that returns the key unchanged.
- ``resolve_locale`` — priority-ordered resolver (query → user pref → header → default).
- ``negotiate_accept_language`` — quality-weighted BCP-47 negotiation.
- ``_(...)`` and ``N_(...)`` helpers for translatable strings in code.

Spec §11; rules in ``.cursor/rules/i18n-l10n.mdc``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from babel.dates import format_datetime as babel_format_datetime
from babel.numbers import format_currency as babel_format_currency
from babel.numbers import format_decimal as babel_format_decimal
from babel.support import Translations

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


# ── Protocol ─────────────────────────────────────────────────────


class Translator(Protocol):
    """Translation + locale-aware formatting interface (see spec §11.3)."""

    def gettext(self, key: str, *, locale: str | None = None, **params: object) -> str: ...

    def ngettext(
        self,
        singular: str,
        plural: str,
        n: int,
        *,
        locale: str | None = None,
        **params: object,
    ) -> str: ...

    def format_datetime(
        self,
        dt: datetime,
        *,
        locale: str | None = None,
        format: str = "medium",
    ) -> str: ...

    def format_number(
        self,
        value: int | float | Decimal,
        *,
        locale: str | None = None,
    ) -> str: ...

    def format_currency(
        self,
        amount: Decimal,
        currency: str,
        *,
        locale: str | None = None,
    ) -> str: ...

    def is_rtl(self, locale: str) -> bool: ...


# ── BabelTranslator ──────────────────────────────────────────────


class BabelTranslator:
    """Default implementation backed by Babel + gettext catalogs."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._dir = Path(settings.locale_dir)
        self._domain = settings.locale_domain
        self._fallback = settings.locale_fallback
        self._enabled = set(settings.locales_enabled)
        self._rtl = set(settings.rtl_locales)
        # Per-instance catalog cache. Instance-scoped (not @lru_cache on the method,
        # which would pin every translator instance in a process-global cache).
        self._catalogs: dict[str, Translations] = {}

    def _translations(self, locale: str) -> Translations:
        """Load + cache one ``Translations`` per locale (once per instance)."""
        cached = self._catalogs.get(locale)
        if cached is not None:
            return cached
        if not self._dir.exists():
            loaded: Translations = Translations()
        else:
            result = Translations.load(
                dirname=str(self._dir),
                locales=[locale, self._fallback],
                domain=self._domain,
            )
            loaded = result if isinstance(result, Translations) else Translations()
        self._catalogs[locale] = loaded
        return loaded

    def _resolve(self, locale: str | None) -> str:
        if locale and locale in self._enabled:
            return locale
        return self._settings.locale_default

    def gettext(self, key: str, *, locale: str | None = None, **params: object) -> str:
        loc = self._resolve(locale)
        try:
            translations = self._translations(loc)
            translated = translations.gettext(key)
        except Exception:
            translated = key
        if not params:
            return translated
        try:
            return translated % params
        except Exception:
            return translated

    def ngettext(
        self,
        singular: str,
        plural: str,
        n: int,
        *,
        locale: str | None = None,
        **params: object,
    ) -> str:
        loc = self._resolve(locale)
        try:
            translations = self._translations(loc)
            text = translations.ngettext(singular, plural, n)
        except Exception:
            text = singular if n == 1 else plural
        merged: dict[str, object] = {"n": n, **params}
        try:
            return text % merged
        except Exception:
            return text

    def format_datetime(
        self,
        dt: datetime,
        *,
        locale: str | None = None,
        format: str = "medium",
    ) -> str:
        loc = self._resolve(locale)
        try:
            return babel_format_datetime(dt, format=format, locale=loc)
        except Exception:
            return dt.isoformat()

    def format_number(
        self,
        value: int | float | Decimal,
        *,
        locale: str | None = None,
    ) -> str:
        loc = self._resolve(locale)
        try:
            return babel_format_decimal(value, locale=loc)
        except Exception:
            return str(value)

    def format_currency(
        self,
        amount: Decimal,
        currency: str,
        *,
        locale: str | None = None,
    ) -> str:
        loc = self._resolve(locale)
        try:
            return babel_format_currency(amount, currency, locale=loc)
        except Exception:
            return f"{amount} {currency}"

    def is_rtl(self, locale: str) -> bool:
        return locale in self._rtl


# ── EchoTranslator (tests) ───────────────────────────────────────


class EchoTranslator:
    """Returns the key unchanged so unit tests can assert on translation keys."""

    def __init__(self, *, rtl_locales: tuple[str, ...] = ("ar",)) -> None:
        self._rtl = set(rtl_locales)

    def gettext(self, key: str, *, locale: str | None = None, **params: object) -> str:
        if not params:
            return key
        try:
            return key % params
        except Exception:
            return key

    def ngettext(
        self,
        singular: str,
        plural: str,
        n: int,
        *,
        locale: str | None = None,
        **params: object,
    ) -> str:
        text = singular if n == 1 else plural
        merged: dict[str, object] = {"n": n, **params}
        try:
            return text % merged
        except Exception:
            return text

    def format_datetime(
        self,
        dt: datetime,
        *,
        locale: str | None = None,
        format: str = "medium",
    ) -> str:
        return dt.isoformat()

    def format_number(
        self,
        value: int | float | Decimal,
        *,
        locale: str | None = None,
    ) -> str:
        return str(value)

    def format_currency(
        self,
        amount: Decimal,
        currency: str,
        *,
        locale: str | None = None,
    ) -> str:
        return f"{amount} {currency}"

    def is_rtl(self, locale: str) -> bool:
        return locale in self._rtl


# ── Factory ──────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_translator() -> Translator:
    """Return the process-wide default translator (BabelTranslator)."""
    return BabelTranslator(get_settings())


# ── Locale negotiation ───────────────────────────────────────────


def negotiate_accept_language(header: str | None, enabled: list[str], default: str) -> str:
    """Quality-weighted BCP-47 negotiation against an enabled allowlist."""
    if not header:
        return default

    enabled_lower = {loc.lower(): loc for loc in enabled}
    candidates: list[tuple[float, int, str]] = []
    for idx, raw in enumerate(header.split(",")):
        token = raw.strip()
        if not token:
            continue
        parts = [p.strip() for p in token.split(";")]
        tag = parts[0].lower()
        q = 1.0
        for param in parts[1:]:
            if param.startswith("q="):
                try:
                    q = float(param[2:])
                except ValueError:
                    q = 0.0
        if q <= 0:
            continue
        # Match exact tag, then primary subtag (e.g., "en-US" -> "en").
        if tag in enabled_lower:
            candidates.append((q, -idx, enabled_lower[tag]))
            continue
        primary = tag.split("-")[0]
        if primary in enabled_lower:
            candidates.append((q, -idx, enabled_lower[primary]))
    if not candidates:
        return default
    candidates.sort(reverse=True)
    return candidates[0][2]


def resolve_locale(
    *,
    query_value: str | None,
    user_pref: str | None,
    accept_language: str | None,
    settings: Settings,
) -> str:
    """Resolve the request locale per spec §11.2 priority order."""
    enabled = settings.locales_enabled
    default = settings.locale_default

    if query_value and settings.locale_query_param and query_value in enabled:
        return query_value

    if user_pref and user_pref in enabled:
        return user_pref

    return negotiate_accept_language(accept_language, enabled, default)


# ── Convenience aliases for source extraction ────────────────────


def _(key: str, *, locale: str | None = None, **params: object) -> str:
    """Translate at call time using the default translator."""
    return get_translator().gettext(key, locale=locale, **params)


def _translation_extraction_marker(key: str) -> str:
    """Mark a string for extraction without translating it now (gettext ``N_`` pattern)."""
    return key


# Bound to ``N_`` so xgettext-style extractors match the usual ``N_('...')`` call form.
N_ = _translation_extraction_marker
