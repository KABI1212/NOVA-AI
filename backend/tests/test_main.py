import pytest

import main as main_module


def test_should_enable_reload_returns_false_when_debug_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "DEBUG", False)

    assert main_module._should_enable_reload() is False


def test_should_enable_reload_disables_32bit_windows(monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "DEBUG", True)
    monkeypatch.setattr(main_module.sys, "platform", "win32")
    monkeypatch.setattr(main_module.platform, "architecture", lambda: ("32bit", "WindowsPE"))

    with pytest.warns(RuntimeWarning, match="Uvicorn reload is disabled"):
        assert main_module._should_enable_reload() is False


def test_should_enable_reload_keeps_reload_for_non_windows_64bit(monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "DEBUG", True)
    monkeypatch.setattr(main_module.sys, "platform", "linux")
    monkeypatch.setattr(main_module.platform, "architecture", lambda: ("64bit", "ELF"))

    assert main_module._should_enable_reload() is True
