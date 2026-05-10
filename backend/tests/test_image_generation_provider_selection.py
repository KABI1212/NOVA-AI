from __future__ import annotations

import importlib

from config.settings import settings

ai_service_module = importlib.import_module("services.ai_service")


def test_explicit_auto_image_provider_ignores_configured_override(monkeypatch) -> None:
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(settings, "KIE_API_KEY", "kie-key")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    assert ai_service_module._resolve_image_provider("auto") == "google"
    assert ai_service_module._resolve_image_provider_chain("auto") == [
        "google",
        "kie",
        "openrouter",
        "openai",
    ]


def test_implicit_image_provider_still_respects_configured_override(monkeypatch) -> None:
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(settings, "KIE_API_KEY", "kie-key")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    assert ai_service_module._resolve_image_provider() == "openrouter"
    assert ai_service_module._resolve_image_provider_chain() == [
        "openrouter",
        "google",
        "kie",
        "openai",
    ]


def test_kie_image_provider_can_be_selected_explicitly(monkeypatch) -> None:
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "")
    monkeypatch.setattr(settings, "KIE_API_KEY", "kie-key")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    assert ai_service_module._resolve_image_provider("kie") == "kie"
    assert ai_service_module._resolve_image_provider_chain("kie") == ["kie"]
