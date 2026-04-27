"""Locale negotiation + translator basics."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.i18n import (
    BabelTranslator,
    EchoTranslator,
    negotiate_accept_language,
    resolve_locale,
)


@pytest.mark.unit
def test_negotiate_picks_highest_quality() -> None:
    header = "fr;q=0.4, ar;q=0.9, en;q=0.5"
    chosen = negotiate_accept_language(header, ["en", "ar"], "en")
    assert chosen == "ar"


@pytest.mark.unit
def test_negotiate_falls_back_to_default() -> None:
    chosen = negotiate_accept_language("fr;q=1.0", ["en", "ar"], "en")
    assert chosen == "en"


@pytest.mark.unit
def test_negotiate_handles_primary_subtag() -> None:
    chosen = negotiate_accept_language("ar-SA;q=1.0", ["en", "ar"], "en")
    assert chosen == "ar"


@pytest.mark.unit
def test_resolve_locale_priority(settings: Settings) -> None:
    out = resolve_locale(
        query_value="ar",
        user_pref="en",
        accept_language="en",
        settings=settings,
    )
    assert out == "ar"  # query wins

    out = resolve_locale(
        query_value=None,
        user_pref="ar",
        accept_language="en",
        settings=settings,
    )
    assert out == "ar"  # user pref wins over header


@pytest.mark.unit
def test_echo_translator_returns_keys() -> None:
    t = EchoTranslator()
    assert t.gettext("auth.invalid_token") == "auth.invalid_token"
    assert t.is_rtl("ar") is True
    assert t.is_rtl("en") is False


@pytest.mark.unit
def test_babel_translator_falls_back_when_catalog_missing(settings: Settings) -> None:
    t = BabelTranslator(settings=settings)
    # Even if compile didn't run, gettext returns the key (a string), not None.
    out = t.gettext("auth.invalid_token", locale="en")
    assert isinstance(out, str)
    assert t.is_rtl("ar") is True
