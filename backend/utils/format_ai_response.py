import re


_CODE_FENCE_PATTERN = re.compile(r"```")
_HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+\S")
_LIST_PATTERN = re.compile(r"^\s*(?:[-*•]|🔹|➜|✨|📌|💡)\s+")
_ORDERED_LIST_PATTERN = re.compile(r"^\s*\d+[\).]\s+")
_TABLE_PATTERN = re.compile(r"^\s*\|.*\|\s*$")
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")


def _is_structured_block(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    return bool(
        _HEADING_PATTERN.match(stripped)
        or _LIST_PATTERN.match(stripped)
        or _ORDERED_LIST_PATTERN.match(stripped)
        or _TABLE_PATTERN.match(stripped)
        or stripped.startswith((">", "---", "***", "___"))
    )


def _looks_like_heading(text: str) -> bool:
    stripped = text.strip()
    return len(stripped) < 60 and "." not in stripped and "\n" not in stripped


def _format_plain_block(text: str) -> str:
    paragraph = " ".join(text.split()).strip()
    if not paragraph:
        return ""

    if _looks_like_heading(paragraph):
        return f"## {paragraph}"

    sentences = [
        sentence.strip()
        for sentence in _SENTENCE_SPLIT_PATTERN.split(paragraph)
        if sentence.strip()
    ]

    if len(sentences) > 1:
        return "\n\n".join(f"🔹 {sentence}" for sentence in sentences)

    return f"🔹 {paragraph}"


def format_ai_response(text: str | None) -> str | None:
    if not text:
        return text

    normalized = str(text).replace("\r\n", "\n").strip()
    if not normalized or _CODE_FENCE_PATTERN.search(normalized):
        return text

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", normalized)
        if paragraph.strip()
    ]
    if not paragraphs:
        return normalized

    formatted: list[str] = []
    for paragraph in paragraphs:
        if _is_structured_block(paragraph):
            formatted.append(paragraph)
        else:
            formatted.append(_format_plain_block(paragraph))

    return "\n\n".join(block for block in formatted if block).strip()
