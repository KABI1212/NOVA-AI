import re
from typing import Dict, List

from config.settings import settings
from prompts import get_mode_prompt


_MARKS_PATTERN = re.compile(
    r"\b(?P<marks>2|3|4|5|8|10|12|15|16)\s*(?:-)?\s*(?:mark|marks)\b",
    re.IGNORECASE,
)
_EXAM_CONTEXT_PATTERN = re.compile(
    r"\b(assignment|assignments|exam|exams|test|tests|semester|internal|question paper|university exam)\b",
    re.IGNORECASE,
)
_COMPARISON_PATTERN = re.compile(
    r"\b(difference between|differences between|difference|compare|comparison|distinguish between|versus|vs\.?)\b",
    re.IGNORECASE,
)
_SHORT_REQUEST_PATTERN = re.compile(
    r"\b(short answer|brief answer|in short|short note|very short answer)\b",
    re.IGNORECASE,
)
_SIMPLE_REQUEST_PATTERN = re.compile(
    r"\b(simple|simply|simple words|simple language|easy to understand|for beginners)\b",
    re.IGNORECASE,
)
_DETAILED_REQUEST_PATTERN = re.compile(
    r"\b(detailed|detail|long answer|elaborate|essay|explain in detail|discussion)\b",
    re.IGNORECASE,
)
_EXPLANATION_PATTERN = re.compile(
    r"\b(explain|how|why|working|works|mechanism|process|flow|steps?|advantages?|disadvantages?|uses?|importance|role)\b",
    re.IGNORECASE,
)
_MINIMAL_REQUEST_PATTERN = re.compile(
    r"\b(minimal|minimally|brief|briefly|concise|short|in short|one line|few lines|summary)\b",
    re.IGNORECASE,
)
_STRICT_EXAM_PATTERN = re.compile(
    r"\b(exam-ready|exam ready|exam format|for exam|for exams|easy to write in exams|strict academic tone|internal verification|definition.*explanation.*key points.*conclusion)\b",
    re.IGNORECASE,
)
_TECHNICAL_FOUNDATIONS_PATTERN = re.compile(
    r"\b(network|networking|protocol|http|https|smtp|imap|pop3|tcp/ip|tcp|udp|tls|ssl|dns|client|server|database|api|system|systems|architecture|ram|rom|memory|cache|operating system|os|compiler|process)\b",
    re.IGNORECASE,
)


def select_model(mode: str) -> str:
    """Select model based on mode."""
    key = (mode or "chat").lower()
    if key == "code":
        return settings.OPENAI_CODE_MODEL
    if key in {"deep", "safe", "knowledge", "learning", "documents"}:
        return settings.OPENAI_EXPLAIN_MODEL
    return settings.OPENAI_CHAT_MODEL


def _latest_user_message(history: List[Dict[str, str]]) -> str:
    for item in reversed(history or []):
        if str(item.get("role", "")).strip().lower() == "user":
            return str(item.get("content", "") or "").strip()
    return ""


def _marks_instruction(marks: int) -> str:
    if marks <= 2:
        return (
            "This is a short exam-style answer. Keep it crisp and direct: "
            "2 to 3 sentences or 2 to 3 points, roughly 35 to 60 words."
        )
    if marks <= 5:
        return (
            "This is a short-to-medium exam answer. Give a compact definition or introduction "
            "followed by 3 to 5 key points, roughly 80 to 150 words."
        )
    if marks <= 8:
        return (
            "This is a medium exam answer. Give a short introduction and a clear structured explanation "
            "with headings or bullets, roughly 160 to 260 words."
        )
    return (
        "This is a long exam answer. Give a well-structured response with introduction, key explanation, "
        "important points, and a brief conclusion, roughly 300 to 500 words."
    )


def _academic_answer_instruction(message: str) -> str | None:
    text = " ".join((message or "").split())
    if not text:
        return None

    simple_requested = bool(_SIMPLE_REQUEST_PATTERN.search(text))
    short_requested = bool(_SHORT_REQUEST_PATTERN.search(text))
    detailed_requested = bool(_DETAILED_REQUEST_PATTERN.search(text))

    marks_match = _MARKS_PATTERN.search(text)
    if marks_match:
        marks = int(marks_match.group("marks"))
        language_instruction = (
            "- Use simple, easy-to-understand language.\n"
            if simple_requested
            else ""
        )
        return (
            "Answer in a student-friendly exam style.\n"
            f"- Match the depth to a {marks}-mark question.\n"
            f"- {_marks_instruction(marks)}\n"
            f"{language_instruction}"
            "- Keep the answer clear, accurate, and easy to write in an exam or assignment.\n"
            "- Do not add unnecessary filler."
        )

    if _EXAM_CONTEXT_PATTERN.search(text):
        if short_requested:
            return (
                "Answer in a short academic style suitable for an assignment or exam.\n"
                "- Keep it concise, direct, and easy to memorize.\n"
                "- Use a brief introduction followed by a few key points."
            )
        if simple_requested:
            return (
                "Answer in a simple academic style.\n"
                "- Use easy language and straightforward explanation.\n"
                "- Keep it clear and compact because the user explicitly asked for a simple answer."
            )
        if detailed_requested:
            return (
                "Answer in a detailed academic style suitable for an assignment or exam.\n"
                "- Use clear structure with introduction, explanation, and conclusion when helpful.\n"
                "- Keep the explanation complete but focused on the asked question."
            )
        return (
            "Answer in a detailed academic style suitable for an assignment or exam.\n"
            "- By default, do not make it too short or overly simplified.\n"
            "- Give enough explanation, structure, and supporting points to feel complete.\n"
            "- Only switch to a short or simple answer if the user explicitly asks for that."
        )

    return None


def _comparison_answer_instruction(message: str) -> str | None:
    text = " ".join((message or "").split())
    if not text or not _COMPARISON_PATTERN.search(text):
        return None

    return (
        "This is a comparison question.\n"
        "- Do not make the answer too brief or overly simple.\n"
        "- Use a clear Markdown table with meaningful comparison points.\n"
        "- After the table, add a short explanation or summary so the differences are easy to understand.\n"
        "- If helpful, include one concise example."
    )


def _exam_ready_instruction(message: str) -> str | None:
    text = " ".join((message or "").split())
    if not text:
        return None

    exam_like = bool(_STRICT_EXAM_PATTERN.search(text))
    technical = bool(_TECHNICAL_FOUNDATIONS_PATTERN.search(text))
    academic_context = bool(_EXAM_CONTEXT_PATTERN.search(text))
    if not exam_like and not (academic_context and technical):
        return None

    return (
        "This request needs a complete exam-ready response.\n"
        "- Use strict academic tone.\n"
        "- Before writing, internally verify that the explanation matches standard real-world CS, systems, or networking fundamentals when applicable.\n"
        "- Use this structure in order when relevant:\n"
        "  1. Definition\n"
        "  2. Explanation\n"
        "  3. Key Points / Features\n"
        "  4. Comparison Table (only if the question is a comparison)\n"
        "  5. Conclusion\n"
        "- Keep the definition short and precise.\n"
        "- In the explanation, describe the real working model, actual components, technical flow, and correct protocols only when they truly apply.\n"
        "- Do not force unrelated protocols, architecture terms, or extra examples.\n"
        "- Avoid storytelling, filler, and unnecessary side notes.\n"
        "- Make the answer easy to reproduce in exams."
    )


def _general_response_instruction(message: str) -> str | None:
    text = " ".join((message or "").split())
    if not text:
        return None

    simple_requested = bool(_SIMPLE_REQUEST_PATTERN.search(text) or _MINIMAL_REQUEST_PATTERN.search(text))
    short_requested = bool(_SHORT_REQUEST_PATTERN.search(text) or _MINIMAL_REQUEST_PATTERN.search(text))
    detailed_requested = bool(_DETAILED_REQUEST_PATTERN.search(text))
    explanation_requested = bool(_EXPLANATION_PATTERN.search(text))
    multi_topic = len(re.findall(r"\b(and|vs|versus)\b|,", text, re.IGNORECASE)) >= 1

    if simple_requested or short_requested:
        return (
            "The user explicitly wants a short/simple answer.\n"
            "- Keep it concise.\n"
            "- Use simple language.\n"
            "- Give only the core answer without extra expansion."
        )

    if detailed_requested:
        return (
            "The user explicitly wants more depth.\n"
            "- Give a fuller explanation.\n"
            "- Use clear structure with short sections or bullets.\n"
            "- Include enough detail to feel complete, not minimal."
        )

    if explanation_requested or multi_topic:
        return (
            "This is an explanation-oriented or multi-concept question.\n"
            "- Do not give a minimal answer.\n"
            "- Explain each important concept clearly.\n"
            "- If multiple concepts are involved, cover them separately and then connect them.\n"
            "- Add one simple example or analogy when it helps understanding."
        )

    return None


def build_messages(history: List[Dict[str, str]], mode: str) -> List[Dict[str, str]]:
    """Inject system prompt for the selected mode."""
    system_prompt = get_mode_prompt(mode)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    latest_user_message = _latest_user_message(history)

    comparison_instruction = _comparison_answer_instruction(latest_user_message)
    if comparison_instruction:
        messages.append({"role": "system", "content": comparison_instruction})

    academic_instruction = _academic_answer_instruction(latest_user_message)
    if academic_instruction:
        messages.append({"role": "system", "content": academic_instruction})

    exam_ready_instruction = _exam_ready_instruction(latest_user_message)
    if exam_ready_instruction:
        messages.append({"role": "system", "content": exam_ready_instruction})

    general_instruction = _general_response_instruction(latest_user_message)
    if general_instruction:
        messages.append({"role": "system", "content": general_instruction})

    return [*messages, *history]


def response_envelope(
    message: str,
    images: List[str] = None,
    code_blocks: List[str] = None,
    audio: str = None,
    references: List[str] = None,
) -> Dict:
    return {
        "message": message,
        "images": images or [],
        "code_blocks": code_blocks or [],
        "audio": audio,
        "references": references or [],
    }
