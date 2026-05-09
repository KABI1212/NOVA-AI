from utils.format_ai_response import format_ai_response


def test_format_ai_response_keeps_short_natural_text() -> None:
    text = "AI can help users answer questions. It can summarize files. It also writes code."

    assert format_ai_response(text) == text


def test_format_ai_response_softly_marks_long_plain_lines() -> None:
    text = (
        "Artificial intelligence helps teams process large amounts of information, "
        "reduce repetitive work, improve decision-making, and respond faster to "
        "customer needs without forcing every task to be handled manually."
    )

    assert format_ai_response(text) == f"🔹 {text}"


def test_format_ai_response_detects_short_heading_lines() -> None:
    assert format_ai_response("Automation and Efficiency") == "## Automation and Efficiency"


def test_format_ai_response_skips_code_blocks() -> None:
    text = "Use this:\n\n```python\nprint('hello')\n```"

    assert format_ai_response(text) == text


def test_format_ai_response_preserves_existing_markdown_lists() -> None:
    text = "## Features\n\n- Fast responses\n- File upload"

    assert format_ai_response(text) == text
