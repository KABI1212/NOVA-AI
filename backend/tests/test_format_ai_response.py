from utils.format_ai_response import format_ai_response


def test_format_ai_response_converts_plain_sentences_to_bullets() -> None:
    result = format_ai_response(
        "AI can help users answer questions. It can summarize files. It also writes code."
    )

    assert result == (
        "🔹 AI can help users answer questions.\n\n"
        "🔹 It can summarize files.\n\n"
        "🔹 It also writes code."
    )


def test_format_ai_response_skips_code_blocks() -> None:
    text = "Use this:\n\n```python\nprint('hello')\n```"

    assert format_ai_response(text) == text


def test_format_ai_response_preserves_existing_markdown_lists() -> None:
    text = "## Features\n\n- Fast responses\n- File upload"

    assert format_ai_response(text) == text
