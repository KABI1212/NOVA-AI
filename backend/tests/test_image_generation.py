from __future__ import annotations

import asyncio

from config.settings import settings
import routes.chat as chat_module
from services.ai_service import ai_service


def test_ai_service_generate_image_without_key_returns_no_placeholder(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    async def scenario() -> None:
        result = await ai_service.generate_image("A cinematic tiger in rain")
        assert result == []

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
