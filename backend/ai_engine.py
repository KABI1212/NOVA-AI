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
_FULL_POWER_PATTERN = re.compile(r"\buse full power\b", re.IGNORECASE)
_STRICT_EXAM_PATTERN = re.compile(
    r"\b(exam-ready|exam ready|exam format|for exam|for exams|easy to write in exams|strict academic tone|internal verification|definition.*explanation.*key points.*conclusion)\b",
    re.IGNORECASE,
)
_MULTI_QUESTION_REQUEST_PATTERN = re.compile(
    r"\b(?:answer|solve|write|give|provide|return|generate)\s+(?:all|every)\s+(?:the\s+)?(?:questions?|answers?)\b"
    r"|\ball questions?\b"
    r"|\ball question answers?\b"
    r"|\bquestion paper\b"
    r"|\bsub-?questions?\b",
    re.IGNORECASE,
)
_QUESTION_ITEM_PATTERN = re.compile(
    r"(?m)^\s*(?:q(?:uestion)?\s*)?(?:\d+|[ivxlcdm]+|[a-z])[\).:-]\s+",
    re.IGNORECASE,
)
_DIAGRAM_REQUEST_PATTERN = re.compile(
    r"\b(diagram|flow\s?chart|flowchart|block diagram|architecture diagram|network diagram|sequence diagram|topology|stack diagram|layered diagram|with diagram|draw .*diagram|neat diagram)\b",
    re.IGNORECASE,
)
_ASSIGNMENT_PATTERN = re.compile(r"\b(?:assignment|assignments)\b", re.IGNORECASE)
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
            "This is a very short exam-style answer. Keep it simple and direct: "
            "1 to 2 short lines or 2 very short points, roughly 20 to 40 words. "
            "State the main idea clearly and add only one small supporting detail when helpful."
        )
    if marks <= 5:
        return (
            "This is a short-to-medium exam answer. Give a compact definition or introduction "
            "followed by 3 to 5 key points, roughly 80 to 180 words."
        )
    if marks == 8:
        return (
            "This is a medium-to-long exam answer. Give a full, developed response with a short introduction, "
            "well-explained points or short subsections, and a brief conclusion. Target about 1500 words."
        )
    if marks == 10:
        return (
            "This is a long exam answer. Give a well-structured response with introduction, deeper explanation, "
            "clear subsections, and a brief conclusion. Target about 2000 words."
        )
    if marks <= 12:
        return (
            "This is a long exam answer. Give a well-structured response with introduction, key explanation, "
            "important points, and a brief conclusion. Target about 2400 words."
        )
    if marks <= 16:
        return (
            "This is a very detailed long answer. Give a strong introduction, deeper explanation with clear "
            "subsections, key points, and a short conclusion. Target about 3000 words."
        )
    return (
        "This is an extended academic answer. Give a complete, well-structured response with strong explanation, "
        "organized sections, and enough depth to feel comprehensive."
    )


def _looks_like_multi_question_request(message: str) -> bool:
    text = message or ""
    if not text.strip():
        return False

    if _MULTI_QUESTION_REQUEST_PATTERN.search(text):
        return True

    if len(_QUESTION_ITEM_PATTERN.findall(text)) >= 2:
        return True

    if len(list(_MARKS_PATTERN.finditer(text))) >= 2 and _EXAM_CONTEXT_PATTERN.search(text):
        return True

    return False


def _academic_answer_instruction(message: str) -> str | None:
    text = " ".join((message or "").split())
    if not text:
        return None

    simple_requested = bool(_SIMPLE_REQUEST_PATTERN.search(text))
    short_requested = bool(_SHORT_REQUEST_PATTERN.search(text))
    detailed_requested = bool(_DETAILED_REQUEST_PATTERN.search(text))
    assignment_requested = bool(_ASSIGNMENT_PATTERN.search(text))

    marks_matches = [int(match.group("marks")) for match in _MARKS_PATTERN.finditer(text)]
    if marks_matches:
        language_instruction = (
            "- Use simple, easy-to-understand language.\n"
            if simple_requested
            else ""
        )
        assignment_instruction = (
            "- Since this is for an assignment, make the explanation fuller, more polished, and more submission-ready than a quick exam note.\n"
            "- When helpful, use short headings, fuller paragraph development, and a brief concluding wrap-up.\n"
            if assignment_requested
            else ""
        )
        if _looks_like_multi_question_request(text) or len(set(marks_matches)) > 1 or len(marks_matches) > 1:
            return (
                "Answer in a student-friendly exam style.\n"
                "- This request includes multiple questions or mixed-mark questions.\n"
                "- Answer every question or sub-question in the order given.\n"
                "- Preserve numbering or section labels so each answer maps to the correct question.\n"
                "- Match each answer's depth to its own mark value instead of using one depth for the whole paper.\n"
                f"{assignment_instruction}"
                f"{language_instruction}"
                "- Do not skip later questions.\n"
                "- If any question text is missing or unclear, say which question is missing instead of silently omitting it.\n"
                "- Keep the answers clear, accurate, and easy to write in an exam or assignment."
            )

        marks = marks_matches[0]
        return (
            "Answer in a student-friendly exam style.\n"
            f"- Match the depth to this {marks}-mark question.\n"
            f"- {_marks_instruction(marks)}\n"
            f"{assignment_instruction}"
            f"{language_instruction}"
            "- Keep the answer clear, accurate, and easy to write in an exam or assignment.\n"
            "- Use enough detail to feel complete, especially for higher-mark or assignment-style questions.\n"
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
            assignment_detail_instruction = (
                "- Because this is for an assignment, add more depth, cleaner structure, and slightly fuller explanation than a short exam answer.\n"
                if assignment_requested
                else ""
            )
            return (
                "Answer in a detailed academic style suitable for an assignment or exam.\n"
                "- Use clear structure with introduction, explanation, and conclusion when helpful.\n"
                "- Keep the explanation complete but focused on the asked question.\n"
                f"{assignment_detail_instruction}"
            )
        assignment_full_instruction = (
            "- For assignments, make the answer fuller, more polished, and more submission-ready than a brief study note.\n"
            "- When helpful, use short headings, fuller paragraph development, and a brief conclusion so the answer feels complete.\n"
            if assignment_requested
            else ""
        )
        return (
            "Answer in a detailed academic style suitable for an assignment or exam.\n"
            "- By default, do not make it too short or overly simplified.\n"
            "- Give enough explanation, structure, and supporting points to feel complete.\n"
            f"{assignment_full_instruction}"
            "- Only switch to a short or simple answer if the user explicitly asks for that."
        )

    return None


def _diagram_answer_instruction(message: str) -> str | None:
    text = " ".join((message or "").split())
    if not text or not _DIAGRAM_REQUEST_PATTERN.search(text):
        return None

    return (
        "The user wants a clear diagram-style answer.\n"
        "- Do not draw rough ASCII art, text boxes, or fake diagrams inside code blocks unless the user explicitly asks for text-only formatting.\n"
        "- Do not make the entire answer only a separate rough diagram. Give the full answer in normal prose and let the visual support it.\n"
        "- Write a normal explanation in clean prose, and keep the diagram references aligned with that explanation.\n"
        "- If the topic is a process, use clear step labels or numbering in the explanation so the visual can match it.\n"
        "- If the topic is a layered architecture or stack, explain it in the same top-to-bottom order as the visual."
    )


def _multi_question_answer_instruction(message: str) -> str | None:
    text = " ".join((message or "").split())
    if not text or not _looks_like_multi_question_request(text):
        return None

    return (
        "This request involves multiple questions.\n"
        "- Answer all visible questions and sub-questions, not just the first few.\n"
        "- Keep the same order as the source question paper or prompt.\n"
        "- Use clear separators or headings so each answer is easy to match to its question.\n"
        "- If different questions have different marks, adjust the answer length for each one individually.\n"
        "- Do not stop after only a few answers when more questions are still visible.\n"
        "- Never silently stop early."
    )


def _comparison_answer_instruction(message: str) -> str | None:
    text = " ".join((message or "").split())
    if not text or not _COMPARISON_PATTERN.search(text):
        return None

    return (
        "This is a comparison question.\n"
        "- Do not answer in plain paragraphs only.\n"
        "- Use a clear Markdown table as the main structure.\n"
        "- Make the first column the comparison aspect or parameter.\n"
        "- Put each item being compared in its own separate column so the differences are easy to scan.\n"
        "- Cover the important differences with enough rows instead of only one or two surface points.\n"
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
            "- Add one short example or analogy only when it genuinely helps understanding."
        )

    return None


def _clarity_first_instruction(mode: str, message: str) -> str | None:
    text = " ".join((message or "").split())
    normalized_mode = (mode or "chat").lower()
    if not text or normalized_mode == "image":
        return None

    return (
        "The user wants clear, easy-to-understand answers.\n"
        "- Use simple, direct language.\n"
        "- Do not force fixed sections like Answer, Step by step, or Example.\n"
        "- Use numbered steps only for instructions, processes, or when the user explicitly asks.\n"
        "- Give an example only when it materially improves understanding or the user asks for one.\n"
        "- Keep the answer natural, compact, and free of extra filler."
    )


def _full_power_instruction(message: str) -> str | None:
    text = " ".join((message or "").split())
    if not text or not _FULL_POWER_PATTERN.search(text):
        return None

    return (
        "The user explicitly requested NOVA Special Mode.\n"
        "- Optimize for quality over speed.\n"
        "- Reason more deeply before answering.\n"
        "- Compare multiple valid approaches or viewpoints when useful.\n"
        "- Produce a more polished, complete, and expert-level final answer.\n"
        "- Keep the answer clear, decisive, and actionable."
    )


def contextual_system_instructions(mode: str, message: str) -> List[str]:
    instructions: List[str] = []

    clarity_instruction = _clarity_first_instruction(mode, message)
    if clarity_instruction:
        instructions.append(clarity_instruction)

    full_power_instruction = _full_power_instruction(message)
    if full_power_instruction:
        instructions.append(full_power_instruction)

    comparison_instruction = _comparison_answer_instruction(message)
    if comparison_instruction:
        instructions.append(comparison_instruction)

    diagram_instruction = _diagram_answer_instruction(message)
    if diagram_instruction:
        instructions.append(diagram_instruction)

    multi_question_instruction = _multi_question_answer_instruction(message)
    if multi_question_instruction:
        instructions.append(multi_question_instruction)

    academic_instruction = _academic_answer_instruction(message)
    if academic_instruction:
        instructions.append(academic_instruction)

    exam_ready_instruction = _exam_ready_instruction(message)
    if exam_ready_instruction:
        instructions.append(exam_ready_instruction)

    general_instruction = _general_response_instruction(message)
    if general_instruction:
        instructions.append(general_instruction)

    return instructions


def build_messages(
    history: List[Dict[str, str]],
    mode: str,
    instruction_message: str | None = None,
) -> List[Dict[str, str]]:
    """Inject system prompt for the selected mode."""
    system_prompt = get_mode_prompt(mode)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    latest_user_message = str(instruction_message or "").strip() or _latest_user_message(history)
    messages.extend(
        {"role": "system", "content": instruction}
        for instruction in contextual_system_instructions(mode, latest_user_message)
    )

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
