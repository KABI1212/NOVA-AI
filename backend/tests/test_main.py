import asyncio

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


def test_api_status_includes_runtime_capabilities(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module.ai_service,
        "get_runtime_capabilities",
        lambda: {
            "configured_provider": "auto",
            "configured_model": None,
            "text_ready": True,
            "available_text_providers": ["google"],
            "preferred_text_provider": "google",
            "image_ready": False,
            "available_image_providers": [],
            "preferred_image_provider": None,
        },
    )
    monkeypatch.setattr(
        main_module.email_service,
        "get_delivery_status",
        lambda: {
            "configured_provider": "smtp",
            "provider": "smtp",
            "delivery_mode": "email",
            "ready": True,
        },
    )

    payload = asyncio.run(main_module.api_status())

    assert payload["status"] == "running"
    assert payload["capabilities"]["ai"]["text_ready"] is True
    assert payload["capabilities"]["auth"]["email_ready"] is True
    assert payload["capabilities"]["auth"]["email"]["provider"] == "smtp"
