"""Settings load + validate without touching the network."""

from __future__ import annotations

import pytest

from app.core.config import Settings, get_settings


@pytest.mark.unit
def test_settings_load(settings: Settings) -> None:
    assert settings.app_name
    assert settings.app_version
    assert "en" in settings.locales_enabled
    assert "ar" in settings.locales_enabled
    assert settings.locale_default == "en"
    assert settings.is_test is True


@pytest.mark.unit
def test_get_settings_is_cached() -> None:
    a = get_settings()
    b = get_settings()
    assert a is b


@pytest.mark.unit
def test_locales_enabled_accepts_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALES_ENABLED", "en, ar, fr")
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.locales_enabled == ["en", "ar", "fr"]
    finally:
        get_settings.cache_clear()
