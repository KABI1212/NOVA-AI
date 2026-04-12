from __future__ import annotations

import asyncio
import importlib

from services.ai_service import ai_service

ai_service_module = importlib.import_module("services.ai_service")


def test_generate_explanation_includes_presentation_style(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_complete(messages, provider=None, model=None, temperature=None, max_tokens=None, use_case=None):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(ai_service_module, "_complete_non_stream", fake_complete)

    async def scenario() -> None:
        result = await ai_service.generate_explanation(
            "Explain how neural networks work",
            mode="deep",
            audience="student",
            detail="detailed",
        )
        assert result == "ok"

    asyncio.run(scenario())

    system_prompt = captured["messages"][0]["content"]
    assert "Make heading and subheading text bold" in system_prompt
    assert "add relevant emojis" in system_prompt
    assert "supportive friend" in system_prompt


def test_generate_code_uses_codex_grade_prompt(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_complete(messages, provider=None, model=None, temperature=None, max_tokens=None, use_case=None):
        captured["messages"] = messages
        captured["use_case"] = use_case
        return "ok"

    monkeypatch.setattr(ai_service_module, "_complete_non_stream", fake_complete)

    async def scenario() -> None:
        result = await ai_service.generate_code("Write a function to reverse a string.", language="python")
        assert result == "ok"

    asyncio.run(scenario())

    system_prompt = captured["messages"][0]["content"]
    assert "Codex-grade programming engine" in system_prompt
    assert "production-ready" in system_prompt
    assert captured["use_case"] == "coding"


def test_document_answers_include_presentation_style(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_complete(messages, provider=None, model=None, temperature=None, max_tokens=None, use_case=None):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(ai_service_module, "_complete_non_stream", fake_complete)

    async def scenario() -> None:
        result = await ai_service.answer_question_from_document(
            "What are the key findings?",
            "The document says the main findings were faster delivery and lower cost.",
        )
        assert result == "ok"

    asyncio.run(scenario())

    system_prompt = captured["messages"][0]["content"]
    assert "Make heading and subheading text bold" in system_prompt
    assert "skip them for sensitive, formal, legal, medical, or financial replies" in system_prompt


def test_document_answers_include_contextual_exam_and_diagram_guidance(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_complete(messages, provider=None, model=None, temperature=None, max_tokens=None, use_case=None):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(ai_service_module, "_complete_non_stream", fake_complete)

    async def scenario() -> None:
        result = await ai_service.answer_question_from_document(
            "Draw a neat diagram of SSH architecture for a 16 mark assignment answer.",
            "SSH includes the authentication protocol, connection protocol, and transport layer over TCP/IP.",
        )
        assert result == "ok"

    asyncio.run(scenario())

    system_prompts = [
        message["content"]
        for message in captured["messages"]
        if message.get("role") == "system"
    ]
    assert any(
        "The user wants a clear diagram-style answer." in content
        for content in system_prompts
    )
    assert any(
        "Match the depth to this 16-mark question." in content
        for content in system_prompts
    )
    assert any(
        "fuller, more polished, and more submission-ready" in content
        for content in system_prompts
    )


def test_document_answers_raise_max_tokens_for_8_mark_questions(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_complete(messages, provider=None, model=None, temperature=None, max_tokens=None, use_case=None):
        captured["messages"] = messages
        captured["max_tokens"] = max_tokens
        return "ok"

    monkeypatch.setattr(ai_service_module, "_complete_non_stream", fake_complete)

    async def scenario() -> None:
        result = await ai_service.answer_question_from_document(
            "Explain SSL record protocol for 8 marks.",
            "The SSL record protocol performs fragmentation, optional compression, MAC addition, encryption, and transmission.",
        )
        assert result == "ok"

    asyncio.run(scenario())

    assert int(captured["max_tokens"]) >= 5120


def test_document_answers_raise_max_tokens_for_16_mark_questions(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_complete(messages, provider=None, model=None, temperature=None, max_tokens=None, use_case=None):
        captured["messages"] = messages
        captured["max_tokens"] = max_tokens
        return "ok"

    monkeypatch.setattr(ai_service_module, "_complete_non_stream", fake_complete)

    async def scenario() -> None:
        result = await ai_service.answer_question_from_document(
            "Explain zero trust architecture for 16 marks.",
            "Zero trust verifies every request, applies least privilege, and continuously validates identity, device state, and policy.",
        )
        assert result == "ok"

    asyncio.run(scenario())

    assert int(captured["max_tokens"]) >= 8192


def test_analyze_image_prefers_openai_when_available(monkeypatch) -> None:
    async def fake_openai(prompt, image_bytes, mime_type="image/png", model=None, max_tokens=None):
        assert prompt == "What is in this image?"
        assert image_bytes == b"image-bytes"
        assert mime_type == "image/png"
        return "A lock icon is visible."

    async def fake_google(prompt, image_bytes, mime_type="image/png", model=None, max_tokens=None):
        raise AssertionError("google fallback should not run when openai succeeds")

    monkeypatch.setattr(ai_service_module, "_analyze_image_with_openai", fake_openai)
    monkeypatch.setattr(ai_service_module, "_analyze_image_with_google", fake_google)
    monkeypatch.setattr(ai_service_module, "_resolve_provider", lambda: "openai")

    async def scenario() -> None:
        result = await ai_service.analyze_image("What is in this image?", b"image-bytes", "image/png")
        assert result == "A lock icon is visible."

    asyncio.run(scenario())


def test_analyze_image_falls_back_to_google_when_openai_fails(monkeypatch) -> None:
    async def fake_openai(prompt, image_bytes, mime_type="image/png", model=None, max_tokens=None):
        raise RuntimeError("openai unavailable")

    async def fake_google(prompt, image_bytes, mime_type="image/png", model=None, max_tokens=None):
        return "The image shows a certificate flow diagram."

    monkeypatch.setattr(ai_service_module, "_analyze_image_with_openai", fake_openai)
    monkeypatch.setattr(ai_service_module, "_analyze_image_with_google", fake_google)
    monkeypatch.setattr(ai_service_module, "_resolve_provider", lambda: "openai")

    async def scenario() -> None:
        result = await ai_service.analyze_image("Explain this diagram.", b"image-bytes", "image/png")
        assert result == "The image shows a certificate flow diagram."

    asyncio.run(scenario())
