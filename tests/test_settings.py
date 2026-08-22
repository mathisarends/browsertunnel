import pytest
from pydantic import ValidationError

from backend.settings import BrowserSettings


def test_browser_settings_defaults() -> None:
    settings = BrowserSettings(_env_file=None)

    assert settings.width == 1600
    assert settings.height == 900
    assert settings.headless is True


def test_browser_settings_load_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BROWSER_CDP_URL", "")
    monkeypatch.setenv("BROWSER_HEADLESS", "false")
    monkeypatch.setenv("BROWSER_WIDTH", "1280")
    monkeypatch.setenv("BROWSER_SCREENCAST_QUALITY", "65")

    settings = BrowserSettings(_env_file=None)

    assert settings.cdp_url is None
    assert settings.headless is False
    assert settings.width == 1280
    assert settings.screencast_quality == 65


def test_browser_settings_validate_quality() -> None:
    with pytest.raises(ValidationError):
        BrowserSettings(screencast_quality=101, _env_file=None)
