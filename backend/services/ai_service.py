"""
ai_service.py - NOVA AI multi-provider chat service
Provides consistent message formatting, logging, low-temperature generation,
provider fallback, and safer empty-response handling.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import time
from urllib.parse import urlparse
from typing import Any, AsyncGenerator, Dict, List, Optional
from xml.sax.saxutils import escape

import httpx

from ai_engine import contextual_system_instructions
from config.settings import settings
from prompts import get_presentation_style_prompt


logger = logging.getLogger(__name__)

LOCAL_FALLBACK_MESSAGE = (
    "NOVA AI couldn't get a usable response from the configured AI providers right now. "
    "Please try again in a moment."
)

_OFFLINE_TEXT = (
    "NOVA AI is running in offline mode. "
    "Configure an AI provider (OPENAI_API_KEY / DEEPSEEK_API_KEY / "
    "GOOGLE_API_KEY / GROQ_API_KEY / ANTHROPIC_API_KEY) "
    "or point OLLAMA_BASE_URL at a reachable Ollama server."
)

_DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
_DEFAULT_GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
_DEFAULT_OPENROUTER_IMAGE_MODEL = "sourceful/riverflow-v2-fast-preview"
_OPENROUTER_IMAGE_FALLBACK_MODELS = [
    "sourceful/riverflow-v2-fast-preview",
    "sourceful/riverflow-v2-standard-preview",
    "google/gemini-2.5-flash-image",
]
_DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
_DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
_DEFAULT_OLLAMA_MODEL = "llama3"
_HOSTED_RUNTIME_ENV_VARS = (
    "RENDER",
    "RENDER_SERVICE_ID",
    "RENDER_EXTERNAL_URL",
    "RAILWAY_ENVIRONMENT",
    "FLY_APP_NAME",
    "K_SERVICE",
    "DYNO",
    "VERCEL",
)

_FALLBACK_CHAIN = ["openai", "anthropic", "google", "deepseek", "groq", "ollama"]
_PROVIDER_DISABLE_SECONDS = 900.0
_PROVIDER_DISABLED_UNTIL: Dict[str, float] = {}
_IMAGE_PROVIDER_DISABLED_UNTIL: Dict[str, float] = {}
_VALID_ROLES = {"system", "user", "assistant"}
_IMAGE_PROVIDER_ALIASES = {
    "": "",
    "auto": "",
    "default": "",
    "openai": "openai",
    "chatgpt": "openai",
    "google": "google",
    "gemini": "google",
    "openrouter": "openrouter",
}
_IMAGE_PROVIDER_LABELS = {
    "openai": "ChatGPT",
    "google": "Gemini",
    "openrouter": "OpenRouter",
}
_IMAGE_PROMPT_TARGET_GUIDANCE = {
    "auto": "Optimize the wording for a modern image generation model.",
    "chatgpt": "Optimize the wording for ChatGPT / OpenAI image generation.",
    "gemini": "Optimize the wording for Google Gemini image generation.",
    "canva": "Optimize the wording for Canva-style design generation with a clean focal point and layout-ready phrasing.",
}
_IMAGE_STYLE_HINTS = {
    "vivid": "rich color, cinematic lighting, strong contrast, and a bold focal point",
    "natural": "lifelike detail, realistic lighting, balanced color, and an authentic look",
}
_IMAGE_QUALITY_HINTS = {
    "standard": "clean composition with reliable detail",
    "hd": "very high detail, polished lighting, crisp textures, and premium finish",
}
_TASK_PROVIDER_PREFERENCES = {
    "quick": ["groq", "openai", "google", "deepseek", "anthropic", "ollama"],
    "concept": ["openai", "anthropic", "google", "deepseek", "groq", "ollama"],
    "writing": ["openai", "anthropic", "google", "deepseek", "groq", "ollama"],
    "coding": ["openai", "deepseek", "anthropic", "google", "groq", "ollama"],
    "research": ["google", "openai", "anthropic", "deepseek", "groq", "ollama"],
    "document": ["anthropic", "google", "openai", "deepseek", "groq", "ollama"],
    "image_generation": ["google", "openrouter", "openai"],
    "image_prompting": ["openai", "deepseek", "google", "anthropic", "groq", "ollama"],
    "budget": ["deepseek", "groq", "google", "ollama", "openai", "anthropic"],
}
_TASK_LABELS = {
    "quick": "Fastest high-quality replies",
    "concept": "Reasoning and explanations",
    "writing": "Writing and strategy",
    "coding": "Coding",
    "research": "Search and current info",
    "document": "Long context and documents",
    "image_generation": "Image generation",
    "image_prompting": "Image prompt optimization",
    "budget": "Budget and local fallback",
}
_WRITING_REQUEST_PATTERN = re.compile(
    r"\b(?:write|writing|rewrite|rephrase|improve|polish|draft|email|essay|article|story|caption|copy|content|blog|linkedin|tweet|post|proposal|letter|statement|bio|script)\b",
    re.IGNORECASE,
)
_CONCEPT_REQUEST_PATTERN = re.compile(
    r"\b(?:explain|what is|what are|why|how|compare|difference|teach|understand|concept|meaning|overview)\b",
    re.IGNORECASE,
)
_QUICK_REQUEST_START_PATTERN = re.compile(
    r"^(?:what(?:'s|\s+is)?|who(?:'s|\s+is)?|where(?:'s|\s+is)?|when(?:'s|\s+is)?|define|meaning of|tell me about|explain|summarize)\b",
    re.IGNORECASE,
)
_QUICK_REQUEST_COMPLEXITY_PATTERN = re.compile(
    r"\b(?:compare|difference|detailed|detail|essay|article|research|latest|today|current|news|2024|2025|2026|code|debug|optimize|document|assignment|step by step|roadmap|plan)\b",
    re.IGNORECASE,
)
_DOCUMENT_MARKS_PATTERN = re.compile(
    r"\b(?P<marks>2|3|4|5|8|10|12|15|16)\s*(?:-)?\s*(?:mark|marks)\b",
    re.IGNORECASE,
)
_DOCUMENT_MULTI_QUESTION_PATTERN = re.compile(
    r"\b(?:answer|solve|write|give|provide|return|generate)\s+(?:all|every)\s+(?:the\s+)?(?:questions?|answers?)\b"
    r"|\ball questions?\b"
    r"|\ball question answers?\b"
    r"|\bquestion paper\b"
    r"|\bsub-?questions?\b",
    re.IGNORECASE,
)
_DOCUMENT_ASSIGNMENT_PATTERN = re.compile(r"\b(?:assignment|assignments)\b", re.IGNORECASE)


def _with_presentation_style(base_prompt: str) -> str:
    prompt = str(base_prompt or "").strip()
    extra = get_presentation_style_prompt().strip()
    if not extra or extra in prompt:
        return prompt
    return f"{prompt}\n\n{extra}".strip()


def _should_log_debug() -> bool:
    return bool(getattr(settings, "AI_DEBUG_LOGGING", False) or getattr(settings, "DEBUG", False))


def _request_timeout_seconds() -> int:
    return max(10, int(getattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 60) or 60))


def _image_request_timeout_seconds() -> int:
    return max(
        _request_timeout_seconds(),
        int(getattr(settings, "AI_IMAGE_REQUEST_TIMEOUT_SECONDS", 180) or 180),
    )


def _default_temperature() -> float:
    value = float(getattr(settings, "AI_TEMPERATURE", 0.3) or 0.3)
    return max(0.0, min(value, 1.0))


def _default_max_tokens() -> int:
    value = int(getattr(settings, "AI_MAX_TOKENS", 2048) or 2048)
    return max(128, value)


def _preview_text(text: str) -> str:
    limit = int(getattr(settings, "AI_LOG_PREVIEW_CHARS", 400) or 400)
    cleaned = " ".join((text or "").split())
    return cleaned[:limit]


def _document_answer_max_tokens(question: str) -> int:
    base = _default_max_tokens()
    text = " ".join((question or "").split())
    if not text:
        return base

    marks = [int(match.group("marks")) for match in _DOCUMENT_MARKS_PATTERN.finditer(text)]
    if _DOCUMENT_MULTI_QUESTION_PATTERN.search(text) or len(marks) > 1:
        return max(base, 12288)
    if any(mark >= 15 for mark in marks):
        return max(base, 8192)
    if any(mark >= 10 for mark in marks):
        return max(base, 6144)
    if any(mark >= 8 for mark in marks):
        return max(base, 5120)
    if _DOCUMENT_ASSIGNMENT_PATTERN.search(text):
        return max(base, 4096)
    return base


def _normalize_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for raw in messages or []:
        role = str(raw.get("role", "user")).strip().lower()
        if role not in _VALID_ROLES:
            role = "user"
        content = raw.get("content", "")
        if content is None:
            content = ""
        content = str(content).strip()
        if not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def _log_request(
    provider: str,
    model: Optional[str],
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
):
    if not _should_log_debug():
        return

    logger.info(
        "AI request provider=%s model=%s temperature=%.2f max_tokens=%s message_count=%s preview=%s",
        provider,
        model or "<default>",
        temperature,
        max_tokens,
        len(messages),
        json.dumps(
            [
                {
                    "role": message["role"],
                    "content": _preview_text(message["content"]),
                }
                for message in messages
            ],
            ensure_ascii=False,
        ),
    )


def _log_response(
    provider: str,
    model: Optional[str],
    text: str,
):
    if not _should_log_debug():
        return

    logger.info(
        "AI response provider=%s model=%s chars=%s preview=%s",
        provider,
        model or "<default>",
        len(text or ""),
        _preview_text(text or ""),
    )


def _log_failure(provider: str, model: Optional[str], exc: Exception):
    logger.warning(
        "AI provider failed provider=%s model=%s error=%s",
        provider,
        model or "<default>",
        str(exc),
        exc_info=_should_log_debug(),
    )


def _parse_stream_error_detail(status_code: int, error_body: bytes) -> str:
    try:
        payload = json.loads((error_body or b"").decode("utf-8", errors="replace"))
        error = payload.get("error") or {}
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if isinstance(payload, dict) and payload.get("message"):
            return str(payload["message"])
    except Exception:
        pass

    text = (error_body or b"").decode("utf-8", errors="replace").strip()
    return text or f"HTTP {status_code}"


async def _stream_error_message(response: httpx.Response, provider_label: str) -> str:
    error_body = await response.aread()
    detail = _parse_stream_error_detail(response.status_code, error_body)
    return f"{provider_label} HTTP {response.status_code}: {detail}"


def _provider_temporarily_disabled(provider: str) -> bool:
    disabled_until = _PROVIDER_DISABLED_UNTIL.get(str(provider or "").strip().lower(), 0.0)
    return disabled_until > time.monotonic()


def _should_temporarily_disable_provider(provider: str, exc: Exception) -> bool:
    message = " ".join(str(exc or "").split()).lower()
    if not message:
        return False

    patterns = (
        "insufficient_quota",
        "exceeded your current quota",
        "credit balance is too low",
        "insufficient balance",
        "payment required",
        "invalid api key",
        "authentication",
        "unauthorized",
    )
    return any(pattern in message for pattern in patterns)


def _temporarily_disable_provider(provider: str, exc: Exception) -> None:
    normalized_provider = str(provider or "").strip().lower()
    if not normalized_provider or not _should_temporarily_disable_provider(normalized_provider, exc):
        return

    disabled_until = time.monotonic() + _PROVIDER_DISABLE_SECONDS
    _PROVIDER_DISABLED_UNTIL[normalized_provider] = disabled_until
    logger.info(
        "Provider temporarily disabled provider=%s seconds=%s reason=%s",
        normalized_provider,
        int(_PROVIDER_DISABLE_SECONDS),
        str(exc),
    )


def _image_provider_temporarily_disabled(provider: str) -> bool:
    disabled_until = _IMAGE_PROVIDER_DISABLED_UNTIL.get(str(provider or "").strip().lower(), 0.0)
    return disabled_until > time.monotonic()


def _should_temporarily_disable_image_provider(provider: str, exc: Exception) -> bool:
    message = " ".join(str(exc or "").split()).lower()
    if not message:
        return False

    patterns = (
        "billing_hard_limit_reached",
        "billing hard limit",
        "insufficient credits",
        "not enough credits",
        "requires more credits",
        "resource_exhausted",
        "quota exceeded",
        "rate limit",
        "payment required",
        "invalid api key",
        "authentication",
        "unauthorized",
        "user not found",
        "model not found",
        "no such user",
    )
    return any(pattern in message for pattern in patterns)


def _temporarily_disable_image_provider(provider: str, exc: Exception) -> None:
    normalized_provider = str(provider or "").strip().lower()
    if not normalized_provider or not _should_temporarily_disable_image_provider(normalized_provider, exc):
        return

    disabled_until = time.monotonic() + _PROVIDER_DISABLE_SECONDS
    _IMAGE_PROVIDER_DISABLED_UNTIL[normalized_provider] = disabled_until
    logger.info(
        "Image provider temporarily disabled provider=%s seconds=%s reason=%s",
        normalized_provider,
        int(_PROVIDER_DISABLE_SECONDS),
        str(exc),
    )


def _resolve_provider() -> str:
    configured = (getattr(settings, "AI_PROVIDER", "") or "").lower().strip()
    if configured == "auto":
        configured = ""
    if configured:
        return configured
    if _openai_api_key() and not _provider_temporarily_disabled("openai"):
        return "openai"
    if getattr(settings, "ANTHROPIC_API_KEY", "") and not _provider_temporarily_disabled("anthropic"):
        return "anthropic"
    if _google_api_key() and not _provider_temporarily_disabled("google"):
        return "google"
    if _deepseek_api_key() and not _provider_temporarily_disabled("deepseek"):
        return "deepseek"
    if getattr(settings, "GROQ_API_KEY", "") and not _provider_temporarily_disabled("groq"):
        return "groq"
    if _ollama_available() and not _provider_temporarily_disabled("ollama"):
        return "ollama"
    return ""


def _running_in_hosted_runtime() -> bool:
    return any(str(os.getenv(name, "")).strip() for name in _HOSTED_RUNTIME_ENV_VARS)


def _ollama_base_url() -> str:
    return str(getattr(settings, "OLLAMA_BASE_URL", "") or "").strip()


def _ollama_is_loopback() -> bool:
    base_url = _ollama_base_url()
    if not base_url:
        return False
    try:
        hostname = (urlparse(base_url).hostname or "").strip().lower()
    except Exception:
        return False
    return hostname in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _ollama_available() -> bool:
    base_url = _ollama_base_url()
    if not base_url:
        return False
    if _running_in_hosted_runtime() and _ollama_is_loopback():
        return False
    return True


def _google_api_key() -> str:
    return getattr(settings, "GOOGLE_API_KEY", "") or getattr(settings, "GEMINI_API_KEY", "") or ""


def _openai_api_key() -> str:
    return getattr(settings, "OPENAI_API_KEY", "") or ""


def _deepseek_api_key() -> str:
    return getattr(settings, "DEEPSEEK_API_KEY", "") or ""


def _openrouter_api_key() -> str:
    return getattr(settings, "OPENROUTER_API_KEY", "") or ""


def is_quick_answer_request(mode: Optional[str] = None, message: Optional[str] = None) -> bool:
    normalized_mode = str(mode or "chat").strip().lower()
    if normalized_mode != "chat":
        return False

    text = " ".join((message or "").split()).strip()
    if not text:
        return False

    lowered_text = text.lower()

    if len(text) > 90 or len(text.split()) > 14:
        return False

    if lowered_text.startswith("explain ") and len(text.split()) > 4:
        return False

    if lowered_text.startswith(("what is ", "what are ", "what's ")) and " how " in lowered_text:
        return False

    if any(
        marker in lowered_text
        for marker in (
            " classified",
            " classification",
            " types of ",
            " advantages",
            " disadvantages",
            " use cases",
        )
    ):
        return False

    if _WRITING_REQUEST_PATTERN.search(text) or _DOCUMENT_ASSIGNMENT_PATTERN.search(text):
        return False

    if _QUICK_REQUEST_COMPLEXITY_PATTERN.search(text):
        return False

    return bool(_QUICK_REQUEST_START_PATTERN.search(text) or len(text.split()) <= 6)


def infer_use_case(mode: Optional[str] = None, message: Optional[str] = None) -> str:
    normalized_mode = str(mode or "chat").strip().lower()
    text = " ".join((message or "").split()).strip()

    if normalized_mode == "image":
        return "image_generation"
    if normalized_mode == "search":
        return "research"
    if normalized_mode == "code":
        return "coding"
    if normalized_mode == "documents":
        return "document"
    if normalized_mode in {"summary", "summarize", "rewrite"}:
        return "writing"
    if is_quick_answer_request(normalized_mode, text):
        return "quick"
    if normalized_mode in {"deep", "knowledge", "learning", "safe"}:
        if _WRITING_REQUEST_PATTERN.search(text):
            return "writing"
        return "concept"
    if _WRITING_REQUEST_PATTERN.search(text):
        return "writing"
    if _CONCEPT_REQUEST_PATTERN.search(text):
        return "concept"
    return "concept"


def _configured_provider_override() -> Optional[str]:
    configured = (getattr(settings, "AI_PROVIDER", "") or "").lower().strip()
    if configured == "auto":
        return None
    return configured or None


def _configured_model_override() -> Optional[str]:
    configured = (getattr(settings, "AI_MODEL", "") or "").strip()
    return configured or None


def _configured_provider_model(provider: str) -> Optional[str]:
    mapping = {
        "deepseek": getattr(settings, "DEEPSEEK_MODEL", ""),
        "groq": getattr(settings, "GROQ_MODEL", ""),
        "anthropic": getattr(settings, "ANTHROPIC_MODEL", ""),
    }
    configured = str(mapping.get(provider, "") or "").strip()
    return configured or None


def _openrouter_request_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": getattr(settings, "openrouter_referer", "http://localhost:3000"),
        "X-Title": getattr(settings, "openrouter_app_name", getattr(settings, "APP_NAME", "NOVA AI")),
    }


def _provider_chain_for_use_case(use_case: Optional[str]) -> List[str]:
    requested_use_case = str(use_case or "").strip().lower()
    preferred = _TASK_PROVIDER_PREFERENCES.get(requested_use_case) or _FALLBACK_CHAIN
    return list(dict.fromkeys([*preferred, *_FALLBACK_CHAIN]))


def _provider_default_model(provider: str, use_case: Optional[str] = None) -> str:
    normalized_use_case = str(use_case or "").strip().lower()
    if provider == "openai":
        if normalized_use_case == "quick":
            return getattr(settings, "OPENAI_FAST_MODEL", "") or "gpt-4o-mini"
        if normalized_use_case == "coding":
            return getattr(settings, "OPENAI_CODE_MODEL", "") or getattr(settings, "OPENAI_CHAT_MODEL", "") or "gpt-4o"
        if normalized_use_case in {"concept", "document", "research"}:
            return getattr(settings, "OPENAI_EXPLAIN_MODEL", "") or getattr(settings, "OPENAI_CHAT_MODEL", "") or "gpt-4o"
        return getattr(settings, "OPENAI_CHAT_MODEL", "") or "gpt-4o"
    if provider == "deepseek":
        return _configured_provider_model("deepseek") or _DEFAULT_DEEPSEEK_MODEL
    if provider == "google":
        return getattr(settings, "GEMINI_CHAT_MODEL", "") or _DEFAULT_GEMINI_MODEL
    if provider == "groq":
        return _configured_provider_model("groq") or _DEFAULT_GROQ_MODEL
    if provider == "anthropic":
        return _configured_provider_model("anthropic") or _DEFAULT_ANTHROPIC_MODEL
    return _DEFAULT_OLLAMA_MODEL


def _normalize_image_provider(provider: Optional[str]) -> str:
    normalized = str(provider or "").strip().lower()
    return _IMAGE_PROVIDER_ALIASES.get(normalized, normalized)


def _is_explicit_auto_image_provider(provider: Optional[str]) -> bool:
    if provider is None:
        return False
    normalized = str(provider or "").strip().lower()
    return normalized in {"", "auto", "default"}


def _image_provider_ready(provider: str) -> bool:
    if provider == "openai":
        return bool(_openai_api_key())
    if provider == "google":
        return bool(_google_api_key())
    if provider == "openrouter":
        return bool(_openrouter_api_key())
    return False


def _image_provider_available(provider: str) -> bool:
    return _image_provider_ready(provider) and not _image_provider_temporarily_disabled(provider)


def _resolve_image_provider(provider: Optional[str] = None) -> Optional[str]:
    requested = _normalize_image_provider(provider)
    if requested:
        return requested if _image_provider_available(requested) else None

    if not _is_explicit_auto_image_provider(provider):
        configured = _normalize_image_provider(getattr(settings, "AI_IMAGE_PROVIDER", "") or "")
        if configured:
            return configured if _image_provider_available(configured) else None

    if _image_provider_available("google"):
        return "google"
    if _image_provider_available("openrouter"):
        return "openrouter"
    if _image_provider_available("openai"):
        return "openai"
    return None


def _resolve_image_provider_chain(provider: Optional[str] = None) -> List[str]:
    requested = _normalize_image_provider(provider)
    if requested:
        return [requested] if _image_provider_available(requested) else []

    preferred_chain = _provider_chain_for_use_case("image_generation")
    chain: List[str] = []

    if not _is_explicit_auto_image_provider(provider):
        configured = _normalize_image_provider(getattr(settings, "AI_IMAGE_PROVIDER", "") or "")
        if configured and _image_provider_available(configured):
            chain.append(configured)

    for candidate in preferred_chain:
        if (
            candidate in {"google", "openai", "openrouter"}
            and _image_provider_available(candidate)
            and candidate not in chain
        ):
            chain.append(candidate)

    return chain


def _resolve_prompt_enhancer_provider(provider: Optional[str] = None) -> Optional[str]:
    requested = _normalize_image_provider(provider)
    if requested and _provider_available(requested):
        return requested

    configured = str(getattr(settings, "IMAGE_PROMPT_ENHANCER_PROVIDER", "") or "").strip().lower()
    if configured and _provider_available(configured):
        return configured

    for candidate in (
        _resolve_provider(),
        "openai",
        "deepseek",
        "google",
        "anthropic",
        "groq",
        *[item for item in _FALLBACK_CHAIN if item not in {"openai", "deepseek", "google", "anthropic", "groq"}],
    ):
        normalized = str(candidate or "").strip().lower()
        if normalized and _provider_available(normalized):
            return normalized
    return None


def _normalize_image_prompt_target(target: Optional[str]) -> str:
    normalized = str(target or "").strip().lower()
    if normalized in {"", "auto", "default"}:
        return "auto"
    if normalized in {"openai", "chatgpt"}:
        return "chatgpt"
    if normalized in {"google", "gemini"}:
        return "gemini"
    if normalized == "canva":
        return "canva"
    return "auto"


def _clean_image_prompt(prompt: str, limit: int = 4000) -> str:
    return " ".join((prompt or "").split()).strip()[:limit]


def _heuristic_image_prompt(
    prompt: str,
    *,
    size: str = "1024x1024",
    quality: str = "standard",
    style: str = "vivid",
) -> str:
    cleaned_prompt = _clean_image_prompt(prompt, 2400)
    if not cleaned_prompt:
        return ""

    details = [
        cleaned_prompt,
        f"Aspect ratio target: {_image_size_to_aspect_ratio(size)}.",
        f"Visual style: {_IMAGE_STYLE_HINTS.get(style, _IMAGE_STYLE_HINTS['vivid'])}.",
        f"Quality target: {_IMAGE_QUALITY_HINTS.get(quality, _IMAGE_QUALITY_HINTS['standard'])}.",
    ]

    lowered = cleaned_prompt.lower()
    if "text" not in lowered and "caption" not in lowered and "logo" not in lowered:
        details.append("Avoid captions, watermarks, logos, and stray text unless explicitly requested.")

    return " ".join(details).strip()


def _image_generation_prompt_for_provider(
    prompt: str,
    *,
    provider: str,
    size: str = "1024x1024",
    quality: str = "standard",
    style: str = "vivid",
) -> str:
    cleaned_prompt = _clean_image_prompt(prompt, 3200)
    if not cleaned_prompt:
        return ""

    if provider == "google":
        return _heuristic_image_prompt(
            cleaned_prompt,
            size=size,
            quality=quality,
            style=style,
        )
    return cleaned_prompt


def _image_size_to_aspect_ratio(size: str) -> str:
    normalized = str(size or "").strip().lower()
    if normalized == "1792x1024":
        return "16:9"
    if normalized == "1024x1792":
        return "9:16"
    return "1:1"


def _google_image_models() -> List[str]:
    configured_model = str(getattr(settings, "GEMINI_IMAGE_MODEL", "") or "").strip()
    models: List[str] = []
    for candidate in (configured_model, _DEFAULT_GEMINI_IMAGE_MODEL):
        if candidate and candidate not in models:
            models.append(candidate)
    return models


def _google_image_generation_config(size: str) -> Dict[str, object]:
    config: Dict[str, object] = {
        "responseModalities": ["TEXT", "IMAGE"],
    }
    aspect_ratio = _image_size_to_aspect_ratio(size)
    if aspect_ratio:
        config["imageConfig"] = {"aspectRatio": aspect_ratio}
    return config


def _google_image_error(payload: Any, status_code: int, model_name: str) -> RuntimeError:
    message = ""
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "").strip()
            status = str(error.get("status") or "").strip()
            if status and status not in message:
                message = f"{status}: {message}" if message else status
    if not message:
        message = f"Gemini image request failed with HTTP {status_code}"
    return RuntimeError(f"{message} (model={model_name})")


def _summarize_image_provider_error(exc: Exception) -> str:
    message = " ".join(str(exc or "").split()).strip()
    lowered = message.lower()

    if "user not found" in lowered or "model not found" in lowered or "no such user" in lowered:
        return "account or model access error"
    if "billing_hard_limit_reached" in lowered or "billing hard limit" in lowered:
        return "billing hard limit reached"
    if "insufficient credits" in lowered or "not enough credits" in lowered:
        return "insufficient credits"
    if "requires more credits" in lowered or "can only afford" in lowered:
        return "insufficient credits"
    if "no endpoints found" in lowered:
        return "model unavailable"
    if "resource_exhausted" in lowered or "quota exceeded" in lowered:
        return "quota exhausted"
    if "content_policy_violation" in lowered or "content policy" in lowered:
        return "prompt blocked by content policy"
    if "rate limit" in lowered:
        return "rate limited"
    if "provider not configured" in lowered or "no supported image provider" in lowered:
        return "provider not configured"
    return message[:220] if message else "unknown error"


def _build_image_provider_failure(provider_errors: List[tuple[str, Exception]]) -> RuntimeError:
    if not provider_errors:
        return RuntimeError("All image providers failed.")

    details = [
        f"{_IMAGE_PROVIDER_LABELS.get(provider, provider.title())}: {_summarize_image_provider_error(exc)}"
        for provider, exc in provider_errors
    ]
    return RuntimeError(f"All image providers failed. {'; '.join(details)}")


def _inline_data_to_data_url(inline_data) -> Optional[str]:
    if inline_data is None:
        return None

    if isinstance(inline_data, dict):
        data = inline_data.get("data")
        mime_type = inline_data.get("mimeType") or inline_data.get("mime_type") or "image/png"
    else:
        data = getattr(inline_data, "data", None)
        mime_type = getattr(inline_data, "mime_type", None) or getattr(inline_data, "mimeType", None) or "image/png"

    if not data:
        return None

    if isinstance(data, str):
        encoded = data if not data.startswith("data:") else data.split(",", 1)[-1]
        return data if data.startswith("data:") else f"data:{mime_type};base64,{encoded}"

    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _google_response_to_images(payload: Any) -> List[str]:
    if not isinstance(payload, dict):
        return []

    images: List[str] = []
    for candidate in payload.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content") or {}
        if not isinstance(content, dict):
            continue
        for part in content.get("parts") or []:
            if not isinstance(part, dict):
                continue
            data_url = _inline_data_to_data_url(part.get("inlineData") or part.get("inline_data"))
            if data_url:
                images.append(data_url)
    return images


def _openrouter_image_models() -> List[str]:
    configured_model = str(getattr(settings, "OPENROUTER_IMAGE_MODEL", "") or "").strip()
    models = [configured_model] if configured_model else []
    for candidate in [_DEFAULT_OPENROUTER_IMAGE_MODEL, *_OPENROUTER_IMAGE_FALLBACK_MODELS]:
        normalized = str(candidate or "").strip()
        if normalized and normalized not in models:
            models.append(normalized)
    return models


def _openrouter_image_modalities(model_name: str) -> List[str]:
    normalized = str(model_name or "").strip().lower()
    if any(marker in normalized for marker in ("flux", "sourceful/", "recraft", "playground")):
        return ["image"]
    return ["image", "text"]


def _openrouter_image_config(size: str, quality: str) -> Dict[str, str]:
    config: Dict[str, str] = {}
    aspect_ratio = _image_size_to_aspect_ratio(size)
    if aspect_ratio:
        config["aspect_ratio"] = aspect_ratio
    return config


def _openrouter_error(payload: Any, status_code: int, model_name: str) -> RuntimeError:
    message = ""
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "").strip()
        if not message:
            message = str(payload.get("message") or "").strip()
    if not message:
        message = f"OpenRouter image request failed with HTTP {status_code}"
    return RuntimeError(f"{message} (model={model_name})")


def _openrouter_image_request_body(
    prompt: str,
    model_name: str,
    *,
    size: str,
    quality: str,
) -> Dict[str, Any]:
    modalities = _openrouter_image_modalities(model_name)
    body: Dict[str, Any] = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": modalities,
    }
    image_config = _openrouter_image_config(size, quality)
    if image_config:
        body["image_config"] = image_config
    if "text" in modalities:
        # Keep output token reservation tiny so image+text models do not request
        # far more credits than needed for a single generated image.
        body["max_tokens"] = 64
    return body


def _openrouter_response_to_images(payload: Any) -> List[str]:
    if not isinstance(payload, dict):
        return []

    choices = payload.get("choices") or []
    if not isinstance(choices, list) or not choices:
        return []

    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get("message") or choice.get("delta") or {}
    if not isinstance(message, dict):
        return []

    images: List[str] = []
    for item in message.get("images") or []:
        if not isinstance(item, dict):
            continue
        image_url = item.get("image_url") or item.get("imageUrl") or {}
        if isinstance(image_url, dict):
            url = str(image_url.get("url") or "").strip()
        else:
            url = str(image_url or "").strip()
        if url:
            images.append(url)
    return images


def _normalize_image_mime_type(mime_type: Optional[str]) -> str:
    normalized = str(mime_type or "").strip().lower()
    if normalized.startswith("image/"):
        return normalized
    return "image/png"


def _looks_like_base64_image_payload(value: str) -> bool:
    candidate = "".join(str(value or "").split())
    if len(candidate) < 64:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9+/=]+", candidate))


def normalize_image_asset(value: Any) -> Optional[str]:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    if lowered.startswith("data:image/"):
        return candidate
    if lowered.startswith("data:"):
        return None
    if lowered.startswith(("http://", "https://")):
        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https"} and parsed.netloc and not any(ch.isspace() for ch in candidate):
            return candidate
        return None
    if _looks_like_base64_image_payload(candidate):
        return f"data:image/png;base64,{candidate}"
    return None


def sanitize_image_assets(images: List[Any], limit: Optional[int] = None) -> List[str]:
    sanitized: List[str] = []
    seen: set[str] = set()
    max_items = None if limit is None else max(0, int(limit))

    for raw_image in images or []:
        candidate = normalize_image_asset(raw_image)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        sanitized.append(candidate)
        if max_items is not None and len(sanitized) >= max_items:
            break

    return sanitized


def _image_bytes_to_data_url(image_bytes: bytes, mime_type: Optional[str] = None) -> str:
    normalized_mime_type = _normalize_image_mime_type(mime_type)
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{normalized_mime_type};base64,{encoded}"


def _extract_openai_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                if item.strip():
                    parts.append(item.strip())
                continue
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text = str(item.get("text") or "").strip()
                    if text:
                        parts.append(text)
        return "\n".join(parts).strip()

    return str(content or "").strip()


def _google_response_to_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    parts: List[str] = []
    for candidate in payload.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content") or {}
        if not isinstance(content, dict):
            continue
        for part in content.get("parts") or []:
            if not isinstance(part, dict):
                continue
            text = str(part.get("text") or "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


async def _request_google_image_generation(
    client: httpx.AsyncClient,
    api_key: str,
    model_name: str,
    parts: List[Dict[str, object]],
    size: str = "1024x1024",
) -> List[str]:
    response = await client.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent",
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": parts,
                }
            ],
            "generationConfig": _google_image_generation_config(size),
        },
    )

    try:
        payload: Any = response.json()
    except ValueError:
        payload = {"error": {"message": response.text}}

    if response.status_code >= 400:
        raise _google_image_error(payload, response.status_code, model_name)

    return _google_response_to_images(payload)


async def _generate_image_with_openai(
    cleaned_prompt: str,
    size: str = "1024x1024",
    n: int = 1,
    quality: str = "standard",
    style: str = "vivid",
) -> List[str]:
    openai_key = _openai_api_key()
    if not openai_key:
        return []

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=openai_key, timeout=_image_request_timeout_seconds())
    model_name = getattr(settings, "OPENAI_IMAGE_MODEL", "dall-e-3")
    request_args = {
        "model": model_name,
        "prompt": cleaned_prompt,
        "size": size,
        "n": n,
        "response_format": "b64_json",
    }
    if model_name == "dall-e-3":
        request_args["quality"] = quality or getattr(settings, "OPENAI_IMAGE_QUALITY", "hd") or "hd"
        if style in {"vivid", "natural"}:
            request_args["style"] = style
    response = await client.images.generate(**request_args)
    return [
        item.b64_json
        if str(item.b64_json or "").startswith("data:")
        else f"data:image/png;base64,{item.b64_json}"
        for item in response.data
        if getattr(item, "b64_json", None)
    ]


async def _generate_image_with_google(
    cleaned_prompt: str,
    size: str = "1024x1024",
    n: int = 1,
) -> List[str]:
    api_key = _google_api_key()
    if not api_key:
        return []

    requested_images = max(1, min(int(n or 1), 4))
    last_error: Optional[Exception] = None

    async with httpx.AsyncClient(timeout=_image_request_timeout_seconds()) as client:
        for model_name in _google_image_models():
            images: List[str] = []
            try:
                for _ in range(requested_images):
                    generated = await _request_google_image_generation(
                        client,
                        api_key,
                        model_name,
                        [{"text": cleaned_prompt}],
                        size=size,
                    )
                    if not generated:
                        break
                    images.extend(generated)
                    if len(images) >= requested_images:
                        return images[:requested_images]
                if images:
                    return images[:requested_images]
            except Exception as exc:
                last_error = exc

    if last_error is not None:
        raise last_error
    return []


async def _generate_image_with_openrouter(
    cleaned_prompt: str,
    size: str = "1024x1024",
    n: int = 1,
    quality: str = "standard",
) -> List[str]:
    api_key = _openrouter_api_key()
    if not api_key:
        return []

    requested_images = max(1, min(int(n or 1), 4))
    endpoint = f"{str(getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')).rstrip('/')}/chat/completions"
    headers = _openrouter_request_headers(api_key)

    images: List[str] = []
    last_error: Optional[Exception] = None

    async with httpx.AsyncClient(timeout=_image_request_timeout_seconds()) as client:
        for model_name in _openrouter_image_models():
            images = []
            for _ in range(requested_images):
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=_openrouter_image_request_body(
                        cleaned_prompt,
                        model_name,
                        size=size,
                        quality=quality,
                    ),
                )

                try:
                    payload: Any = response.json()
                except ValueError:
                    payload = {"error": {"message": response.text}}

                if response.status_code >= 400:
                    last_error = _openrouter_error(payload, response.status_code, model_name)
                    break

                generated = _openrouter_response_to_images(payload)
                if not generated:
                    last_error = RuntimeError(f"OpenRouter returned no images (model={model_name})")
                    break

                images.extend(generated)
                if len(images) >= requested_images:
                    return images[:requested_images]

            if images:
                return images[:requested_images]

    if images:
        return images[:requested_images]
    if last_error is not None:
        raise last_error
    return []


async def _edit_image_with_google(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/png",
) -> List[str]:
    api_key = _google_api_key()
    if not api_key:
        return []

    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    parts = [
        {"text": prompt},
        {
            "inline_data": {
                "mime_type": _normalize_image_mime_type(mime_type),
                "data": encoded_image,
            }
        },
    ]
    last_error: Optional[Exception] = None

    async with httpx.AsyncClient(timeout=_image_request_timeout_seconds()) as client:
        for model_name in _google_image_models():
            try:
                images = await _request_google_image_generation(
                    client,
                    api_key,
                    model_name,
                    parts,
                )
                if images:
                    return images
            except Exception as exc:
                last_error = exc

    if last_error is not None:
        raise last_error
    return []


async def _edit_image_with_openrouter(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/png",
) -> List[str]:
    api_key = _openrouter_api_key()
    if not api_key:
        return []

    endpoint = f"{str(getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')).rstrip('/')}/chat/completions"
    headers = _openrouter_request_headers(api_key)
    data_url = _image_bytes_to_data_url(image_bytes, mime_type)

    async with httpx.AsyncClient(timeout=_image_request_timeout_seconds()) as client:
        last_error: Optional[Exception] = None
        for model_name in _openrouter_image_models():
            body = _openrouter_image_request_body(prompt, model_name, size="1024x1024", quality="standard")
            body["messages"] = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ]
            response = await client.post(
                endpoint,
                headers=headers,
                json=body,
            )

            try:
                payload: Any = response.json()
            except ValueError:
                payload = {"error": {"message": response.text}}

            if response.status_code >= 400:
                last_error = _openrouter_error(payload, response.status_code, model_name)
                continue

            images = _openrouter_response_to_images(payload)
            if images:
                return images
            last_error = RuntimeError(f"OpenRouter returned no images (model={model_name})")

    if last_error is not None:
        raise last_error
    return []


async def _edit_image_with_openai(
    prompt: str,
    image_bytes: bytes,
) -> List[str]:
    openai_key = _openai_api_key()
    if not openai_key:
        return []

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=openai_key, timeout=_image_request_timeout_seconds())
    image_file = io.BytesIO(image_bytes)
    image_file.name = "image.png"

    try:
        response = await client.images.edit(
            model="gpt-image-1.5",
            image=image_file,
            prompt=prompt,
        )
    except (AttributeError, TypeError):
        image_file.seek(0)
        response = await client.images.create_variation(
            model="dall-e-2",
            image=image_file,
            n=1,
            size="1024x1024",
            response_format="url",
        )

    images: List[str] = []
    for item in getattr(response, "data", []) or []:
        url = getattr(item, "url", None)
        if url:
            images.append(url)
            continue

        b64_json = getattr(item, "b64_json", None)
        if b64_json:
            images.append(f"data:image/png;base64,{b64_json}")

    return images


async def _analyze_image_with_openai(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/png",
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> str:
    openai_key = _openai_api_key()
    if not openai_key:
        return ""

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=openai_key, timeout=_request_timeout_seconds())
    model_name = (
        str(model or "").strip()
        or str(getattr(settings, "OPENAI_VISION_MODEL", "") or "").strip()
        or str(getattr(settings, "OPENAI_CHAT_MODEL", "") or "").strip()
        or "gpt-4o-mini"
    )
    data_url = _image_bytes_to_data_url(image_bytes, mime_type)

    response = await client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": _with_presentation_style(
                    "Analyze the uploaded image carefully and answer the user's request accurately. "
                    "Describe only what is actually visible and say when something is uncertain."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        temperature=_default_temperature(),
        max_tokens=max_tokens or _default_max_tokens(),
    )
    content = ((response.choices or [None])[0].message.content if getattr(response, "choices", None) else "")
    return _extract_openai_message_text(content)


async def _analyze_image_with_google(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/png",
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> str:
    api_key = _google_api_key()
    if not api_key:
        return ""

    model_name = (
        str(model or "").strip()
        or str(getattr(settings, "GEMINI_VISION_MODEL", "") or "").strip()
        or _DEFAULT_GEMINI_MODEL
    )
    normalized_mime_type = _normalize_image_mime_type(mime_type)
    encoded_image = base64.b64encode(image_bytes).decode("ascii")

    async with httpx.AsyncClient(timeout=_request_timeout_seconds()) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": normalized_mime_type,
                                    "data": encoded_image,
                                }
                            },
                        ],
                    }
                ],
                "generationConfig": {
                    "temperature": _default_temperature(),
                    "maxOutputTokens": max_tokens or _default_max_tokens(),
                },
            },
        )

    try:
        payload: Any = response.json()
    except ValueError:
        payload = {"error": {"message": response.text}}

    if response.status_code >= 400:
        raise _google_image_error(payload, response.status_code, model_name)

    return _google_response_to_text(payload)


def _messages_to_gemini(messages: List[Dict[str, str]]):
    from google.genai import types  # type: ignore

    system_parts: List[str] = []
    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_parts.append(content)
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append(types.Content(role=gemini_role, parts=[types.Part.from_text(text=content)]))
    return contents, "\n\n".join(part for part in system_parts if part).strip()


def _model_for_provider(
    provider: str,
    requested_provider: str,
    explicit_model: Optional[str],
) -> Optional[str]:
    if explicit_model and provider == requested_provider:
        return explicit_model

    if provider != requested_provider:
        return None

    configured_model = (getattr(settings, "AI_MODEL", "") or "").strip()
    if not configured_model:
        return None

    if provider == "openai":
        return configured_model
    if provider == "deepseek" and configured_model.startswith("deepseek-"):
        return configured_model
    if provider == "google" and configured_model.startswith("gemini-"):
        return configured_model
    if provider == "anthropic" and configured_model.startswith("claude-"):
        return configured_model
    if provider == "groq" and not configured_model.startswith(("gpt-", "gemini-", "claude-", "deepseek-")):
        return configured_model
    if provider == "ollama":
        return configured_model

    return None


async def _stream_google(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    from google import genai
    from google.genai import types  # type: ignore

    api_key = _google_api_key()
    if not api_key:
        raise RuntimeError("Missing GOOGLE_API_KEY or GEMINI_API_KEY")

    model_name = model or getattr(settings, "GEMINI_CHAT_MODEL", "") or _DEFAULT_GEMINI_MODEL
    if not model_name.startswith("gemini-"):
        model_name = getattr(settings, "GEMINI_CHAT_MODEL", "") or _DEFAULT_GEMINI_MODEL

    contents, system_instruction = _messages_to_gemini(messages)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction or None,
        temperature=temperature if temperature is not None else _default_temperature(),
        max_output_tokens=max_tokens or _default_max_tokens(),
    )

    client = genai.Client(api_key=api_key)
    stream = await client.aio.models.generate_content_stream(
        model=model_name,
        contents=contents,
        config=config,
    )
    async for chunk in stream:
        text = getattr(chunk, "text", None)
        if text:
            yield text


async def _stream_groq(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    api_key = getattr(settings, "GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY")

    payload = {
        "model": model or _provider_default_model("groq"),
        "messages": messages,
        "stream": True,
        "max_tokens": max_tokens or _default_max_tokens(),
        "temperature": temperature if temperature is not None else _default_temperature(),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=_request_timeout_seconds()) as client:
        async with client.stream(
            "POST",
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code >= 400:
                raise RuntimeError(await _stream_error_message(response, "Groq"))
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line.replace("data:", "", 1).strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                token = ((event.get("choices") or [{}])[0].get("delta") or {}).get("content")
                if token:
                    yield token


async def _stream_deepseek(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    from openai import AsyncOpenAI

    api_key = _deepseek_api_key()
    if not api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        timeout=_request_timeout_seconds(),
    )
    stream = await client.chat.completions.create(
        model=model or _provider_default_model("deepseek"),
        messages=messages,
        stream=True,
        temperature=temperature if temperature is not None else _default_temperature(),
        max_tokens=max_tokens or _default_max_tokens(),
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def _stream_anthropic(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    import anthropic as _anthropic  # type: ignore

    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY")

    system = next((message["content"] for message in messages if message["role"] == "system"), "")
    user_messages = [message for message in messages if message["role"] != "system"]

    client = _anthropic.AsyncAnthropic(api_key=api_key, timeout=_request_timeout_seconds())
    async with client.messages.stream(
        model=model or _provider_default_model("anthropic"),
        max_tokens=max_tokens or _default_max_tokens(),
        temperature=temperature if temperature is not None else _default_temperature(),
        system=system,
        messages=user_messages,
    ) as stream:
        async for text in stream.text_stream:
            if text:
                yield text


async def _stream_ollama(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    payload = {
        "model": model or _DEFAULT_OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
        "options": {
            "num_predict": max_tokens or getattr(settings, "OLLAMA_NUM_PREDICT", 512),
            "num_ctx": getattr(settings, "OLLAMA_NUM_CTX", 4096),
            "temperature": temperature if temperature is not None else _default_temperature(),
        },
    }

    async with httpx.AsyncClient(timeout=_request_timeout_seconds()) as client:
        async with client.stream(
            "POST",
            f"{getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')}/api/chat",
            json=payload,
        ) as response:
            if response.status_code >= 400:
                raise RuntimeError(await _stream_error_message(response, "Ollama"))
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = data.get("message", {}).get("content", "")
                if token:
                    yield token


async def _stream_openai(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    from openai import AsyncOpenAI

    api_key = _openai_api_key()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")

    client = AsyncOpenAI(api_key=api_key, timeout=_request_timeout_seconds())
    stream = await client.chat.completions.create(
        model=model or getattr(settings, "OPENAI_CHAT_MODEL", "gpt-4o"),
        messages=messages,
        stream=True,
        temperature=temperature if temperature is not None else _default_temperature(),
        max_tokens=max_tokens or _default_max_tokens(),
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


_PROVIDER_STREAM_MAP = {
    "openai": _stream_openai,
    "deepseek": _stream_deepseek,
    "google": _stream_google,
    "groq": _stream_groq,
    "anthropic": _stream_anthropic,
    "ollama": _stream_ollama,
}


def _provider_ready(provider: str) -> bool:
    if provider == "openai":
        return bool(_openai_api_key())
    if provider == "deepseek":
        return bool(_deepseek_api_key())
    if provider == "google":
        return bool(_google_api_key())
    if provider == "groq":
        return bool(getattr(settings, "GROQ_API_KEY", ""))
    if provider == "anthropic":
        return bool(getattr(settings, "ANTHROPIC_API_KEY", ""))
    if provider == "ollama":
        return _ollama_available()
    return False


def _provider_available(provider: str) -> bool:
    return _provider_ready(provider) and not _provider_temporarily_disabled(provider)


def _auto_provider_attempt_limit() -> int:
    value = int(getattr(settings, "AI_AUTO_MAX_PROVIDER_ATTEMPTS", 2) or 2)
    return max(1, value)


def _provider_chain(provider: Optional[str], use_case: Optional[str] = None) -> List[str]:
    explicit_provider = (provider or "").lower().strip()
    if explicit_provider:
        return [explicit_provider]

    configured_provider = _configured_provider_override()
    if configured_provider:
        return [configured_provider] + [item for item in _FALLBACK_CHAIN if item != configured_provider]

    preferred_chain = _provider_chain_for_use_case(use_case)
    if use_case:
        return preferred_chain

    requested = _resolve_provider().lower().strip()
    if requested in preferred_chain:
        return [requested] + [item for item in preferred_chain if item != requested]
    return preferred_chain


def _ready_provider_chain(provider: Optional[str], use_case: Optional[str] = None) -> List[str]:
    chain = _provider_chain(provider, use_case=use_case)
    ready_chain = [item for item in chain if _provider_available(item)]
    if provider:
        return ready_chain

    attempt_limit = _auto_provider_attempt_limit()
    if len(ready_chain) > attempt_limit:
        logger.info(
            "Limiting automatic AI provider fallback attempts limit=%s chain=%s use_case=%s",
            attempt_limit,
            ready_chain[:attempt_limit],
            use_case or "<default>",
        )
    return ready_chain[:attempt_limit]


def describe_default_provider_stack() -> List[Dict[str, Any]]:
    return [
        {
            "use_case": use_case,
            "label": _TASK_LABELS.get(use_case, use_case.replace("_", " ").title()),
            "providers": providers,
        }
        for use_case, providers in _TASK_PROVIDER_PREFERENCES.items()
    ]


async def stream_direct(
    messages: List[Dict[str, str]],
    provider: str,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    use_case: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    key = (provider or "").lower().strip()
    fn = _PROVIDER_STREAM_MAP.get(key)
    if fn is None:
        raise RuntimeError(f"Unsupported provider: {provider}")
    if _provider_temporarily_disabled(key):
        raise RuntimeError(f"Provider temporarily unavailable: {key}")
    if not _provider_ready(key):
        raise RuntimeError(f"Provider not configured: {key}")

    normalized_messages = _normalize_messages(messages)
    if not normalized_messages:
        raise RuntimeError("No valid messages were provided to the AI service")

    resolved_model = model or _provider_default_model(key, use_case)
    resolved_temperature = temperature if temperature is not None else _default_temperature()
    resolved_max_tokens = max_tokens or _default_max_tokens()
    _log_request(key, resolved_model, normalized_messages, resolved_temperature, resolved_max_tokens)

    async for token in fn(
        normalized_messages,
        resolved_model,
        resolved_temperature,
        resolved_max_tokens,
    ):
        yield token


async def direct_completion(
    messages: List[Dict[str, str]],
    provider: str,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    use_case: Optional[str] = None,
) -> str:
    tokens: List[str] = []
    async for token in stream_direct(messages, provider, model, temperature, max_tokens, use_case=use_case):
        tokens.append(token)
    text = "".join(tokens).strip()
    if not text:
        raise RuntimeError(f"Provider '{provider}' returned an empty response")
    _log_response(provider, model, text)
    return text


async def _stream_with_fallback(
    messages: List[Dict[str, str]],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    use_case: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    normalized_messages = _normalize_messages(messages)
    if not normalized_messages:
        raise RuntimeError("No valid messages were provided to the AI service")

    ready_chain = _ready_provider_chain(provider, use_case=use_case)
    if not ready_chain:
        if provider:
            if _provider_temporarily_disabled(provider):
                raise RuntimeError(f"Provider temporarily unavailable: {provider}")
            raise RuntimeError(f"Provider not configured: {provider}")
        logger.warning("No configured AI providers were available")
        yield _OFFLINE_TEXT
        return

    requested_provider = (provider or _configured_provider_override() or _resolve_provider()).lower().strip()
    errors: List[str] = []

    for current_provider in ready_chain:
        fn = _PROVIDER_STREAM_MAP.get(current_provider)
        if fn is None:
            errors.append(f"{current_provider}: unsupported provider")
            continue

        model_for_provider = (
            _model_for_provider(current_provider, requested_provider, model)
            or (
                _configured_model_override()
                if current_provider == requested_provider and _configured_provider_override() == requested_provider
                else None
            )
            or _provider_default_model(current_provider, use_case)
        )
        resolved_temperature = temperature if temperature is not None else _default_temperature()
        resolved_max_tokens = max_tokens or _default_max_tokens()

        _log_request(
            current_provider,
            model_for_provider,
            normalized_messages,
            resolved_temperature,
            resolved_max_tokens,
        )

        chunks: List[str] = []
        try:
            async for token in fn(
                normalized_messages,
                model_for_provider,
                resolved_temperature,
                resolved_max_tokens,
            ):
                if token:
                    chunks.append(token)
                    yield token

            text = "".join(chunks).strip()
            if text:
                _log_response(current_provider, model_for_provider, text)
                return

            warning = f"{current_provider}: empty response"
            logger.warning("AI provider returned no content provider=%s model=%s", current_provider, model_for_provider)
            errors.append(warning)
        except Exception as exc:
            _log_failure(current_provider, model_for_provider, exc)
            _temporarily_disable_provider(current_provider, exc)
            errors.append(f"{current_provider}: {exc}")
            if chunks:
                partial = "".join(chunks).strip()
                if partial:
                    logger.warning(
                        "Discarding partial AI response after provider failure provider=%s model=%s chars=%s",
                        current_provider,
                        model_for_provider,
                        len(partial),
                    )
                    raise RuntimeError(
                        f"Provider '{current_provider}' failed after a partial response; refusing to return an incomplete answer"
                    ) from exc

        if provider:
            break

    raise RuntimeError("All configured AI providers failed or returned empty responses: " + "; ".join(errors))


async def _complete_non_stream(
    messages: List[Dict[str, str]],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    use_case: Optional[str] = None,
) -> str:
    normalized_messages = _normalize_messages(messages)
    if not normalized_messages:
        raise RuntimeError("No valid messages were provided to the AI service")

    ready_chain = _ready_provider_chain(provider, use_case=use_case)
    if not ready_chain:
        if provider:
            if _provider_temporarily_disabled(provider):
                raise RuntimeError(f"Provider temporarily unavailable: {provider}")
            raise RuntimeError(f"Provider not configured: {provider}")
        logger.warning("No configured AI providers were available")
        return _OFFLINE_TEXT

    requested_provider = (provider or _configured_provider_override() or _resolve_provider()).lower().strip()
    errors: List[str] = []

    for current_provider in ready_chain:
        fn = _PROVIDER_STREAM_MAP.get(current_provider)
        if fn is None:
            errors.append(f"{current_provider}: unsupported provider")
            continue

        model_for_provider = (
            _model_for_provider(current_provider, requested_provider, model)
            or (
                _configured_model_override()
                if current_provider == requested_provider and _configured_provider_override() == requested_provider
                else None
            )
            or _provider_default_model(current_provider, use_case)
        )
        resolved_temperature = temperature if temperature is not None else _default_temperature()
        resolved_max_tokens = max_tokens or _default_max_tokens()

        _log_request(
            current_provider,
            model_for_provider,
            normalized_messages,
            resolved_temperature,
            resolved_max_tokens,
        )

        chunks: List[str] = []
        try:
            async for token in fn(
                normalized_messages,
                model_for_provider,
                resolved_temperature,
                resolved_max_tokens,
            ):
                if token:
                    chunks.append(token)

            text = "".join(chunks).strip()
            if text:
                _log_response(current_provider, model_for_provider, text)
                return text

            warning = f"{current_provider}: empty response"
            logger.warning(
                "AI provider returned no content in buffered completion provider=%s model=%s",
                current_provider,
                model_for_provider,
            )
            errors.append(warning)
        except Exception as exc:
            _log_failure(current_provider, model_for_provider, exc)
            _temporarily_disable_provider(current_provider, exc)
            errors.append(f"{current_provider}: {exc}")
            partial = "".join(chunks).strip()
            if partial:
                logger.warning(
                    "Discarding partial buffered AI response after provider failure provider=%s model=%s chars=%s",
                    current_provider,
                    model_for_provider,
                    len(partial),
                )
                if provider:
                    raise RuntimeError(
                        f"Provider '{current_provider}' failed after a partial response; refusing to return an incomplete answer"
                    ) from exc

        if provider:
            break

    raise RuntimeError("All configured AI providers failed or returned empty responses: " + "; ".join(errors))


class AIService:
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        provider: Optional[str] = None,
        use_case: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        if stream:
            async for token in _stream_with_fallback(messages, provider, model, temperature, max_tokens, use_case=use_case):
                yield token
        else:
            result = await _complete_non_stream(messages, provider, model, temperature, max_tokens, use_case=use_case)
            yield result

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_case: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        async for token in _stream_with_fallback(messages, provider, model, temperature, max_tokens, use_case=use_case):
            yield token

    async def generate_code(
        self,
        prompt: str,
        language: str = "python",
        sample_input: str = "",
    ) -> str:
        sample_text = " ".join((sample_input or "").split()).strip()
        sample_guidance = (
            f"Use this sample input or runtime scenario when you describe the output:\n{sample_text}"
            if sample_text
            else (
                "If the task needs input, invent one tiny representative example before you show the expected output. "
                "If the task does not need input, show the normal output directly."
            )
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are NOVA AI's Codex-grade programming engine. Generate clean, accurate, production-ready, runnable "
                    f"{language} code. Do not invent APIs or library behavior. If there is an obvious bug, edge case, or better practical approach, handle it proactively.\n\n"
                    "Return markdown with exactly these sections:\n"
                    "## Summary\n"
                    "A short explanation of what the solution does.\n"
                    f"## Code\n```{language}\n...\n```\n"
                    "## Output\n"
                    "Show the expected output in a fenced text block.\n"
                    "## Notes\n"
                    "Use short flat bullets for assumptions, setup, or edge cases.\n\n"
                    f"{sample_guidance}"
                ),
            },
            {"role": "user", "content": prompt},
        ]
        return await _complete_non_stream(messages, use_case="coding")

    async def explain_code(
        self,
        code: str,
        language: str = "python",
        sample_input: str = "",
    ) -> str:
        sample_text = " ".join((sample_input or "").split()).strip()
        sample_guidance = (
            f"Use this sample input or runtime scenario when you describe the output:\n{sample_text}"
            if sample_text
            else (
                "If the code needs input, create one tiny representative example before you describe the output. "
                "If it does not need input, show the normal output directly."
            )
        )
        messages = [
            {
                "role": "system",
                "content": _with_presentation_style(
                    "You are NOVA AI's senior coding copilot. Explain the code clearly, "
                    "step by step, call out important edge cases, and say when any behavior depends on external context.\n\n"
                    "Return markdown with exactly these sections:\n"
                    "## Summary\n"
                    "## Explanation\n"
                    "## Output\n"
                    "Use a fenced text block for the expected output.\n"
                    "## Key points\n"
                    "Use short flat bullets.\n\n"
                    f"{sample_guidance}"
                ),
            },
            {"role": "user", "content": f"Explain this {language} code:\n\n{code}"},
        ]
        return await _complete_non_stream(messages, use_case="coding")

    async def debug_code(
        self,
        code: str,
        language: str = "python",
        error: str = "",
        sample_input: str = "",
    ) -> str:
        prompt = f"Debug this {language} code:\n\n{code}"
        if error:
            prompt += f"\n\nError message:\n{error}"
        sample_text = " ".join((sample_input or "").split()).strip()
        if sample_text:
            prompt += f"\n\nSample input or runtime scenario:\n{sample_text}"
        messages = [
            {
                "role": "system",
                "content": _with_presentation_style(
                    f"You are NOVA AI's Codex-grade {language} debugger. Identify the real issue, avoid guessing, "
                    "and provide the most reliable corrected solution with a concise explanation.\n\n"
                    "Return markdown with exactly these sections:\n"
                    "## Root cause\n"
                    f"## Fixed code\n```{language}\n...\n```\n"
                    "## Output\n"
                    "Use a fenced text block for the expected output after the fix.\n"
                    "## Fix notes\n"
                    "Use short flat bullets for the main changes."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        return await _complete_non_stream(messages, use_case="coding")

    async def optimize_code(
        self,
        code: str,
        language: str = "python",
        sample_input: str = "",
    ) -> str:
        sample_text = " ".join((sample_input or "").split()).strip()
        sample_guidance = (
            f"Use this sample input or runtime scenario when you describe the output:\n{sample_text}"
            if sample_text
            else (
                "If the code needs input, create one tiny representative example before you describe the output. "
                "If it does not need input, show the normal output directly."
            )
        )
        messages = [
            {
                "role": "system",
                "content": _with_presentation_style(
                    f"You are NOVA AI's {language} optimization specialist. Suggest accurate, justified "
                    "performance improvements, prefer practical wins, and avoid speculative claims.\n\n"
                    "Return markdown with exactly these sections:\n"
                    "## Summary\n"
                    f"## Improved code\n```{language}\n...\n```\n"
                    "## Output\n"
                    "Use a fenced text block for the expected output.\n"
                    "## Improvements\n"
                    "Use short flat bullets for the main gains.\n\n"
                    f"{sample_guidance}"
                ),
            },
            {"role": "user", "content": f"Optimize this code:\n\n{code}"},
        ]
        return await _complete_non_stream(messages, use_case="coding")

    async def generate_explanation(
        self,
        prompt: str,
        mode: str = "deep",
        audience: str = "general",
        detail: str = "detailed",
    ) -> str:
        mode = (mode or "deep").lower()
        audience = (audience or "general").lower()
        detail = (detail or "detailed").lower()

        if mode == "safe":
            system = _with_presentation_style(
                "You are NOVA AI's Safe Reasoning assistant. Provide a structured answer with the sections "
                "Answer, Safety Notes, and Next Steps. If you are unsure, say so. Be calm, supportive, and friendly."
            )
        elif mode == "knowledge":
            system = _with_presentation_style(
                "You are NOVA AI's Knowledge Assistant. Provide a concise, factual answer and distinguish "
                "clearly between facts and uncertainty. Keep the tone warm and approachable."
            )
        elif mode == "summary":
            system = _with_presentation_style(
                "You are NOVA AI's Summarizer. Provide a clear summary with key points only, using a warm and friendly tone."
            )
        else:
            system = _with_presentation_style(
                "You are NOVA AI's Deep Explanation Engine. Explain step by step with clear logic, "
                "but do not invent missing facts. Be warm and friendly, like a supportive friend."
            )

        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"Audience: {audience}\nDetail Level: {detail}\nRequest: {prompt}",
            },
        ]
        use_case = "writing" if mode == "summary" else infer_use_case(mode, prompt)
        return await _complete_non_stream(messages, use_case=use_case)

    async def summarize_document(self, text: str) -> str:
        messages = [
            {
                "role": "system",
                "content": _with_presentation_style(
                    "You are an expert at summarizing documents. Summarize only what is supported by the text "
                    "and do not add unsupported claims."
                ),
            },
            {"role": "user", "content": f"Summarize this document:\n\n{str(text)[:8000]}"},
        ]
        return await _complete_non_stream(messages, use_case="document")

    async def answer_question_from_document(
        self,
        question: str,
        context: str,
        max_context_chars: int = 20000,
    ) -> str:
        question_text = " ".join((question or "").split())
        contextual_instructions = contextual_system_instructions("documents", question_text)

        messages = [
            {
                "role": "system",
                "content": _with_presentation_style(
                    "Answer questions only from the provided context. Use simple, clear language by default. "
                    "Start with the direct answer. Prefer short paragraphs or bullets when that makes the answer easier "
                    "to understand. If the user asks for a process, explanation, or workflow, explain it step by step. "
                    "If the answer is not in the context, say \"I don't know based on the provided document.\""
                ),
            },
            *[
                {"role": "system", "content": instruction}
                for instruction in contextual_instructions
            ],
            {"role": "user", "content": f"Context:\n{str(context)[:max_context_chars]}\n\nQuestion: {question}"},
        ]
        return await _complete_non_stream(
            messages,
            max_tokens=_document_answer_max_tokens(question_text),
            use_case="document",
        )

    async def rewrite_document_question(self, question: str) -> str:
        question_text = " ".join((question or "").split()).strip()
        if not question_text:
            return ""

        messages = [
            {
                "role": "system",
                "content": _with_presentation_style(
                    "Rewrite the user's academic or document question into one clearer, more polished question. "
                    "Preserve the original meaning, technical terms, marks, and any instructions about tables, "
                    "diagrams, simplicity, or comparison format. Return only the rewritten question with no intro, "
                    "no bullets, and no extra explanation."
                ),
            },
            {"role": "user", "content": question_text},
        ]
        rewritten = await _complete_non_stream(
            messages,
            max_tokens=max(256, min(_default_max_tokens(), 512)),
            use_case="writing",
        )
        return " ".join((rewritten or "").split()).strip(" '\"")

    async def enhance_image_prompt(
        self,
        prompt: str,
        *,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid",
        provider: Optional[str] = None,
        prompt_target: str = "auto",
    ) -> str:
        cleaned_prompt = _clean_image_prompt(prompt, 2400)
        if not cleaned_prompt:
            return ""

        fallback_prompt = _heuristic_image_prompt(
            cleaned_prompt,
            size=size,
            quality=quality,
            style=style,
        )
        enhancer_provider = _resolve_prompt_enhancer_provider(provider)
        if not enhancer_provider:
            return fallback_prompt

        target = _normalize_image_prompt_target(prompt_target)
        messages = [
            {
                "role": "system",
                "content": _with_presentation_style(
                    "Rewrite the user's image idea into one strong, production-ready image prompt. "
                    "Preserve the user's subject, count, mood, requested text, brand names, and intent. "
                    "Add concrete composition, lighting, background, materials, and camera cues only when helpful. "
                    "Avoid adding captions, logos, watermarks, or extra objects unless the user explicitly asked for them. "
                    "Return only the final prompt with no bullets, no title, and no explanation. "
                    f"{_IMAGE_PROMPT_TARGET_GUIDANCE.get(target, _IMAGE_PROMPT_TARGET_GUIDANCE['auto'])} "
                    f"The output should fit a {_image_size_to_aspect_ratio(size)} composition and reflect a {style} style with {quality} quality."
                ),
            },
            {"role": "user", "content": cleaned_prompt},
        ]

        try:
            rewritten = await _complete_non_stream(
                messages,
                provider=enhancer_provider,
                temperature=0.4,
                max_tokens=max(256, min(_default_max_tokens(), 450)),
                use_case="image_prompting",
            )
            normalized = _clean_image_prompt(str(rewritten or "").strip(" '\""), 2400)
            return normalized or fallback_prompt
        except Exception as exc:
            logger.warning(
                "Image prompt enhancement failed provider=%s prompt=%s error=%s",
                enhancer_provider,
                cleaned_prompt[:180],
                exc,
            )
            return fallback_prompt

    async def generate_image_result(
        self,
        prompt: str,
        *,
        size: str = "1024x1024",
        n: int = 1,
        quality: str = "standard",
        style: str = "vivid",
        provider: Optional[str] = None,
        enhance_prompt: bool = True,
        prompt_target: str = "auto",
        raise_on_error: bool = False,
    ) -> Dict[str, Any]:
        cleaned_prompt = _clean_image_prompt(prompt)
        if not cleaned_prompt:
            return {
                "prompt": "",
                "revised_prompt": "",
                "provider": None,
                "provider_label": None,
                "images": [],
            }

        candidate_providers = _resolve_image_provider_chain(provider)
        resolved_provider = candidate_providers[0] if candidate_providers else None
        revised_prompt = cleaned_prompt
        if enhance_prompt:
            revised_prompt = await self.enhance_image_prompt(
                cleaned_prompt,
                size=size,
                quality=quality,
                style=style,
                provider=resolved_provider or provider,
                prompt_target=prompt_target,
            )

        generation_prompt = _image_generation_prompt_for_provider(
            revised_prompt or cleaned_prompt,
            provider=resolved_provider or "",
            size=size,
            quality=quality,
            style=style,
        )

        if not resolved_provider:
            logger.info("Image generation skipped because no available image provider is ready")
            return {
                "prompt": cleaned_prompt,
                "revised_prompt": revised_prompt or cleaned_prompt,
                "provider": None,
                "provider_label": None,
                "images": [],
            }

        last_error: Optional[Exception] = None
        provider_errors: List[tuple[str, Exception]] = []

        for candidate_provider in candidate_providers:
            generation_prompt = _image_generation_prompt_for_provider(
                revised_prompt or cleaned_prompt,
                provider=candidate_provider,
                size=size,
                quality=quality,
                style=style,
            )
            try:
                if candidate_provider == "google":
                    images = await _generate_image_with_google(generation_prompt, size=size, n=n)
                elif candidate_provider == "openrouter":
                    images = await _generate_image_with_openrouter(
                        generation_prompt,
                        size=size,
                        n=n,
                        quality=quality,
                    )
                else:
                    images = await _generate_image_with_openai(
                        generation_prompt,
                        size=size,
                        n=n,
                        quality=quality,
                        style=style,
                    )

                images = sanitize_image_assets(images, limit=n)
                if images:
                    return {
                        "prompt": cleaned_prompt,
                        "revised_prompt": revised_prompt or cleaned_prompt,
                        "provider": candidate_provider,
                        "provider_label": _IMAGE_PROVIDER_LABELS.get(candidate_provider, candidate_provider.title()),
                        "images": images,
                    }

                logger.warning(
                    "Image API returned no image data provider=%s prompt=%s",
                    candidate_provider,
                    generation_prompt[:180],
                )
            except Exception as exc:
                last_error = exc
                provider_errors.append((candidate_provider, exc))
                _temporarily_disable_image_provider(candidate_provider, exc)
                logger.warning(
                    "Image API failed provider=%s prompt=%s error=%s",
                    candidate_provider,
                    generation_prompt[:180],
                    exc,
                )

        if raise_on_error and last_error is not None:
            raise _build_image_provider_failure(provider_errors) from last_error

        return {
            "prompt": cleaned_prompt,
            "revised_prompt": revised_prompt or cleaned_prompt,
            "provider": resolved_provider,
            "provider_label": _IMAGE_PROVIDER_LABELS.get(resolved_provider, resolved_provider.title()) if resolved_provider else None,
            "images": [],
        }

    async def analyze_image(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        if not image_bytes:
            return ""

        cleaned_prompt = " ".join((prompt or "").split()).strip()
        effective_prompt = cleaned_prompt or "Describe this image clearly and answer the user's request."
        requested_provider = (provider or _resolve_provider()).lower().strip()
        candidate_providers = [requested_provider] + [
            item for item in ("openai", "google") if item != requested_provider
        ]

        last_error: Optional[Exception] = None
        for candidate_provider in candidate_providers:
            try:
                if candidate_provider == "openai":
                    answer = await _analyze_image_with_openai(
                        effective_prompt,
                        image_bytes,
                        mime_type=mime_type,
                        model=model if candidate_provider == requested_provider else None,
                        max_tokens=max_tokens,
                    )
                elif candidate_provider == "google":
                    answer = await _analyze_image_with_google(
                        effective_prompt,
                        image_bytes,
                        mime_type=mime_type,
                        model=model if candidate_provider == requested_provider else None,
                        max_tokens=max_tokens,
                    )
                else:
                    continue

                answer_text = str(answer or "").strip()
                if answer_text:
                    return answer_text
            except Exception as exc:
                last_error = exc
                _log_failure(candidate_provider, model, exc)

        if last_error is not None:
            raise RuntimeError(f"Image analysis failed: {last_error}") from last_error

        if provider:
            raise RuntimeError(f"Provider not configured for image analysis: {provider}")

        return _OFFLINE_TEXT

    async def generate_learning_roadmap(self, topic: str, level: str = "beginner") -> Dict:
        messages = [
            {
                "role": "system",
                "content": _with_presentation_style(
                    "You are an expert learning advisor. Create a structured roadmap with realistic milestones "
                    "and avoid unsupported claims about external resources."
                ),
            },
            {"role": "user", "content": f"Create a {level} learning roadmap for: {topic}"},
        ]
        roadmap = await _complete_non_stream(messages, use_case="concept")
        return {"topic": topic, "level": level, "roadmap": roadmap}

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
        quality: str = "standard",
        style: str = "vivid",
        provider: Optional[str] = None,
        enhance_prompt: bool = True,
        prompt_target: str = "auto",
    ) -> List[str]:
        result = await self.generate_image_result(
            prompt,
            size=size,
            n=n,
            quality=quality,
            style=style,
            provider=provider,
            enhance_prompt=enhance_prompt,
            prompt_target=prompt_target,
        )
        return list(result.get("images") or [])

    def has_available_text_provider(
        self,
        provider: Optional[str] = None,
        use_case: Optional[str] = None,
    ) -> bool:
        return any(_provider_available(candidate) for candidate in _provider_chain(provider, use_case=use_case))

    def get_runtime_capabilities(self) -> Dict[str, Any]:
        available_text_providers = [
            provider
            for provider in dict.fromkeys([*_provider_chain(None), *_FALLBACK_CHAIN])
            if _provider_available(provider)
        ]
        available_image_providers = [
            provider
            for provider in ("google", "openrouter", "openai")
            if _image_provider_available(provider)
        ]

        return {
            "configured_provider": _configured_provider_override() or "auto",
            "configured_model": _configured_model_override(),
            "text_ready": bool(available_text_providers),
            "available_text_providers": available_text_providers,
            "preferred_text_provider": available_text_providers[0] if available_text_providers else None,
            "image_ready": bool(available_image_providers),
            "available_image_providers": available_image_providers,
            "preferred_image_provider": available_image_providers[0] if available_image_providers else None,
        }

    def has_available_image_provider(self, provider: Optional[str] = None) -> bool:
        return bool(_resolve_image_provider_chain(provider))

    async def edit_image(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
        provider: Optional[str] = None,
    ) -> List[str]:
        cleaned_prompt = " ".join((prompt or "").split()).strip()[:4000]
        if not image_bytes:
            return []

        candidate_providers = _resolve_image_provider_chain(provider)
        if not candidate_providers:
            logger.info("Image editing skipped because no available image provider is ready")
            return []

        edit_prompt = cleaned_prompt or "Create a polished new image inspired by this upload."

        last_error: Optional[Exception] = None
        provider_errors: List[tuple[str, Exception]] = []

        for candidate_provider in candidate_providers:
            try:
                if candidate_provider == "google":
                    images = sanitize_image_assets(
                        await _edit_image_with_google(edit_prompt, image_bytes, mime_type=mime_type)
                    )
                elif candidate_provider == "openrouter":
                    images = sanitize_image_assets(
                        await _edit_image_with_openrouter(edit_prompt, image_bytes, mime_type=mime_type)
                    )
                else:
                    images = sanitize_image_assets(
                        await _edit_image_with_openai(edit_prompt, image_bytes)
                    )

                if images:
                    return images
                logger.warning("Image edit returned no data provider=%s prompt=%s", candidate_provider, edit_prompt[:180])
            except Exception as exc:
                last_error = exc
                provider_errors.append((candidate_provider, exc))
                _temporarily_disable_image_provider(candidate_provider, exc)
                logger.warning(
                    "Image edit failed provider=%s prompt=%s error=%s",
                    candidate_provider,
                    edit_prompt[:180],
                    exc,
                )
        if provider_errors:
            raise _build_image_provider_failure(provider_errors) from last_error
        return []

    async def get_available_image_providers(self) -> List[Dict[str, Any]]:
        providers: List[Dict[str, Any]] = [
            {
                "id": "auto",
                "name": "Auto",
                "available": bool(_resolve_image_provider()),
                "description": "Default image stack: Gemini first, then OpenRouter, then ChatGPT.",
            }
        ]

        providers.append(
            {
                "id": "google",
                "name": "Gemini",
                "available": _image_provider_available("google"),
                "description": "Default for image generation, search-backed prompts, and fast image work.",
            }
        )
        providers.append(
            {
                "id": "openrouter",
                "name": "OpenRouter",
                "available": _image_provider_available("openrouter"),
                "description": "Image fallback router using your OpenRouter credits and model access.",
            }
        )
        providers.append(
            {
                "id": "openai",
                "name": "ChatGPT",
                "available": _image_provider_available("openai"),
                "description": "Direct OpenAI image generation fallback.",
            }
        )
        return providers

    async def get_available_providers(self) -> List[Dict]:
        providers = []

        if _openai_api_key():
            openai_models = [
                getattr(settings, "OPENAI_FAST_MODEL", ""),
                getattr(settings, "OPENAI_CHAT_MODEL", ""),
                getattr(settings, "OPENAI_CODE_MODEL", ""),
                getattr(settings, "OPENAI_EXPLAIN_MODEL", ""),
            ]
            providers.append(
                {
                    "id": "openai",
                    "name": "ChatGPT",
                    "models": [model for model in dict.fromkeys(openai_models) if model] or ["gpt-4o"],
                    "recommended_for": ["Reasoning", "Coding", "Writing", "Strategy"],
                }
            )

        if getattr(settings, "ANTHROPIC_API_KEY", ""):
            anthropic_models = [
                getattr(settings, "ANTHROPIC_MODEL", ""),
                "claude-opus-4-5",
                "claude-sonnet-4-5",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ]
            providers.append(
                {
                    "id": "anthropic",
                    "name": "Claude",
                    "models": [model for model in dict.fromkeys(anthropic_models) if model],
                    "recommended_for": ["Long context", "Document analysis", "Calm reasoning"],
                }
            )

        if _google_api_key():
            google_models = [
                getattr(settings, "GEMINI_CHAT_MODEL", ""),
                "gemini-2.5-flash",
                "gemini-2.5-pro",
            ]
            providers.append(
                {
                    "id": "google",
                    "name": "Gemini",
                    "models": [model for model in dict.fromkeys(google_models) if model],
                    "recommended_for": ["Search-backed research", "Current information", "Multimodal"],
                }
            )

        if _deepseek_api_key():
            deepseek_models = [
                getattr(settings, "DEEPSEEK_MODEL", ""),
                "deepseek-chat",
                "deepseek-coder",
                "deepseek-reasoner",
            ]
            providers.append(
                {
                    "id": "deepseek",
                    "name": "DeepSeek",
                    "models": [model for model in dict.fromkeys(deepseek_models) if model],
                    "recommended_for": ["Coding", "Math", "Logic"],
                }
            )

        if getattr(settings, "GROQ_API_KEY", ""):
            groq_models = [
                getattr(settings, "GROQ_MODEL", ""),
                "llama-3.3-70b-versatile",
                "llama3-8b-8192",
                "mixtral-8x7b-32768",
                "gemma2-9b-it",
            ]
            providers.append(
                {
                    "id": "groq",
                    "name": "Groq",
                    "models": [model for model in dict.fromkeys(groq_models) if model],
                    "recommended_for": ["Ultra-fast replies"],
                }
            )

        providers.append(
            {
                "id": "ollama",
                "name": "Ollama (Local)",
                "models": ["llama3", "mistral", "codellama"],
                "recommended_for": ["Private local use", "Offline fallback"],
            }
        )
        return providers


ai_service = AIService()


def generate_response(message: str) -> str:
    cleaned = (message or "").strip()
    if not cleaned:
        return "NOVA AI: Ask me anything."
    return f"NOVA AI: {cleaned}"


async def stream_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    provider: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    use_case: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    async for token in _stream_with_fallback(messages, provider, model, temperature, max_tokens, use_case=use_case):
        yield token


def generate_image_url(prompt: str) -> str:
    from urllib.parse import quote

    def extract_context(raw_prompt: str) -> tuple[str, str]:
        source = str(raw_prompt or "").strip()
        user_match = re.search(r"User prompt:\s*(.*?)(?:\nAssistant answer:|\Z)", source, re.S | re.I)
        answer_match = re.search(r"Assistant answer:\s*(.*?)(?:\nWeb grounding for accuracy:|\Z)", source, re.S | re.I)
        user_prompt = (user_match.group(1).strip() if user_match else "").strip()
        answer = (answer_match.group(1).strip() if answer_match else "").strip()
        if not user_prompt and not answer:
            source = re.sub(r"Create .*?visual .*?(?:\n|$)", "", source, flags=re.I | re.S)
            source = re.sub(r"Prefer .*?concept\.\s*", "", source, flags=re.I | re.S)
            source = re.sub(r"Web grounding for accuracy:.*\Z", "", source, flags=re.I | re.S)
            user_prompt = source.strip()
        return user_prompt, answer

    def short_text(value: str, limit: int) -> str:
        cleaned = " ".join((value or "").split()).strip()
        return cleaned[:limit].strip()

    def wrap_text(value: str, max_chars: int, max_lines: int = 3) -> List[str]:
        words = short_text(value, 240).split()
        if not words:
            return []

        lines: List[str] = []
        current = words[0]
        for word in words[1:]:
            if len(current) + 1 + len(word) <= max_chars:
                current = f"{current} {word}"
            else:
                lines.append(current)
                current = word
                if len(lines) >= max_lines - 1:
                    break
        if current and len(lines) < max_lines:
                lines.append(current)
        return lines[:max_lines]

    def extract_topics(question: str) -> List[str]:
        cleaned = short_text(question, 180)
        if not cleaned:
            return []

        cleaned = re.sub(
            r"\b(explain|what is|what are|how does|how do|how is|how are|tell me about|difference between|compare|between|show me|diagram of)\b",
            "",
            cleaned,
            flags=re.I,
        )
        cleaned = re.sub(r"\b(work|works|working|function|functions|overview|basics|concept)\b", "", cleaned, flags=re.I)
        parts = re.split(r"\s*(?:,|/|\band\b|\bvs\.?\b|\bversus\b)\s*", cleaned, flags=re.I)
        topics: List[str] = []
        for part in parts:
            candidate = short_text(re.sub(r"[?!.]", "", part), 30)
            if len(candidate) < 2:
                continue
            if candidate.lower() in {"the", "a", "an", "of", "for"}:
                continue
            topics.append(candidate)
        return list(dict.fromkeys(topics))[:4]

    def extract_items(text: str) -> List[str]:
        source = str(text or "").strip()
        if not source:
            return []

        table_rows = []
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.count("|") < 2:
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if not cells or all(re.fullmatch(r"[-: ]+", cell or "") for cell in cells):
                continue
            table_rows.append(cells)
        if len(table_rows) >= 2:
            headers = table_rows[0]
            summaries: List[str] = []
            for row in table_rows[1:6]:
                pairs = [
                    f"{headers[index]}: {row[index]}"
                    for index in range(min(len(headers), len(row)))
                    if headers[index] and row[index]
                ]
                candidate = short_text("; ".join(pairs[:3]), 96)
                if candidate:
                    summaries.append(candidate)
            if summaries:
                return summaries[:5]

        bullet_items = [
            short_text(re.sub(r"^[-*0-9.\s]+", "", line), 90)
            for line in source.splitlines()
            if line.strip().startswith(("-", "*")) or re.match(r"^\d+[.)]\s", line.strip())
        ]
        bullet_items = [item for item in bullet_items if item]
        if bullet_items:
            return bullet_items[:5]

        sentence_items = []
        for sentence in re.split(r"(?<=[.!?])\s+", source):
            candidate = short_text(sentence, 90)
            if len(candidate) < 14:
                continue
            sentence_items.append(candidate)
        return sentence_items[:5]

    def topic_points(topics: List[str], items: List[str]) -> List[str]:
        if not topics:
            return items[:4]

        matched: List[str] = []
        lowered_items = [item.lower() for item in items]
        used_indexes: set[int] = set()
        for topic in topics:
            topic_key = topic.lower()
            match_index = next(
                (index for index, item in enumerate(lowered_items) if topic_key in item and index not in used_indexes),
                None,
            )
            if match_index is None:
                match_index = next((index for index in range(len(items)) if index not in used_indexes), None)
            if match_index is not None:
                used_indexes.add(match_index)
                matched.append(items[match_index])
        return matched[: max(1, min(len(topics), 4))]

    def extract_dates(text: str) -> List[str]:
        matches = re.findall(
            r"\b(?:\d{4}|\d{3}s|\d{2}(?:st|nd|rd|th)\s+century|ancient|medieval|modern)\b",
            text or "",
            flags=re.I,
        )
        dates: List[str] = []
        seen: set[str] = set()
        for value in matches:
            normalized = value.strip()
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            dates.append(normalized)
        return dates[:4]

    def detect_style(question: str, answer_text: str, topics: List[str], items: List[str]) -> str:
        combined = f"{question} {answer_text}".lower()
        if re.search(r"^\s*\|.+\|\s*$", answer_text or "", re.M):
            return "comparison"
        if re.search(r"\b(compare|comparison|difference|vs|versus|distinguish)\b", combined) and len(topics) >= 2:
            return "comparison"
        if len(topics) >= 2 and re.search(r"\b(and|vs|versus)\b", question.lower()) and not re.search(
            r"\b(cycle|phase|timeline|history|process|workflow|steps?)\b",
            combined,
        ):
            return "comparison"
        if re.search(r"\b(timeline|history|historical|evolution|chronology|progression)\b", combined) or extract_dates(combined):
            return "timeline"
        if re.search(r"\b(cycle|life cycle|lifecycle|phase|stages?)\b", combined):
            return "cycle"
        if re.search(r"\b(network|internet|client|server|router|request|response|database|api)\b", combined):
            return "network"
        if re.search(r"\b(layer|layers|architecture|structure|components?|parts?|types?|stack)\b", combined):
            return "hierarchy"
        if re.search(r"\b(how|process|workflow|works|working|steps?|flow|pipeline)\b", combined) and len(items) >= 3:
            return "process"
        if len(topics) >= 3:
            return "concept"
        return "concept"

    def detect_domain(question: str, answer_text: str) -> str:
        combined = f"{question} {answer_text}".lower()
        if re.search(
            r"\b(ram|rom|cpu|gpu|cache|memory|storage|disk|kernel|database|server|client|network|api|http|tcp|udp|os|operating system|algorithm|compiler|pipeline|router)\b",
            combined,
        ):
            return "technology"
        if re.search(
            r"\b(cell|heart|brain|photosynthesis|ecosystem|dna|protein|atom|molecule|respiration|blood|plant|animal|organ|nucleus)\b",
            combined,
        ):
            return "science"
        if re.search(r"\b(history|empire|war|revolution|century|medieval|ancient|modern|dynasty|timeline)\b", combined):
            return "history"
        if re.search(r"\b(market|business|finance|revenue|profit|supply|demand|inflation|economy|sales)\b", combined):
            return "business"
        return "general"

    def build_theme(style: str, domain: str) -> Dict[str, object]:
        return {
            "bg_start": "#ffffff",
            "bg_end": "#ffffff",
            "glow": "#ffffff",
            "label": "#1d4ed8",
            "title": "#111827",
            "subtitle": "#6b7280",
            "body": "#374151",
            "footer": "#6b7280",
            "panel_fill": "#ffffff",
            "panel_stroke": "#9ca3af",
            "frame_stroke": "#d1d5db",
            "connector": "#6b7280",
            "pattern": "none",
            "pattern_color": "#ffffff",
            "colors": ["#1d4ed8", "#6b7280", "#111827", "#9ca3af"],
        }

    def multiline_text(
        x: int,
        y: int,
        lines: List[str],
        *,
        font_size: int,
        fill: str,
        weight: str = "400",
        anchor: str = "start",
    ) -> str:
        content = [escape(line) for line in lines if line]
        if not content:
            return ""
        line_height = int(font_size * 1.32)
        spans = "".join(
            f"<tspan x='{x}' dy='{0 if index == 0 else line_height}'>{line}</tspan>"
            for index, line in enumerate(content)
        )
        return (
            f"<text x='{x}' y='{y}' font-size='{font_size}' fill='{fill}' text-anchor='{anchor}' "
            f"font-weight='{weight}' font-family='Segoe UI, Arial, sans-serif'>{spans}</text>"
        )

    def background_pattern() -> str:
        return ""

    def background_overlay() -> str:
        return ""

    def render_header(title_lines: List[str], subtitle_lines: List[str], label: str) -> str:
        return (
            f"<text x='512' y='86' font-size='18' fill='{theme['label']}' text-anchor='middle' font-family='Arial, Helvetica, sans-serif'>"
            f"{escape(label)}</text>"
            + multiline_text(512, 132, title_lines[:2] or ["Diagram"], font_size=34, fill=str(theme["title"]), weight="600", anchor="middle")
        )

    def panel(x: int, y: int, width: int, height: int, title: str, body: str, accent: str) -> str:
        title_lines = wrap_text(title, 18, 2)
        body_lines = wrap_text(body, 24, 4)
        return (
            "<g>"
            f"<rect x='{x}' y='{y}' width='{width}' height='{height}' rx='2' fill='{theme['panel_fill']}' stroke='{accent}' stroke-width='1.8'/>"
            + multiline_text(x + 22, y + 42, title_lines, font_size=22, fill=str(theme["title"]), weight="600")
            + multiline_text(x + 22, y + 90, body_lines, font_size=18, fill=str(theme["body"]))
            + "</g>"
        )

    def render_comparison(topics: List[str], mapped_points: List[str]) -> str:
        colors = list(theme["colors"])
        cards = []
        count = max(2, min(len(topics), 4))
        gap = 22
        total_width = 884
        column_width = int((total_width - ((count - 1) * gap)) / count)
        start_x = int((1024 - ((count * column_width) + ((count - 1) * gap))) / 2)
        for index, topic in enumerate(topics[:count]):
            cards.append(
                panel(
                    start_x + index * (column_width + gap),
                    306,
                    column_width,
                    430,
                    topic,
                    mapped_points[index] if index < len(mapped_points) else "Key traits from the answer.",
                    colors[index % len(colors)],
                )
            )
        return "".join(cards)

    def render_process(items: List[str]) -> str:
        colors = list(theme["colors"])
        count = max(3, min(len(items), 4))
        gap = 24
        node_width = 180
        total_width = (count * node_width) + ((count - 1) * gap)
        start_x = int((1024 - total_width) / 2)
        node_positions = [(start_x + index * (node_width + gap), 404) for index in range(count)]
        nodes = []
        arrows = []
        for index, (x, y) in enumerate(node_positions):
            body = items[index] if index < len(items) else "Key step"
            nodes.append(panel(x, y, node_width, 210, f"Step {index + 1}", body, colors[index % len(colors)]))
            if index < len(node_positions) - 1:
                arrows.append(
                    f"<line x1='{x + node_width}' y1='{y + 105}' x2='{node_positions[index + 1][0] - 18}' y2='{y + 105}' "
                    f"stroke='{theme['connector']}' stroke-width='2' stroke-linecap='round'/>"
                    f"<polygon points='{node_positions[index + 1][0] - 18},{y + 92} {node_positions[index + 1][0] - 18},{y + 118} {node_positions[index + 1][0] + 6},{y + 105}' "
                    f"fill='{theme['label']}'/>"
                )
        return "".join(arrows + nodes)

    def render_hierarchy(items: List[str]) -> str:
        widths = [660, 570, 480, 390]
        y_positions = [302, 434, 566, 698]
        colors = list(theme["colors"])
        blocks = []
        for index, y in enumerate(y_positions):
            width = widths[index]
            x = int((1024 - width) / 2)
            body = items[index] if index < len(items) else "Layer summary"
            blocks.append(panel(x, y, width, 96, f"Layer {index + 1}", body, colors[index % len(colors)]))
        connectors = "".join(
            f"<line x1='512' y1='{396 + (index * 132)}' x2='512' y2='{428 + (index * 132)}' stroke='{theme['connector']}' stroke-width='2' stroke-linecap='round'/>"
            for index in range(3)
        )
        return connectors + "".join(blocks)

    def render_cycle(items: List[str]) -> str:
        positions = [(512, 332), (760, 512), (512, 712), (264, 512)]
        colors = list(theme["colors"])
        nodes = []
        arrows = [
            f"<path d='M 585 356 C 660 392 704 432 734 478' fill='none' stroke='{theme['connector']}' stroke-width='2' stroke-linecap='round'/>",
            f"<path d='M 736 584 C 702 652 650 694 582 724' fill='none' stroke='{theme['connector']}' stroke-width='2' stroke-linecap='round'/>",
            f"<path d='M 438 724 C 370 694 318 652 286 584' fill='none' stroke='{theme['connector']}' stroke-width='2' stroke-linecap='round'/>",
            f"<path d='M 288 478 C 320 412 370 370 438 340' fill='none' stroke='{theme['connector']}' stroke-width='2' stroke-linecap='round'/>",
        ]
        for index, (x, y) in enumerate(positions):
            title = f"Stage {index + 1}"
            body_lines = wrap_text(items[index] if index < len(items) else "Cycle point", 16, 3)
            nodes.append(
                "<g>"
                f"<rect x='{x - 104}' y='{y - 74}' width='208' height='148' rx='2' fill='{theme['panel_fill']}' stroke='{colors[index % len(colors)]}' stroke-width='1.8'/>"
                + multiline_text(x, y - 24, [title], font_size=22, fill=str(theme["title"]), weight="600", anchor="middle")
                + multiline_text(x, y + 12, body_lines, font_size=18, fill=str(theme["body"]), anchor="middle")
                + "</g>"
            )
        return "".join(arrows + nodes)

    def render_timeline(items: List[str], dates: List[str]) -> str:
        colors = list(theme["colors"])
        count = max(3, min(len(items), 4))
        centers = [152, 392, 632, 872][:count]
        cards = []
        connectors = [
            f"<line x1='{centers[0]}' y1='520' x2='{centers[-1]}' y2='520' stroke='{theme['connector']}' stroke-width='2' stroke-linecap='round'/>"
        ]
        for index, center_x in enumerate(centers):
            top = index % 2 == 0
            card_y = 304 if top else 566
            marker_y = 520
            cards.append(
                f"<line x1='{center_x}' y1='{marker_y}' x2='{center_x}' y2='{card_y + (210 if top else 0)}' stroke='{theme['connector']}' stroke-width='2' stroke-linecap='round'/>"
                f"<circle cx='{center_x}' cy='{marker_y}' r='9' fill='{colors[index % len(colors)]}'/>"
            )
            label = dates[index] if index < len(dates) else f"Stage {index + 1}"
            cards.append(panel(center_x - 92, card_y, 184, 210, label, items[index], colors[index % len(colors)]))
        return "".join(connectors + cards)

    def render_network(topics: List[str], mapped_points: List[str], title_text: str) -> str:
        colors = list(theme["colors"])
        center_title = short_text(title_text, 34) or "System"
        nodes = [
            "<g>"
            f"<rect x='372' y='420' width='280' height='188' rx='2' fill='{theme['panel_fill']}' stroke='{theme['label']}' stroke-width='1.8'/>"
            + multiline_text(512, 488, wrap_text(center_title, 18, 2), font_size=26, fill=str(theme["title"]), weight="600", anchor="middle")
            + multiline_text(512, 544, ["Main system"], font_size=18, fill=str(theme["subtitle"]), anchor="middle")
            + "</g>"
        ]
        positions = [(100, 278), (744, 278), (100, 650), (744, 650)]
        for index, (x, y) in enumerate(positions[: max(2, min(len(topics) or 3, 4))]):
            topic = topics[index] if index < len(topics) else f"Node {index + 1}"
            body = mapped_points[index] if index < len(mapped_points) else "Connected concept"
            nodes.append(
                f"<line x1='512' y1='514' x2='{x + 140}' y2='{y + 88}' stroke='{theme['connector']}' stroke-width='2' stroke-linecap='round'/>"
            )
            nodes.append(panel(x, y, 280, 176, topic, body, colors[index % len(colors)]))
        return "".join(nodes)

    def render_concept(topics: List[str], mapped_points: List[str], title_text: str) -> str:
        positions = [(236, 356), (788, 356), (236, 676), (788, 676)]
        colors = list(theme["colors"])
        nodes = [
            "<g>"
            f"<rect x='362' y='432' width='300' height='164' rx='2' fill='{theme['panel_fill']}' stroke='{theme['label']}' stroke-width='1.8'/>"
            + multiline_text(512, 492, wrap_text(title_text, 18, 3), font_size=26, fill=str(theme["title"]), weight="600", anchor="middle")
            + "</g>"
        ]
        connectors = []
        for index, (x, y) in enumerate(positions[: max(2, min(len(topics) or 3, 4))]):
            topic = topics[index] if index < len(topics) else f"Concept {index + 1}"
            body = mapped_points[index] if index < len(mapped_points) else "Key point"
            connectors.append(
                f"<line x1='512' y1='514' x2='{x}' y2='{y}' stroke='{theme['connector']}' stroke-width='2' stroke-linecap='round'/>"
            )
            nodes.append(
                "<g>"
                f"<rect x='{x - 118}' y='{y - 74}' width='236' height='148' rx='2' fill='{theme['panel_fill']}' stroke='{colors[index % len(colors)]}' stroke-width='1.8'/>"
                + multiline_text(x, y - 18, wrap_text(topic, 14, 2), font_size=22, fill=str(theme["title"]), weight="600", anchor="middle")
                + multiline_text(x, y + 18, wrap_text(body, 16, 3), font_size=18, fill=str(theme["body"]), anchor="middle")
                + "</g>"
            )
        return "".join(connectors + nodes)

    user_prompt, answer = extract_context(prompt)
    title_source = user_prompt or answer or "NOVA AI"
    title = short_text(title_source, 52) or "NOVA AI"
    topics = extract_topics(user_prompt or title_source)
    items = extract_items(answer or user_prompt)
    mapped_points = topic_points(topics, items)
    style = detect_style(user_prompt, answer, topics, items)
    dates = extract_dates(f"{user_prompt} {answer}")
    theme = build_theme(style, "general")
    header = render_header(
        wrap_text(title, 22, 2),
        wrap_text(short_text(user_prompt or answer, 120), 42, 2),
        f"{style.title()}",
    )

    if style == "comparison" and len(topics) >= 2:
        body = render_comparison(topics[:4], mapped_points)
    elif style == "timeline" and items:
        body = render_timeline(items[:4], dates)
    elif style == "process" and items:
        body = render_process(items[:4])
    elif style == "hierarchy" and items:
        body = render_hierarchy(items[:4])
    elif style == "cycle" and items:
        body = render_cycle((items + items)[:4])
    elif style == "network":
        body = render_network(topics[:4], mapped_points[:4] or items[:4], title)
    else:
        body = render_concept(topics[:4], mapped_points[:4] or items[:4], title)

    footer = ""

    svg = "".join(
        [
            "<svg xmlns='http://www.w3.org/2000/svg' width='1024' height='1024'>",
            "<rect width='100%' height='100%' fill='#ffffff'/>",
            f"<rect x='42' y='42' width='940' height='940' rx='2' fill='none' stroke='{theme['frame_stroke']}' stroke-width='1.5'/>",
            header,
            body,
            footer,
            "</svg>",
        ]
    )
    return f"data:image/svg+xml;utf8,{quote(svg)}"
