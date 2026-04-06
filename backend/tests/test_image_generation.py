from __future__ import annotations

import asyncio
import importlib

import pytest

from config.settings import settings
import routes.chat as chat_module
import routes.document as document_module
import routes.image as image_module
from services.ai_service import ai_service
from fastapi import HTTPException

ai_service_module = importlib.import_module("services.ai_service")


@pytest.fixture(autouse=True)
def _reset_image_provider_state(monkeypatch):
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    ai_service_module._IMAGE_PROVIDER_DISABLED_UNTIL.clear()


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
        assert "A cinematic tiger in rain" in prompt
        assert size == "1024x1024"
        assert n == 1
        return ["data:image/png;base64,gemini-image"]

    monkeypatch.setattr(ai_service_module, "_generate_image_with_google", fake_generate)

    async def scenario() -> None:
        result = await ai_service.generate_image("A cinematic tiger in rain")
        assert result == ["data:image/png;base64,gemini-image"]

    asyncio.run(scenario())


def test_resolve_image_provider_prefers_google_when_multiple_keys_exist(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    assert ai_service_module._resolve_image_provider() == "google"


def test_ai_service_enhance_image_prompt_falls_back_to_heuristic_when_no_provider_ready(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")

    async def scenario() -> None:
        revised = await ai_service.enhance_image_prompt(
            "Minimalist sneaker on a reflective platform",
            size="1792x1024",
            quality="hd",
            style="vivid",
            prompt_target="canva",
        )
        assert "Minimalist sneaker on a reflective platform" in revised
        assert "Aspect ratio target: 16:9." in revised
        assert "Quality target:" in revised

    asyncio.run(scenario())


def test_ai_service_generate_image_result_returns_provider_and_revised_prompt(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    async def fake_enhance(prompt: str, **kwargs):
        assert prompt == "A premium running shoe on marble"
        return "Enhanced studio product shot prompt"

    async def fake_generate(prompt: str, size: str = "1024x1024", n: int = 1, quality: str = "standard", style: str = "vivid"):
        assert prompt == "Enhanced studio product shot prompt"
        assert size == "1024x1024"
        assert n == 1
        assert quality == "hd"
        assert style == "natural"
        return ["data:image/png;base64,openai-image"]

    monkeypatch.setattr(ai_service, "enhance_image_prompt", fake_enhance)
    monkeypatch.setattr(ai_service_module, "_generate_image_with_openai", fake_generate)

    async def scenario() -> None:
        result = await ai_service.generate_image_result(
            "A premium running shoe on marble",
            quality="hd",
            style="natural",
            provider="chatgpt",
            prompt_target="chatgpt",
        )
        assert result["provider"] == "openai"
        assert result["provider_label"] == "ChatGPT"
        assert result["revised_prompt"] == "Enhanced studio product shot prompt"
        assert result["images"] == ["data:image/png;base64,openai-image"]

    asyncio.run(scenario())


def test_ai_service_generate_image_result_auto_falls_back_to_openai_when_google_fails(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    async def fake_enhance(prompt: str, **kwargs):
        return prompt

    async def fake_google(prompt: str, size: str = "1024x1024", n: int = 1):
        raise RuntimeError("RESOURCE_EXHAUSTED: quota exceeded")

    async def fake_openai(prompt: str, size: str = "1024x1024", n: int = 1, quality: str = "standard", style: str = "vivid"):
        return ["data:image/png;base64,openai-fallback"]

    monkeypatch.setattr(ai_service, "enhance_image_prompt", fake_enhance)
    monkeypatch.setattr(ai_service_module, "_generate_image_with_google", fake_google)
    monkeypatch.setattr(ai_service_module, "_generate_image_with_openai", fake_openai)

    async def scenario() -> None:
        result = await ai_service.generate_image_result(
            "A glowing lantern on a table",
            provider="auto",
            enhance_prompt=True,
        )
        assert result["provider"] == "openai"
        assert result["images"] == ["data:image/png;base64,openai-fallback"]

    asyncio.run(scenario())


def test_ai_service_generate_image_result_skips_invalid_non_image_payloads(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    async def fake_enhance(prompt: str, **kwargs):
        return prompt

    async def fake_google(prompt: str, size: str = "1024x1024", n: int = 1):
        return [
            "services.rate_limit_service Redis unavailable for rate limiting",
            "%5Bservices.ai_service%5D+provider%3Dgoogle",
        ]

    async def fake_openai(prompt: str, size: str = "1024x1024", n: int = 1, quality: str = "standard", style: str = "vivid"):
        return ["data:image/png;base64,clean-openai-image"]

    monkeypatch.setattr(ai_service, "enhance_image_prompt", fake_enhance)
    monkeypatch.setattr(ai_service_module, "_generate_image_with_google", fake_google)
    monkeypatch.setattr(ai_service_module, "_generate_image_with_openai", fake_openai)

    async def scenario() -> None:
        result = await ai_service.generate_image_result(
            "Network security diagram",
            provider="auto",
            enhance_prompt=True,
        )
        assert result["provider"] == "openai"
        assert result["images"] == ["data:image/png;base64,clean-openai-image"]

    asyncio.run(scenario())


def test_image_provider_is_temporarily_disabled_after_quota_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_service_module.time, "monotonic", lambda: 100.0)

    ai_service_module._temporarily_disable_image_provider(
        "google",
        RuntimeError("RESOURCE_EXHAUSTED: quota exceeded"),
    )

    assert ai_service_module._image_provider_temporarily_disabled("google") is True

    monkeypatch.setattr(ai_service_module.time, "monotonic", lambda: 1000.0)
    assert ai_service_module._image_provider_temporarily_disabled("google") is False


def test_resolve_image_provider_chain_skips_temporarily_disabled_provider(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(ai_service_module.time, "monotonic", lambda: 100.0)

    ai_service_module._temporarily_disable_image_provider(
        "google",
        RuntimeError("RESOURCE_EXHAUSTED: quota exceeded"),
    )

    assert ai_service_module._resolve_image_provider_chain() == ["openai"]


def test_ai_service_generate_image_result_auto_reports_both_provider_failures(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "AI_IMAGE_PROVIDER", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    async def fake_enhance(prompt: str, **kwargs):
        return prompt

    async def fake_google(prompt: str, size: str = "1024x1024", n: int = 1):
        raise RuntimeError("RESOURCE_EXHAUSTED: quota exceeded")

    async def fake_openai(prompt: str, size: str = "1024x1024", n: int = 1, quality: str = "standard", style: str = "vivid"):
        raise RuntimeError("billing_hard_limit_reached")

    monkeypatch.setattr(ai_service, "enhance_image_prompt", fake_enhance)
    monkeypatch.setattr(ai_service_module, "_generate_image_with_google", fake_google)
    monkeypatch.setattr(ai_service_module, "_generate_image_with_openai", fake_openai)

    async def scenario() -> None:
        try:
            await ai_service.generate_image_result(
                "A glowing lantern on a table",
                provider="auto",
                enhance_prompt=True,
                raise_on_error=True,
            )
        except RuntimeError as exc:
            message = str(exc)
            assert "All image providers failed." in message
            assert "Gemini: quota exhausted" in message
            assert "ChatGPT: billing hard limit reached" in message
        else:
            raise AssertionError("Expected RuntimeError")

    asyncio.run(scenario())


def test_ai_service_generate_image_result_auto_falls_back_to_openrouter_when_direct_providers_fail(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-key")

    async def fake_enhance(prompt: str, **kwargs):
        return prompt

    async def fake_google(prompt: str, size: str = "1024x1024", n: int = 1):
        raise RuntimeError("RESOURCE_EXHAUSTED: quota exceeded")

    async def fake_openrouter(prompt: str, size: str = "1024x1024", n: int = 1, quality: str = "standard"):
        assert quality == "standard"
        return ["data:image/png;base64,openrouter-image"]

    async def fake_openai(prompt: str, size: str = "1024x1024", n: int = 1, quality: str = "standard", style: str = "vivid"):
        raise RuntimeError("billing_hard_limit_reached")

    monkeypatch.setattr(ai_service, "enhance_image_prompt", fake_enhance)
    monkeypatch.setattr(ai_service_module, "_generate_image_with_google", fake_google)
    monkeypatch.setattr(ai_service_module, "_generate_image_with_openrouter", fake_openrouter)
    monkeypatch.setattr(ai_service_module, "_generate_image_with_openai", fake_openai)

    async def scenario() -> None:
        result = await ai_service.generate_image_result(
            "A glowing lantern on a table",
            provider="auto",
            enhance_prompt=True,
        )
        assert result["provider"] == "openrouter"
        assert result["provider_label"] == "OpenRouter"
        assert result["images"] == ["data:image/png;base64,openrouter-image"]

    asyncio.run(scenario())


def test_openrouter_image_models_prefer_configured_model_then_cheaper_fallbacks(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_IMAGE_MODEL", "google/gemini-2.5-flash-image")

    models = ai_service_module._openrouter_image_models()

    assert models[0] == "google/gemini-2.5-flash-image"
    assert "sourceful/riverflow-v2-fast-preview" in models
    assert "sourceful/riverflow-v2-standard-preview" in models


def test_summarize_image_provider_error_compacts_openrouter_credit_message() -> None:
    summary = ai_service_module._summarize_image_provider_error(
        RuntimeError("This request requires more credits, or fewer tokens. You requested up to 29366 tokens, but can only afford 6703.")
    )

    assert summary == "insufficient credits"


def test_raise_image_http_error_maps_quota_to_429() -> None:
    try:
        image_module._raise_image_http_error(RuntimeError("RESOURCE_EXHAUSTED: quota exceeded"))
    except HTTPException as exc:
        assert exc.status_code == 429
        assert "quota" in str(exc.detail).lower()
    else:
        raise AssertionError("Expected HTTPException")


def test_raise_image_http_error_maps_billing_to_402() -> None:
    try:
        image_module._raise_image_http_error(RuntimeError("billing_hard_limit_reached"))
    except HTTPException as exc:
        assert exc.status_code == 402
        assert "billing" in str(exc.detail).lower()
    else:
        raise AssertionError("Expected HTTPException")


def test_raise_image_http_error_maps_multi_provider_failure_to_503() -> None:
    try:
        image_module._raise_image_http_error(
            RuntimeError("All image providers failed. Gemini: quota exhausted; ChatGPT: billing hard limit reached")
        )
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "Gemini: quota exhausted" in str(exc.detail)
        assert "ChatGPT: billing hard limit reached" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException")


def test_raise_image_http_error_maps_insufficient_credits_to_402() -> None:
    try:
        image_module._raise_image_http_error(RuntimeError("OpenRouter: insufficient credits"))
    except HTTPException as exc:
        assert exc.status_code == 402
        assert "billing" in str(exc.detail).lower()
    else:
        raise AssertionError("Expected HTTPException")


def test_raise_image_http_error_maps_credit_shortage_message_to_402() -> None:
    try:
        image_module._raise_image_http_error(
            RuntimeError("This request requires more credits, or fewer tokens. You requested up to 29366 tokens, but can only afford 6703.")
        )
    except HTTPException as exc:
        assert exc.status_code == 402
        assert "billing" in str(exc.detail).lower()
    else:
        raise AssertionError("Expected HTTPException")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/image.png",
        "http://localhost/image.png",
        "http://[::1]/image.png",
        "http://10.0.0.5/image.png",
    ],
)
def test_validate_proxy_url_blocks_private_hosts(url: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        image_module._validate_proxy_url(url)

    assert exc_info.value.status_code == 400
    assert "not allowed" in str(exc_info.value.detail).lower()


def test_fetch_proxy_image_rejects_non_image_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeStreamResponse:
        status_code = 200
        headers = {"content-type": "text/html", "content-length": "18"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self):
            yield b"<html>nope</html>"

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            assert kwargs["follow_redirects"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method: str, url: str):
            assert method == "GET"
            assert url == "https://example.com/file"
            return FakeStreamResponse()

    monkeypatch.setattr(image_module.httpx, "AsyncClient", FakeAsyncClient)

    async def scenario() -> None:
        with pytest.raises(HTTPException) as exc_info:
            await image_module._fetch_proxy_image("https://example.com/file")

        assert exc_info.value.status_code == 400
        assert "did not return an image" in str(exc_info.value.detail).lower()

    asyncio.run(scenario())


def test_proxy_image_preserves_upstream_media_type(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(url: str) -> tuple[bytes, str]:
        assert url == "https://example.com/photo.jpg"
        return b"jpeg-bytes", "image/jpeg"

    monkeypatch.setattr(image_module, "_fetch_proxy_image", fake_fetch)

    async def scenario() -> None:
        response = await image_module.proxy_image(
            "https://example.com/photo.jpg",
            current_user=object(),
        )

        assert response.media_type == "image/jpeg"
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        assert b"".join(chunks) == b"jpeg-bytes"

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


def test_generate_images_best_effort_skips_cleanly_when_no_image_provider_is_available(
    monkeypatch,
) -> None:
    async def forbidden_generate(prompt: str):
        raise AssertionError("image generation should not run when no image provider is available")

    monkeypatch.setattr(chat_module.ai_service, "has_available_image_provider", lambda provider=None: False)
    monkeypatch.setattr(chat_module.ai_service, "generate_image", forbidden_generate)

    async def scenario() -> None:
        result = await chat_module._generate_images_best_effort("A clean diagram of binary search")
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
