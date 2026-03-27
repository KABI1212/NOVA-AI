from __future__ import annotations

import asyncio
import importlib

import pytest

ai_service_module = importlib.import_module("services.ai_service")


def test_complete_non_stream_rejects_partial_provider_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def partial_failure(messages, model, temperature, max_tokens):
        yield "Half answer"
        raise RuntimeError("stream dropped")

    monkeypatch.setattr(ai_service_module, "_provider_ready", lambda provider: True)
    monkeypatch.setattr(ai_service_module, "_PROVIDER_STREAM_MAP", {"openai": partial_failure})

    async def scenario() -> None:
        with pytest.raises(RuntimeError, match="partial response"):
            await ai_service_module._complete_non_stream(
                [{"role": "user", "content": "Answer all questions from this paper."}],
                provider="openai",
                model="test-model",
            )

    asyncio.run(scenario())
