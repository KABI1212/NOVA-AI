from __future__ import annotations

import asyncio
import importlib
import sys
from types import SimpleNamespace

import pytest

ai_service_module = importlib.import_module("services.ai_service")


class _FakeAnthropicStream:
    def __init__(self, attempt: int, *, fail_after_text: bool = False) -> None:
        self.attempt = attempt
        self.fail_after_text = fail_after_text
        self.text_stream = self._text_stream()

    async def __aenter__(self):
        if self.attempt == 1 and not self.fail_after_text:
            raise RuntimeError("stream dropped before content")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def _text_stream(self):
        yield "Hello"
        if self.fail_after_text:
            raise RuntimeError("stream dropped after content")


def test_anthropic_stream_retries_when_interrupted_before_first_token(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = []

    class FakeMessages:
        def stream(self, **kwargs):
            attempts.append(kwargs)
            return _FakeAnthropicStream(len(attempts))

    class FakeAsyncAnthropic:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    monkeypatch.setattr(ai_service_module.settings, "ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setattr(ai_service_module.settings, "AI_STREAM_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(ai_service_module.settings, "AI_STREAM_RETRY_BACKOFF_SECONDS", 0)
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(AsyncAnthropic=FakeAsyncAnthropic))

    async def scenario() -> None:
        chunks = [
            token
            async for token in ai_service_module._stream_anthropic(
                [{"role": "user", "content": "Hi"}],
                "claude-test",
                0.2,
                4096,
            )
        ]
        assert chunks == ["Hello"]
        assert len(attempts) == 2

    asyncio.run(scenario())


def test_anthropic_stream_does_not_retry_after_partial_text(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = []

    class FakeMessages:
        def stream(self, **kwargs):
            attempts.append(kwargs)
            return _FakeAnthropicStream(len(attempts), fail_after_text=True)

    class FakeAsyncAnthropic:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    monkeypatch.setattr(ai_service_module.settings, "ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setattr(ai_service_module.settings, "AI_STREAM_RETRY_ATTEMPTS", 3)
    monkeypatch.setattr(ai_service_module.settings, "AI_STREAM_RETRY_BACKOFF_SECONDS", 0)
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(AsyncAnthropic=FakeAsyncAnthropic))

    async def scenario() -> None:
        chunks = []
        with pytest.raises(RuntimeError, match="after content"):
            async for token in ai_service_module._stream_anthropic(
                [{"role": "user", "content": "Hi"}],
                "claude-test",
                0.2,
                4096,
            ):
                chunks.append(token)
        assert chunks == ["Hello"]
        assert len(attempts) == 1

    asyncio.run(scenario())


def test_complete_non_stream_recovers_from_partial_failure_when_provider_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def partial_failure(messages, model, temperature, max_tokens):
        yield "Half answer"
        raise RuntimeError("stream dropped")

    async def successful_provider(messages, model, temperature, max_tokens):
        yield "Recovered answer"

    monkeypatch.setattr(ai_service_module.settings, "AI_AUTO_MAX_PROVIDER_ATTEMPTS", 6)
    monkeypatch.setattr(ai_service_module, "_provider_available", lambda provider: True)
    monkeypatch.setattr(
        ai_service_module,
        "_provider_chain",
        lambda provider=None, use_case=None: ["openai", "google"],
    )
    monkeypatch.setattr(ai_service_module, "_configured_provider_override", lambda: None)
    monkeypatch.setattr(ai_service_module, "_resolve_provider", lambda: "openai")
    monkeypatch.setattr(
        ai_service_module,
        "_model_for_provider",
        lambda current_provider, requested_provider, model: model if current_provider == requested_provider else None,
    )
    monkeypatch.setattr(
        ai_service_module,
        "_PROVIDER_STREAM_MAP",
        {"openai": partial_failure, "google": successful_provider},
    )

    async def scenario() -> None:
        result = await ai_service_module._complete_non_stream(
            [{"role": "user", "content": "Answer all questions from this paper."}],
            provider="openai",
            model="test-model",
        )
        assert result == "Recovered answer"

    asyncio.run(scenario())


def test_explicit_provider_chain_tries_requested_provider_first_then_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ai_service_module,
        "_provider_chain_for_use_case",
        lambda use_case=None: ["google", "groq", "openai"],
    )

    assert ai_service_module._provider_chain("openai", use_case="concept") == [
        "openai",
        "google",
        "groq",
        "anthropic",
        "deepseek",
        "ollama",
    ]


def test_complete_non_stream_recovers_from_partial_failure_when_provider_is_auto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def partial_failure(messages, model, temperature, max_tokens):
        yield "Half answer"
        raise RuntimeError("stream dropped")

    async def successful_provider(messages, model, temperature, max_tokens):
        yield "Recovered answer"

    monkeypatch.setattr(ai_service_module, "_provider_available", lambda provider: True)
    monkeypatch.setattr(ai_service_module, "_provider_chain", lambda provider=None, use_case=None: ["openai", "google"])
    monkeypatch.setattr(ai_service_module, "_configured_provider_override", lambda: None)
    monkeypatch.setattr(ai_service_module, "_resolve_provider", lambda: "openai")
    monkeypatch.setattr(ai_service_module, "_model_for_provider", lambda current_provider, requested_provider, model: None)
    monkeypatch.setattr(
        ai_service_module,
        "_PROVIDER_STREAM_MAP",
        {"openai": partial_failure, "google": successful_provider},
    )

    async def scenario() -> None:
        result = await ai_service_module._complete_non_stream(
            [{"role": "user", "content": "What is a protocol?"}],
            provider=None,
            model="test-model",
        )
        assert result == "Recovered answer"

    asyncio.run(scenario())


def test_complete_non_stream_limits_automatic_provider_fallback_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_provider(messages, model, temperature, max_tokens):
        if False:
            yield ""
        raise RuntimeError("provider down")

    async def successful_provider(messages, model, temperature, max_tokens):
        yield "Recovered answer"

    monkeypatch.setattr(ai_service_module.settings, "AI_AUTO_MAX_PROVIDER_ATTEMPTS", 2)
    monkeypatch.setattr(ai_service_module, "_provider_available", lambda provider: True)
    monkeypatch.setattr(
        ai_service_module,
        "_provider_chain",
        lambda provider=None, use_case=None: ["openai", "google", "anthropic"],
    )
    monkeypatch.setattr(ai_service_module, "_configured_provider_override", lambda: None)
    monkeypatch.setattr(ai_service_module, "_resolve_provider", lambda: "openai")
    monkeypatch.setattr(
        ai_service_module,
        "_model_for_provider",
        lambda current_provider, requested_provider, model: None,
    )
    monkeypatch.setattr(
        ai_service_module,
        "_PROVIDER_STREAM_MAP",
        {
            "openai": failing_provider,
            "google": failing_provider,
            "anthropic": successful_provider,
        },
    )

    async def scenario() -> None:
        with pytest.raises(
            RuntimeError,
            match="openai: provider down; google: provider down",
        ):
            await ai_service_module._complete_non_stream(
                [{"role": "user", "content": "What is a protocol?"}],
                provider=None,
                model="test-model",
            )

    asyncio.run(scenario())


def test_default_auto_provider_attempt_limit_covers_full_fallback_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(ai_service_module.settings, "AI_AUTO_MAX_PROVIDER_ATTEMPTS", raising=False)

    assert ai_service_module._auto_provider_attempt_limit() == 6


def test_infer_use_case_prefers_writing_for_rewrite_requests() -> None:
    assert ai_service_module.infer_use_case("chat", "Rewrite this email to sound professional.") == "writing"


def test_infer_use_case_prefers_concept_for_explanations() -> None:
    assert ai_service_module.infer_use_case("chat", "Explain what recursion is in simple terms.") == "concept"


def test_concept_provider_chain_keeps_groq_in_default_attempt_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_service_module, "_configured_provider_override", lambda: None)
    monkeypatch.setattr(ai_service_module, "_resolve_provider", lambda: "openai")
    monkeypatch.setattr(ai_service_module.settings, "AI_AUTO_MAX_PROVIDER_ATTEMPTS", 2)

    chain = ai_service_module._provider_chain(None, use_case="concept")

    assert chain[:2] == ["openai", "groq"]


def test_infer_use_case_avoids_quick_for_multi_part_definition_question() -> None:
    assert (
        ai_service_module.infer_use_case("chat", "what is java and how can be classified?")
        == "concept"
    )


def test_provider_chain_uses_research_preferences_when_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_service_module, "_configured_provider_override", lambda: None)
    monkeypatch.setattr(ai_service_module, "_resolve_provider", lambda: "openai")

    chain = ai_service_module._provider_chain(None, use_case="research")

    assert chain[:4] == ["google", "openai", "anthropic", "deepseek"]


def test_resolve_provider_prefers_chatgpt_then_claude_before_other_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_service_module.settings, "AI_PROVIDER", "")
    monkeypatch.setattr(ai_service_module.settings, "GROQ_API_KEY", "groq-key")
    monkeypatch.setattr(ai_service_module.settings, "GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr(ai_service_module.settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(ai_service_module.settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(ai_service_module.settings, "ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setattr(ai_service_module.settings, "DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setattr(ai_service_module.settings, "OLLAMA_BASE_URL", "http://localhost:11434")

    assert ai_service_module._resolve_provider() == "openai"


def test_get_available_providers_matches_requested_priority_and_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_service_module.settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(ai_service_module.settings, "DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setattr(ai_service_module.settings, "GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr(ai_service_module.settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(ai_service_module.settings, "ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setattr(ai_service_module.settings, "GROQ_API_KEY", "groq-key")
    monkeypatch.setattr(ai_service_module.settings, "OLLAMA_BASE_URL", "http://localhost:11434")

    async def scenario() -> None:
        providers = await ai_service_module.ai_service.get_available_providers()

        assert [provider["id"] for provider in providers] == [
            "openai",
            "anthropic",
            "google",
            "deepseek",
            "groq",
            "ollama",
        ]
        assert providers[0]["name"] == "ChatGPT"
        assert providers[1]["name"] == "Claude"
        assert providers[2]["name"] == "Gemini"
        assert providers[3]["name"] == "DeepSeek"
        assert providers[0]["recommended_for"] == [
            "Reasoning",
            "Coding",
            "Writing",
            "Strategy",
        ]

    asyncio.run(scenario())


def test_provider_default_model_uses_code_model_for_openai_coding() -> None:
    assert (
        ai_service_module._provider_default_model("openai", "coding")
        == ai_service_module.settings.OPENAI_CODE_MODEL
    )


def test_provider_default_model_falls_back_to_gpt_4o_for_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_service_module.settings, "OPENAI_CHAT_MODEL", "")
    monkeypatch.setattr(ai_service_module.settings, "OPENAI_CODE_MODEL", "")
    monkeypatch.setattr(ai_service_module.settings, "OPENAI_EXPLAIN_MODEL", "")

    assert ai_service_module._provider_default_model("openai", "coding") == "gpt-4o"
    assert ai_service_module._provider_default_model("openai", "concept") == "gpt-4o"
    assert ai_service_module._provider_default_model("openai", "chat") == "gpt-4o"


def test_provider_default_model_uses_gemini_chat_model_for_google(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_service_module.settings, "GEMINI_CHAT_MODEL", "gemini-2.5-flash")

    assert ai_service_module._provider_default_model("google", "research") == "gemini-2.5-flash"


def test_provider_default_model_uses_configured_groq_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_service_module.settings, "GROQ_MODEL", "llama-3.1-8b-instant")

    assert ai_service_module._provider_default_model("groq") == "llama-3.1-8b-instant"


def test_streaming_error_body_can_be_read_without_response_not_read() -> None:
    class DummyResponse:
        status_code = 429

        async def aread(self):
            return b'{"error":{"message":"quota exceeded"}}'

    async def scenario() -> None:
        message = await ai_service_module._stream_error_message(DummyResponse(), "Groq")
        assert message == "Groq HTTP 429: quota exceeded"

    asyncio.run(scenario())


def test_provider_is_temporarily_disabled_after_quota_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    ai_service_module._PROVIDER_DISABLED_UNTIL.clear()
    monkeypatch.setattr(ai_service_module.time, "monotonic", lambda: 100.0)

    ai_service_module._temporarily_disable_provider(
        "openai",
        RuntimeError("insufficient_quota: exceeded your current quota"),
    )

    assert ai_service_module._provider_temporarily_disabled("openai") is True

    monkeypatch.setattr(ai_service_module.time, "monotonic", lambda: 1000.0)
    assert ai_service_module._provider_temporarily_disabled("openai") is False


def test_resolve_image_provider_defaults_to_google_first_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_service_module.settings, "AI_IMAGE_PROVIDER", "")
    monkeypatch.setattr(ai_service_module.settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(ai_service_module.settings, "GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr(ai_service_module.settings, "GEMINI_API_KEY", "")

    assert ai_service_module._resolve_image_provider() == "google"
