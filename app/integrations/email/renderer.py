"""Jinja2 template renderer for emails.

Templates live under ``app/templates/email/<template_id>/<locale>/{subject,html,txt}.j2``.
If a locale-specific subdir is missing for a given template, the renderer falls
back to ``LOCALE_FALLBACK`` and increments
``EMAIL_LOCALE_FALLBACK_TOTAL{template, locale}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import (
    BaseLoader,
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateNotFound,
    select_autoescape,
)

from app.core.config import Settings
from app.core.i18n import Translator
from app.core.logging import get_logger
from app.core.metrics import EMAIL_LOCALE_FALLBACK_TOTAL

log = get_logger(__name__)

EMAIL_TEMPLATE_ROOT = Path("app/templates/email")


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    """Output of :meth:`TemplateRenderer.render`."""

    subject: str
    text_body: str
    html_body: str
    locale: str


class TemplateRenderer:
    """Renders ``subject.j2``, ``html.j2``, and ``txt.j2`` for the requested locale."""

    def __init__(self, *, settings: Settings, translator: Translator) -> None:
        self._settings = settings
        self._translator = translator
        self._fallback = settings.locale_fallback
        self._env = Environment(
            loader=FileSystemLoader(EMAIL_TEMPLATE_ROOT),
            autoescape=select_autoescape(["html", "j2", "html.j2"]),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=["jinja2.ext.i18n", "jinja2.ext.do"],
            enable_async=True,
        )
        # Wire i18n into Jinja so ``{% trans %}`` and ``{{ _("...") }}`` work in templates.
        # Using a per-render closure keeps the locale request-scoped.

    def render(
        self,
        *,
        template: str,
        locale: str,
        context: dict[str, object] | None = None,
    ) -> RenderedEmail:
        """Render the three parts. Falls back to the default locale if missing."""
        ctx = self._build_context(context, locale=locale)

        def _load(part: str) -> tuple[str, str]:
            """Load ``<template>/<locale>/<part>.j2``, falling back to default locale."""
            try:
                tpl = self._env.get_template(f"{template}/{locale}/{part}.j2")
                return tpl.render(**ctx), locale
            except TemplateNotFound:
                EMAIL_LOCALE_FALLBACK_TOTAL.labels(template=template, locale=locale).inc()
                tpl = self._env.get_template(f"{template}/{self._fallback}/{part}.j2")
                return tpl.render(**ctx), self._fallback

        subject_text, subject_locale = _load("subject")
        text_body_text, _ = _load("txt")
        html_body_text, _ = _load("html")

        return RenderedEmail(
            subject=subject_text.strip(),
            text_body=text_body_text,
            html_body=html_body_text,
            locale=subject_locale,
        )

    def _build_context(
        self,
        ctx: dict[str, object] | None,
        *,
        locale: str,
    ) -> dict[str, object]:
        """Inject helpers into the template context."""
        translator = self._translator

        def _gettext(key: str, **params: object) -> str:
            return translator.gettext(key, locale=locale, **params)

        def _ngettext(singular: str, plural: str, n: int, **params: object) -> str:
            return translator.ngettext(singular, plural, n, locale=locale, **params)

        out: dict[str, object] = {
            "_": _gettext,
            "gettext": _gettext,
            "ngettext": _ngettext,
            "is_rtl": translator.is_rtl(locale),
            "locale": locale,
            "lang_dir": "rtl" if translator.is_rtl(locale) else "ltr",
            "app_name": self._settings.app_name,
            "from_address": self._settings.email_from_address,
            "from_name": self._settings.email_from_name,
        }
        if ctx:
            out.update(ctx)
        return out


# Re-export for symmetry: tests can pass a ``BaseLoader`` for an in-memory env.
__all__ = ["BaseLoader", "RenderedEmail", "TemplateRenderer"]
