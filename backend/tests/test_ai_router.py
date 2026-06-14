from __future__ import annotations

import asyncio

from services import ai_router


def test_generate_answer_uses_instant_strategy(monkeypatch) -> None:
    captured = {}

    async def fake_fallback_fast(prompt: str) -> str:
        captured["prompt"] = prompt
        return "fast answer"

    monkeypatch.setattr(ai_router, "_fallback_fast", fake_fallback_fast)

    async def scenario() -> None:
        response = await ai_router.generate_answer("hi", [])
        assert response == "fast answer"
        assert "User question:\nhi" in captured["prompt"]

    asyncio.run(scenario())


def test_generate_answer_uses_race_strategy(monkeypatch) -> None:
    captured = {}

    async def fake_race_short(prompt: str) -> str:
        captured["prompt"] = prompt
        return "race answer"

    monkeypatch.setattr(ai_router, "_race_short", fake_race_short)

    async def scenario() -> None:
        response = await ai_router.generate_answer("tell me a joke", [])
        assert response == "race answer"
        assert "tell me a joke" in captured["prompt"]

    asyncio.run(scenario())


def test_generate_answer_uses_groq_strategy(monkeypatch) -> None:
    captured = {}

    async def fake_ask_groq(prompt: str, system_prompt: str, model: str) -> str:
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        captured["model"] = model
        return "groq answer"

    monkeypatch.setattr(ai_router.settings, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ai_router, "ask_groq", fake_ask_groq)

    async def scenario() -> None:
        response = await ai_router.generate_answer(
            "please explain routers clearly",
            [],
        )
        assert response == "groq answer"
        assert "please explain routers clearly" in captured["prompt"]
        assert captured["system_prompt"] == ai_router.SYSTEM_PROMPT
        assert captured["model"] == "llama-3.3-70b-versatile"

    asyncio.run(scenario())


def test_generate_answer_merges_claude_and_deepseek_strategy(monkeypatch) -> None:
    async def fake_ask_claude(prompt: str, system_prompt: str, model: str) -> str:
        return "Claude answer"

    async def fake_ask_deepseek(prompt: str, system_prompt: str, model: str) -> str:
        return "DeepSeek answer"

    monkeypatch.setattr(ai_router.settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(ai_router.settings, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(ai_router, "ask_claude", fake_ask_claude)
    monkeypatch.setattr(ai_router, "ask_deepseek", fake_ask_deepseek)

    async def scenario() -> None:
        response = await ai_router.generate_answer(
                (
                    "please explain how distributed systems coordinate consistency across replicas "
                    "when network partitions occur and clients continue sending writes "
                    "during failover recovery across multiple database regions"
                ),
            [],
        )
        assert response == "Claude answer\n\nDeepSeek answer"

    asyncio.run(scenario())
