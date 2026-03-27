from __future__ import annotations

import asyncio
import importlib

from config.settings import settings
import routes.chat as chat_module
import routes.document as document_module
from services.ai_service import ai_service

ai_service_module = importlib.import_module("services.ai_service")


def test_ai_service_generate_image_without_key_returns_no_placeholder(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    async def scenario() -> None:
        result = await ai_service.generate_image("A cinematic tiger in rain")
        assert result == []

    asyncio.run(scenario())


def test_ai_service_generate_image_uses_gemini_when_google_is_configured(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "AI_PROVIDER", "google")

    async def fake_generate(prompt: str, size: str = "1024x1024", n: int = 1):
        assert prompt == "A cinematic tiger in rain"
        assert size == "1024x1024"
        assert n == 1
        return ["data:image/png;base64,gemini-image"]

    monkeypatch.setattr(ai_service_module, "_generate_image_with_google", fake_generate)

    async def scenario() -> None:
        result = await ai_service.generate_image("A cinematic tiger in rain")
        assert result == ["data:image/png;base64,gemini-image"]

    asyncio.run(scenario())


def test_generate_images_best_effort_prefers_web_references_for_answer_prompts(
    monkeypatch,
) -> None:
    async def fake_ground(prompt: str):
        return "Create a faithful diagram from this exact answer", [
            "https://example.com/web-image.png",
            "https://example.com/diagram-reference.png",
        ]

    async def fake_generate(prompt: str):
        raise AssertionError("model image generation should not run when web references exist")

    monkeypatch.setattr(chat_module, "_ground_answer_image_prompt", fake_ground)
    monkeypatch.setattr(chat_module.ai_service, "generate_image", fake_generate)

    async def scenario() -> None:
        result = await chat_module._generate_images_best_effort(
            "User prompt: CPU scheduling\nAssistant answer: Round robin balances fairness."
        )
        assert result == [
            "https://example.com/web-image.png",
            "https://example.com/diagram-reference.png",
        ]

    asyncio.run(scenario())


def test_generate_images_best_effort_falls_back_to_model_generation_when_web_references_are_missing(
    monkeypatch,
) -> None:
    async def fake_ground(prompt: str):
        return "Create a faithful diagram from this exact answer", []

    async def fake_generate(prompt: str):
        return ["data:image/png;base64,real-generated-image"]

    monkeypatch.setattr(chat_module, "_ground_answer_image_prompt", fake_ground)
    monkeypatch.setattr(chat_module.ai_service, "generate_image", fake_generate)

    async def scenario() -> None:
        result = await chat_module._generate_images_best_effort(
            "User prompt: Binary search\nAssistant answer: Binary search repeatedly halves the search space."
        )
        assert result == ["data:image/png;base64,real-generated-image"]

    asyncio.run(scenario())


def test_generate_images_best_effort_returns_empty_when_no_real_visuals_are_available(
    monkeypatch,
) -> None:
    async def fake_ground(prompt: str):
        return "Create a faithful diagram from this exact answer", []

    async def fake_generate(prompt: str):
        return []

    monkeypatch.setattr(chat_module, "_ground_answer_image_prompt", fake_ground)
    monkeypatch.setattr(chat_module.ai_service, "generate_image", fake_generate)

    async def scenario() -> None:
        result = await chat_module._generate_images_best_effort(
            "User prompt: Binary search\nAssistant answer: Binary search repeatedly halves the search space."
        )
        assert result == []

    asyncio.run(scenario())


def test_document_answer_images_best_effort_prefers_web_results(
    monkeypatch,
) -> None:
    async def fake_search(query: str, max_results: int = 6):
        return [
            {
                "title": "SSH architecture diagram",
                "url": "https://example.com/ssh-architecture",
                "image_url": "https://example.com/ssh-architecture.png",
                "thumbnail_url": "",
                "width": 1600,
                "height": 1200,
                "source": "Example",
            }
        ]

    async def fake_generate(prompt: str):
        raise AssertionError("model image generation should not run when web results exist")

    monkeypatch.setattr(document_module, "search_web_images", fake_search)
    monkeypatch.setattr(document_module.ai_service, "generate_image", fake_generate)

    async def scenario() -> None:
        result = await document_module._generate_document_answer_images_best_effort(
            "Draw a neat diagram of SSH architecture for 16 marks.",
            "SSH architecture includes the transport layer, user authentication layer, and connection layer over TCP.",
        )
        assert result == ["https://example.com/ssh-architecture.png"]

    asyncio.run(scenario())


def test_document_answer_images_best_effort_falls_back_to_model_generation(
    monkeypatch,
) -> None:
    async def fake_search(query: str, max_results: int = 6):
        return []

    async def fake_generate(prompt: str):
        return ["data:image/png;base64,document-diagram"]

    monkeypatch.setattr(document_module, "search_web_images", fake_search)
    monkeypatch.setattr(document_module.ai_service, "generate_image", fake_generate)

    async def scenario() -> None:
        result = await document_module._generate_document_answer_images_best_effort(
            "Draw a neat diagram of SSL handshake.",
            "The SSL handshake starts with client hello and server hello, then certificate exchange, key exchange, and finished messages.",
        )
        assert result == ["data:image/png;base64,document-diagram"]

    asyncio.run(scenario())


def test_resolve_effective_mode_switches_chat_image_requests() -> None:
    assert (
        chat_module._resolve_effective_mode(
            "chat",
            "Generate an image of a dog and a cat sleeping together",
        )
        == "image"
    )
    assert (
        chat_module._resolve_effective_mode(
            "chat",
            "Explain the difference between dogs and cats",
        )
        == "chat"
    )
    assert (
        chat_module._resolve_effective_mode(
            "chat",
            "Illustrate a golden retriever and a tabby cat curled up together on a blanket",
        )
        == "image"
    )
    assert (
        chat_module._resolve_effective_mode(
            "chat",
            "Create timetable for monday and tuesday",
        )
        == "chat"
    )
    assert (
        chat_module._resolve_effective_mode(
            "chat",
            "A cute golden retriever puppy sitting on green grass in a sunny park, soft natural lighting, highly detailed fur, realistic style, shallow depth of field, 4k quality",
        )
        == "image"
    )


def test_response_max_tokens_expands_for_multi_question_exam_prompts() -> None:
    assert (
        chat_module._response_max_tokens(
            "Answer all questions from this question paper. There are 5 questions of 2 marks and 3 questions of 8 marks.",
            "chat",
        )
        >= 16384
    )


def test_response_max_tokens_expands_for_single_high_mark_questions() -> None:
    assert (
        chat_module._response_max_tokens(
            "Explain SSH architecture for 16 marks.",
            "chat",
        )
        >= 8192
    )


def test_build_regenerate_instruction_uses_previous_answer_as_draft() -> None:
    instruction = chat_module._build_regenerate_instruction(
        "Dogs are friendly pets that often enjoy play and companionship."
    )

    assert "Previous assistant answer draft" in instruction
    assert "Dogs are friendly pets" in instruction
    assert "Treat the previous assistant answer as a draft to improve." in instruction


def test_build_regenerate_instruction_without_previous_answer_uses_base_instruction() -> None:
    instruction = chat_module._build_regenerate_instruction("")

    assert instruction == chat_module.REGENERATE_VARIATION_INSTRUCTION


def test_resolve_regenerated_text_keeps_previous_useful_answer_on_fallback() -> None:
    result = chat_module._resolve_regenerated_text(
        chat_module.FALLBACK_MESSAGE,
        "Binary search runs in logarithmic time on sorted input.",
    )

    assert result == "Binary search runs in logarithmic time on sorted input."
