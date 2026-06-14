import asyncio
import logging
import os
from typing import List

from config.settings import settings
from prompts import get_mode_prompt

from services.provider_clients import (
    ask_chatgpt,
    ask_claude,
    ask_deepseek,
    ask_gemini,
    ask_groq,
    ask_ollama,
    ask_perplexity,
)

FAST_TIMEOUT_SECONDS = 1.2
MODEL_TIMEOUT_SECONDS = 8.0

SYSTEM_PROMPT = (
    f"{get_mode_prompt('chat')}\n\n"
    "Additional router rules:\n"
    "- Do not mention model names.\n"
    "- Do not mention response times."
)

logger = logging.getLogger(__name__)


def select_model(message: str) -> str:
    word_count = len((message or "").split())

    if word_count < 4:
        return "instant"
    if word_count < 10:
        return "race"
    if word_count < 20:
        return "groq"
    return "claude_deepseek"


def is_follow_up(message: str) -> bool:
    text = (message or "").lower()
    followup_tokens = ["he", "she", "it", "they", "his", "her", "their", "this", "that", "those", "these"]
    return any(token in text.split() for token in followup_tokens)


def format_history(history: List[dict], limit: int = 12) -> str:
    clipped = history[-limit:] if limit else history
    lines = []
    for item in clipped:
        role = item.get("role", "user").capitalize()
        content = item.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _strip_tool_prefix(message: str) -> str:
    lines = [line.strip() for line in (message or "").splitlines() if line.strip()]
    cleaned = []
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            continue
        cleaned.append(line)
    return " ".join(cleaned).strip()


def _formatting_instructions(message: str) -> str:
    text = _strip_tool_prefix(message).lower()
    instructions = []

    diff_keywords = [
        "difference",
        "differences",
        "compare",
        "comparison",
        "vs ",
        "versus",
        "contrast",
    ]
    bullet_keywords = [
        "point by point",
        "point-by-point",
        "bullet",
        "bullets",
        "list the",
        "list ",
        "steps",
        "points",
    ]
    long_keywords = [
        "detail explanation",
        "detailed explanation",
        "explain in detail",
        "elaborate",
        "in depth",
        "in-depth",
        "comprehensive",
        "full explanation",
        "2-3 pages",
        "two to three pages",
        "long answer",
        "long response",
    ]

    if any(k in text for k in diff_keywords):
        instructions.append(
            "Use a clean Markdown table with a concise header row and consistent capitalization."
        )
        instructions.append("Avoid excessive bolding inside table cells; keep it professional.")
        instructions.append("Add a 1-2 sentence summary after the table.")

    if any(k in text for k in bullet_keywords):
        instructions.append("Use bullet points for the main points.")

    if any(k in text for k in long_keywords):
        instructions.append("Provide a long, detailed response (roughly 1200-1800 words).")

    return "\n".join(f"- {line}" for line in instructions if line)


def build_prompt(history: List[dict], message: str) -> str:
    history_text = format_history(history)
    prompt = (
        f"Conversation history:\n{history_text}\n\n"
        f"User question:\n{message}\n\n"
        "Answer clearly using the conversation context."
    )
    if is_follow_up(message):
        prompt += "\n\nThis appears to be a follow-up. Resolve references using the conversation history."
    formatting = _formatting_instructions(message)
    if formatting:
        prompt += f"\n\nFormatting requirements:\n{formatting}"
    return prompt


def _has_key(name: str) -> bool:
    if name == "gemini":
        return bool(getattr(settings, "GOOGLE_API_KEY", "") or getattr(settings, "GEMINI_API_KEY", ""))
    if name == "claude":
        return bool(getattr(settings, "ANTHROPIC_API_KEY", ""))
    if name == "chatgpt":
        return bool(getattr(settings, "OPENAI_API_KEY", ""))
    if name == "deepseek":
        return bool(getattr(settings, "DEEPSEEK_API_KEY", ""))
    if name == "groq":
        return bool(getattr(settings, "GROQ_API_KEY", ""))
    if name == "perplexity":
        return bool(os.getenv("PERPLEXITY_API_KEY") or getattr(settings, "PERPLEXITY_API_KEY", ""))
    if name == "ollama":
        return True
    return False


def _available(providers: List[str]) -> List[str]:
    return [name for name in providers if _has_key(name)]


async def _call_with_timeout(coro, timeout: float = MODEL_TIMEOUT_SECONDS):
    return await asyncio.wait_for(coro, timeout=timeout)


async def _fallback_fast(prompt: str) -> str:
    fallback_chain = _available(["gemini", "groq", "chatgpt", "deepseek", "claude", "perplexity", "ollama"])
    if not fallback_chain:
        return "NOVA AI is ready, but no AI provider is configured yet."

    for provider in fallback_chain:
        try:
            if provider == "gemini":
                return await _call_with_timeout(
                    ask_gemini(prompt, SYSTEM_PROMPT, "gemini-1.5-flash"),
                    timeout=MODEL_TIMEOUT_SECONDS,
                )
            if provider == "groq":
                return await _call_with_timeout(
                    ask_groq(prompt, SYSTEM_PROMPT, "llama-3.3-70b-versatile"),
                    timeout=MODEL_TIMEOUT_SECONDS,
                )
            if provider == "chatgpt":
                return await _call_with_timeout(
                    ask_chatgpt(prompt, SYSTEM_PROMPT, "gpt-4o-mini"),
                    timeout=MODEL_TIMEOUT_SECONDS,
                )
            if provider == "deepseek":
                return await _call_with_timeout(
                    ask_deepseek(prompt, SYSTEM_PROMPT, "deepseek-chat"),
                    timeout=MODEL_TIMEOUT_SECONDS,
                )
            if provider == "claude":
                return await _call_with_timeout(
                    ask_claude(prompt, SYSTEM_PROMPT, "claude-sonnet-4-5"),
                    timeout=MODEL_TIMEOUT_SECONDS,
                )
            if provider == "perplexity":
                return await _call_with_timeout(
                    ask_perplexity(prompt, SYSTEM_PROMPT, "sonar-pro"),
                    timeout=MODEL_TIMEOUT_SECONDS,
                )
            if provider == "ollama":
                return await _call_with_timeout(
                    ask_ollama(prompt, SYSTEM_PROMPT, "llama3"),
                    timeout=MODEL_TIMEOUT_SECONDS,
                )
        except Exception:
            continue

    return "NOVA AI is ready, but no AI provider responded in time."


async def _race_short(prompt: str) -> str:
    candidates = _available(["gemini", "claude", "perplexity"])
    if not candidates:
        return await _fallback_fast(prompt)

    task_map = []
    for name in candidates:
        if name == "gemini":
            task_map.append(asyncio.create_task(ask_gemini(prompt, SYSTEM_PROMPT, "gemini-1.5-flash")))
        if name == "claude":
            task_map.append(asyncio.create_task(ask_claude(prompt, SYSTEM_PROMPT, "claude-sonnet-4-5")))
        if name == "perplexity":
            task_map.append(asyncio.create_task(ask_perplexity(prompt, SYSTEM_PROMPT, "sonar-pro")))

    done, pending = await asyncio.wait(task_map, timeout=FAST_TIMEOUT_SECONDS, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()

    for task in done:
        if task.cancelled():
            continue
        if task.exception():
            continue
        result = (task.result() or "").strip()
        if result:
            return result

    return await _fallback_fast(prompt)


def _merge_answers(primary: str, secondary: str) -> str:
    if not primary:
        return secondary
    if not secondary:
        return primary
    if primary in secondary:
        return secondary
    if secondary in primary:
        return primary
    return f"{primary}\n\n{secondary}"


async def generate_answer(message: str, history: List[dict]) -> str:
    prompt = build_prompt(history or [], message)
    strategy = select_model(message)
    logger.info(
        "ai_router.generate_answer strategy=%s history_count=%s message=%s",
        strategy,
        len(history or []),
        " ".join((message or "").split())[:200],
    )

    if strategy == "instant":
        response_text = await _fallback_fast(prompt)
    elif strategy == "race":
        response_text = await _race_short(prompt)
    elif strategy == "groq":
        if not _has_key("groq"):
            response_text = await _fallback_fast(prompt)
        else:
            try:
                response_text = await _call_with_timeout(
                    ask_groq(prompt, SYSTEM_PROMPT, "llama-3.3-70b-versatile"),
                    timeout=MODEL_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                logger.warning("ai_router_groq_failed error=%s", exc)
                response_text = await _fallback_fast(prompt)
    else:
        responses = []
        if _has_key("claude"):
            responses.append(
                _call_with_timeout(
                    ask_claude(prompt, SYSTEM_PROMPT, "claude-sonnet-4-5"),
                    timeout=MODEL_TIMEOUT_SECONDS,
                )
            )
        if _has_key("deepseek"):
            responses.append(
                _call_with_timeout(
                    ask_deepseek(prompt, SYSTEM_PROMPT, "deepseek-chat"),
                    timeout=MODEL_TIMEOUT_SECONDS,
                )
            )

        if not responses:
            response_text = await _fallback_fast(prompt)
        else:
            results = await asyncio.gather(*responses, return_exceptions=True)
            clean_results = [
                str(result).strip()
                for result in results
                if not isinstance(result, Exception) and str(result).strip()
            ]
            response_text = ""
            for result in clean_results:
                response_text = _merge_answers(response_text, result)
            if not response_text:
                response_text = await _fallback_fast(prompt)

    response_text = response_text.strip()
    if response_text:
        return response_text

    return "I don't know based on the information I have."
