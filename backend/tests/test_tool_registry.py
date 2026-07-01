from __future__ import annotations

import asyncio

import pytest

import services.tool_registry as registry
from services.tool_registry import ToolDefinition, list_tools, run_tool


def test_list_tools_exposes_public_schemas() -> None:
    tools = list_tools()

    assert {tool["id"] for tool in tools} >= {"multi_ai_compose", "live_research_agent"}
    compose = next(tool for tool in tools if tool["id"] == "multi_ai_compose")
    assert compose["input_schema"]["required"] == ["question"]
    assert "runner" not in compose


def test_run_tool_validates_required_question(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_runner(payload):
        raise AssertionError("runner should not run for invalid input")

    monkeypatch.setitem(
        registry._TOOLS,
        "test_tool",
        ToolDefinition(
            id="test_tool",
            name="Test Tool",
            description="A test tool.",
            category="test",
            input_schema=registry.QUESTION_INPUT_SCHEMA,
            runner=fake_runner,
        ),
    )

    async def scenario() -> None:
        with pytest.raises(ValueError, match="question is required"):
            await run_tool("test_tool", {})

    asyncio.run(scenario())


def test_run_tool_rejects_unknown_input_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_runner(payload):
        raise AssertionError("runner should not run for invalid input")

    monkeypatch.setitem(
        registry._TOOLS,
        "strict_tool",
        ToolDefinition(
            id="strict_tool",
            name="Strict Tool",
            description="A strict test tool.",
            category="test",
            input_schema=registry.QUESTION_INPUT_SCHEMA,
            runner=fake_runner,
        ),
    )

    async def scenario() -> None:
        with pytest.raises(ValueError, match="Unknown input field"):
            await run_tool("strict_tool", {"question": "hello", "extra": True})

    asyncio.run(scenario())


def test_run_tool_returns_result_with_tool_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_runner(payload):
        return {"answer": f"Echo: {payload['question']}"}

    monkeypatch.setitem(
        registry._TOOLS,
        "echo_tool",
        ToolDefinition(
            id="echo_tool",
            name="Echo Tool",
            description="Echoes input.",
            category="test",
            input_schema=registry.QUESTION_INPUT_SCHEMA,
            runner=fake_runner,
        ),
    )

    async def scenario() -> None:
        payload = await run_tool("echo_tool", {"question": "  hello   world  "})
        assert payload["answer"] == "Echo: hello   world"
        assert payload["tool"]["id"] == "echo_tool"

    asyncio.run(scenario())
