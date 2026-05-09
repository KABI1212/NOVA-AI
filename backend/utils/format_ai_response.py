import re


_CODE_FENCE = "```"
_HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+\S")
_LIST_PATTERN = re.compile(
    r"^\s*(?:[-*•]|\U0001F539|➜|✨|\U0001F4CC|\U0001F4A1)\s+"
)
_ORDERED_LIST_PATTERN = re.compile(r"^\s*\d+[\).]\s+")
_TABLE_PATTERN = re.compile(r"^\s*\|.*\|\s*$")


def _is_existing_markdown(line: str) -> bool:
    stripped = line.strip()
    return bool(
        _HEADING_PATTERN.match(stripped)
        or _LIST_PATTERN.match(stripped)
        or _ORDERED_LIST_PATTERN.match(stripped)
        or _TABLE_PATTERN.match(stripped)
        or stripped.startswith((">", "---", "***", "___", _CODE_FENCE))
    )


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    return len(stripped) < 50 and "." not in stripped and ":" not in stripped


def format_ai_response(text: str | None) -> str | None:
    if not text:
        return text

    normalized = str(text).replace("\r\n", "\n")
    if _CODE_FENCE in normalized:
        return text

    formatted: list[str] = []
    for line in normalized.split("\n"):
        stripped = line.strip()

        if not stripped:
            formatted.append("")
            continue

        if _is_existing_markdown(stripped):
            formatted.append(stripped)
            continue

        if _looks_like_heading(stripped):
            formatted.append(f"## {stripped}")
            continue

        if len(stripped) > 120 and "\U0001F539" not in stripped:
            formatted.append(f"\U0001F539 {stripped}")
            continue

        formatted.append(stripped)

    return "\n".join(formatted).strip()
