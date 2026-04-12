import asyncio

import routes.chat as chat_module
from services import search_service


def test_should_use_search_only_for_temporal_or_volatile_queries() -> None:
    assert chat_module._should_use_search("What is recursion?") is False
    assert chat_module._should_use_search("What is the latest AI news today?") is True
    assert chat_module._should_use_search("Bitcoin price in USD") is True


def test_dedupe_image_assets_ignores_invalid_non_image_strings() -> None:
    images = chat_module._dedupe_image_assets(
        [
            "https://example.com/diagram.png",
            "services.ai_service provider=google model=gemini",
            "%5Bservices.ai_service%5D+provider%3Dgoogle",
            "data:image/png;base64,abc123abc123abc123abc123abc123abc123abc123abc123abc123abc123abc123",
            "https://example.com/diagram.png",
        ]
    )

    assert images == [
        "https://example.com/diagram.png",
        "data:image/png;base64,abc123abc123abc123abc123abc123abc123abc123abc123abc123abc123abc123",
    ]


def test_is_temporal_query_avoids_static_captain_false_positive() -> None:
    assert search_service.is_temporal_query("Who is Captain America?") is False
    assert search_service.is_temporal_query("Who is the captain of India cricket team?") is True


def test_maybe_enhance_temporal_message_skips_page_fetch_without_force_search(
    monkeypatch,
) -> None:
    async def fake_search_web(query: str, max_results: int = 5):
        return [
            {
                "title": "BTC price today",
                "url": "https://example.com/btc",
                "snippet": "BTC trades near 65000 USD.",
                "date": "2026-03-27",
                "source": "Example",
            }
        ]

    async def forbidden_fetch(url: str, max_chars: int = 3000):
        raise AssertionError("page fetch should not run when search is not forced")

    monkeypatch.setattr(chat_module, "search_web", fake_search_web)
    monkeypatch.setattr(chat_module, "fetch_page_content", forbidden_fetch)

    async def scenario() -> None:
        enhanced = await chat_module._maybe_enhance_temporal_message("bitcoin price")
        assert "SEARCH RESULTS:" in enhanced
        assert "User Question: bitcoin price" in enhanced

    asyncio.run(scenario())


def test_maybe_enhance_temporal_message_with_sources_returns_visible_sources(
    monkeypatch,
) -> None:
    async def fake_search_web(query: str, max_results: int = 5):
        return [
            {
                "title": "Latest BTC price",
                "url": "https://example.com/btc",
                "snippet": "BTC moves above 65000 USD.",
                "date": "2026-03-27",
                "source": "Example Finance",
            }
        ]

    monkeypatch.setattr(chat_module, "search_web", fake_search_web)

    async def scenario() -> None:
        enhanced, sources = await chat_module._maybe_enhance_temporal_message_with_sources("bitcoin price")
        assert "SEARCH RESULTS:" in enhanced
        assert sources == [
            {
                "title": "Latest BTC price",
                "url": "https://example.com/btc",
                "source": "Example Finance",
                "date": "2026-03-27",
                "snippet": "BTC moves above 65000 USD.",
            }
        ]

    asyncio.run(scenario())


def test_cross_check_answer_if_needed_returns_original_when_no_search_context(
    monkeypatch,
) -> None:
    async def forbidden_collect(*args, **kwargs):
        raise AssertionError("cross-check should not run when source material matches the user message")

    monkeypatch.setattr(chat_module, "_collect_ai_response", forbidden_collect)

    async def scenario() -> None:
        draft = "Recursion is when a function calls itself."
        result = await chat_module._cross_check_answer_if_needed(
            "What is recursion?",
            "What is recursion?",
            draft,
            provider=None,
            model=None,
            max_tokens=1200,
        )
        assert result == draft

    asyncio.run(scenario())


def test_cross_check_answer_if_needed_revises_search_backed_answers(
    monkeypatch,
) -> None:
    captured = {}

    async def fake_collect(ai_messages, provider, model, temperature=None, max_tokens=None, use_case=None):
        captured["messages"] = ai_messages
        captured["provider"] = provider
        captured["model"] = model
        captured["temperature"] = temperature
        captured["max_tokens"] = max_tokens
        captured["use_case"] = use_case
        return "Verified answer"

    monkeypatch.setattr(chat_module, "_collect_ai_response", fake_collect)

    async def scenario() -> None:
        result = await chat_module._cross_check_answer_if_needed(
            "Who won the IPL 2025 final?",
            "Today's date is March 27, 2026.\nSEARCH RESULTS:\n[1] IPL result",
            "Draft answer",
            provider="openai",
            model="gpt-4o-mini",
            max_tokens=1600,
        )
        assert result == "Verified answer"
        assert captured["provider"] == "openai"
        assert captured["model"] == "gpt-4o-mini"
        assert captured["temperature"] == 0.0
        assert captured["max_tokens"] == 1024
        assert captured["use_case"] == "research"
        assert captured["messages"][0]["role"] == "system"

    asyncio.run(scenario())


def test_build_ai_messages_uses_raw_prompt_for_instruction_detection() -> None:
    messages = chat_module._build_ai_messages(
        history=[],
        user_message=(
            "Today's date is April 04, 2026.\n\n"
            "SEARCH RESULTS:\n"
            "- difference between Java and C++\n"
            "- Java is simple for beginners\n"
            "User Question: what is java? advantage of java/"
        ),
        mode="chat",
        instruction_message="what is java? advantage of java/",
    )

    system_messages = [message["content"] for message in messages if message.get("role") == "system"]

    assert not any("This is a comparison question." in content for content in system_messages)
    assert not any("The user explicitly wants a short/simple answer." in content for content in system_messages)


def test_build_ai_messages_adds_document_grounding_instruction_when_context_exists() -> None:
    messages = chat_module._build_ai_messages(
        history=[],
        user_message="What is the launch date?",
        mode="documents",
        doc_context="Launch date: April 5, 2026.",
    )

    system_messages = [message["content"] for message in messages if message.get("role") == "system"]

    assert any("Document verification mode:" in content for content in system_messages)
    assert any("Document context:" in content for content in system_messages)


def test_build_cross_check_messages_preserves_markdown_structure_guidance() -> None:
    messages = chat_module._build_cross_check_messages(
        "Explain zero trust architecture.",
        "Fresh source material",
        "## **Overview**\n\n- Verify every request.",
    )

    assert messages[0]["role"] == "system"
    assert "Preserve the user's language, the draft's useful level of detail" in messages[0]["content"]
    assert "Do not flatten a structured draft into one dense paragraph." in messages[0]["content"]
    assert "Make heading and subheading text bold" in messages[0]["content"]


def test_looks_like_stale_cutoff_answer_detects_cutoff_language() -> None:
    assert (
        chat_module._looks_like_stale_cutoff_answer(
            "My knowledge cutoff is in 2023, so I may miss newer updates."
        )
        is True
    )
    assert chat_module._looks_like_stale_cutoff_answer("The 2023 season was exciting.") is False


def test_best_effort_answer_retries_with_fresh_sources_when_draft_is_stale(
    monkeypatch,
) -> None:
    async def fake_enhance_with_sources(message: str, force_search: bool = False):
        return (f"SEARCHED::{message}", [{"title": "IPL 2024", "url": "https://example.com/ipl"}]) if force_search else (message, [])

    async def fake_collect(ai_messages, provider, model, temperature=None, max_tokens=None, use_case=None):
        last_message = ai_messages[-1]["content"]
        if str(last_message).startswith("SEARCHED::"):
            return "Kolkata Knight Riders won the 2024 IPL title."
        return "My knowledge cutoff is 2023, so I cannot confirm newer winners."

    async def passthrough_cross_check(
        user_message,
        source_material,
        draft_answer,
        provider,
        model,
        max_tokens=None,
        compatible_provider=None,
    ):
        return draft_answer

    async def fake_search_backup_bundle(message: str, force_search: bool = False):
        raise AssertionError("search backup should not run when freshness retry succeeds")

    monkeypatch.setattr(chat_module, "_maybe_enhance_temporal_message_with_sources", fake_enhance_with_sources)
    monkeypatch.setattr(chat_module, "_collect_ai_response", fake_collect)
    monkeypatch.setattr(chat_module, "_cross_check_answer_if_needed", passthrough_cross_check)
    monkeypatch.setattr(chat_module, "_search_backup_answer_bundle", fake_search_backup_bundle)

    async def scenario() -> None:
        result = await chat_module._best_effort_answer(
            history=[],
            user_message="Who won IPL 2024?",
            mode="chat",
            provider=None,
            model=None,
            max_tokens=900,
        )
        assert result == "Kolkata Knight Riders won the 2024 IPL title."

    asyncio.run(scenario())


def test_best_effort_answer_bundle_document_mode_uses_document_fallback_without_web_search(
    monkeypatch,
) -> None:
    async def failing_collect(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    async def forbidden_search_backup_bundle(message: str, force_search: bool = False):
        raise AssertionError("document mode should not fall back to web search")

    monkeypatch.setattr(chat_module, "_collect_ai_response", failing_collect)
    monkeypatch.setattr(chat_module, "_search_backup_answer_bundle", forbidden_search_backup_bundle)

    async def scenario() -> None:
        answer, sources, answer_source = await chat_module._best_effort_answer_bundle(
            history=[],
            user_message="What is the launch date?",
            mode="documents",
            provider=None,
            model=None,
            doc_context="Launch date: April 5, 2026.\n\nVenue: Chennai.",
            max_tokens=900,
        )

        assert "april 5, 2026" in answer.lower()
        assert sources
        assert answer_source == "document"
        assert sources[0]["kind"] == "document"
        assert "April 5, 2026" in sources[0]["excerpt"]

    asyncio.run(scenario())


def test_best_effort_answer_bundle_forces_search_backup_for_non_temporal_prompt_when_ai_fails(
    monkeypatch,
) -> None:
    async def failing_collect(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    async def passthrough_cross_check(
        user_message,
        source_material,
        draft_answer,
        provider,
        model,
        max_tokens=None,
        compatible_provider=None,
    ):
        return draft_answer

    call_sequence = []

    async def fake_search_backup_bundle(message: str, force_search: bool = False):
        call_sequence.append(force_search)
        if force_search:
            return (
                "Best current answer I could verify from fresh web results:\nDigital marketing is...",
                [
                    {
                        "title": "Digital marketing guide",
                        "url": "https://example.com/marketing",
                    }
                ],
            )
        return None, []

    monkeypatch.setattr(
        chat_module,
        "_maybe_enhance_temporal_message_with_sources",
        lambda message, force_search=False: asyncio.sleep(0, result=(message, [])),
    )
    monkeypatch.setattr(chat_module, "_collect_ai_response", failing_collect)
    monkeypatch.setattr(chat_module, "_cross_check_answer_if_needed", passthrough_cross_check)
    monkeypatch.setattr(chat_module, "_search_backup_answer_bundle", fake_search_backup_bundle)

    async def scenario() -> None:
        answer, sources, answer_source = await chat_module._best_effort_answer_bundle(
            history=[],
            user_message="explain digital marketing in simple terms",
            mode="chat",
            provider=None,
            model=None,
            max_tokens=1200,
        )

        assert "digital marketing" in answer.lower()
        assert sources
        assert answer_source == "web"
        assert call_sequence == [False, True]

    asyncio.run(scenario())


def test_best_effort_answer_bundle_keeps_temporal_chat_provider_first_by_default(
    monkeypatch,
) -> None:
    monkeypatch.setattr(chat_module.settings, "CHAT_AUTO_WEB_SEARCH_IN_CHAT", False)

    async def forbidden_enhance(message: str, force_search: bool = False):
        raise AssertionError("normal chat should not auto-search before the provider answers")

    async def fake_collect(ai_messages, provider, model, temperature=None, max_tokens=None, use_case=None):
        return "Provider-first answer"

    async def passthrough_cross_check(
        user_message,
        source_material,
        draft_answer,
        provider,
        model,
        max_tokens=None,
        compatible_provider=None,
    ):
        return draft_answer

    monkeypatch.setattr(chat_module, "_maybe_enhance_temporal_message_with_sources", forbidden_enhance)
    monkeypatch.setattr(chat_module, "_collect_ai_response", fake_collect)
    monkeypatch.setattr(chat_module, "_cross_check_answer_if_needed", passthrough_cross_check)

    async def scenario() -> None:
        answer, sources, answer_source = await chat_module._best_effort_answer_bundle(
            history=[],
            user_message="What is the latest AI news?",
            mode="chat",
            provider=None,
            model=None,
            max_tokens=1200,
        )

        assert answer == "Provider-first answer"
        assert sources == []
        assert answer_source == "ai"

    asyncio.run(scenario())
