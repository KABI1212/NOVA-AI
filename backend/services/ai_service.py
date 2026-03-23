"""
ai_service.py - NOVA AI multi-provider chat service
Provides consistent message formatting, logging, low-temperature generation,
provider fallback, and safer empty-response handling.
"""

from __future__ import annotations

import json
import logging
import re
from typing import AsyncGenerator, Dict, List, Optional
from xml.sax.saxutils import escape

import httpx

from config.settings import settings


logger = logging.getLogger(__name__)

_OFFLINE_TEXT = (
    "NOVA AI is running in offline mode. "
    "Configure an AI provider (OPENAI_API_KEY / DEEPSEEK_API_KEY / "
    "GOOGLE_API_KEY / GROQ_API_KEY / ANTHROPIC_API_KEY) "
    "or start Ollama (ollama serve)."
)

_DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
_DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
_DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
_DEFAULT_OLLAMA_MODEL = "llama3"

_FALLBACK_CHAIN = ["openai", "deepseek", "google", "groq", "anthropic", "ollama"]
_VALID_ROLES = {"system", "user", "assistant"}


def _should_log_debug() -> bool:
    return bool(getattr(settings, "AI_DEBUG_LOGGING", False) or getattr(settings, "DEBUG", False))


def _request_timeout_seconds() -> int:
    return max(10, int(getattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 60) or 60))


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


def _resolve_provider() -> str:
    configured = (getattr(settings, "AI_PROVIDER", "") or "").lower().strip()
    if configured:
        return configured
    if _openai_api_key():
        return "openai"
    if _deepseek_api_key():
        return "deepseek"
    if _google_api_key():
        return "google"
    if getattr(settings, "GROQ_API_KEY", ""):
        return "groq"
    if getattr(settings, "ANTHROPIC_API_KEY", ""):
        return "anthropic"
    return "ollama"


def _google_api_key() -> str:
    return getattr(settings, "GOOGLE_API_KEY", "") or getattr(settings, "GEMINI_API_KEY", "") or ""


def _openai_api_key() -> str:
    return getattr(settings, "OPENAI_API_KEY", "") or ""


def _deepseek_api_key() -> str:
    return getattr(settings, "DEEPSEEK_API_KEY", "") or ""


def _provider_default_model(provider: str) -> str:
    if provider == "openai":
        return getattr(settings, "OPENAI_CHAT_MODEL", "") or "gpt-4-turbo-preview"
    if provider == "deepseek":
        return _DEFAULT_DEEPSEEK_MODEL
    if provider == "google":
        return _DEFAULT_GEMINI_MODEL
    if provider == "groq":
        return _DEFAULT_GROQ_MODEL
    if provider == "anthropic":
        return _DEFAULT_ANTHROPIC_MODEL
    return _DEFAULT_OLLAMA_MODEL


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

    model_name = model or _DEFAULT_GEMINI_MODEL
    if not model_name.startswith("gemini-"):
        model_name = _DEFAULT_GEMINI_MODEL

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
        "model": model or _DEFAULT_GROQ_MODEL,
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
                raise RuntimeError(f"Groq HTTP {response.status_code}: {response.text}")
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
        model=model or _DEFAULT_DEEPSEEK_MODEL,
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
        model=model or _DEFAULT_ANTHROPIC_MODEL,
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
                raise RuntimeError(f"Ollama HTTP {response.status_code}: {response.text}")
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
        model=model or getattr(settings, "OPENAI_CHAT_MODEL", "gpt-4-turbo-preview"),
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
        return True
    return False


def _provider_chain(provider: Optional[str]) -> List[str]:
    requested = (provider or _resolve_provider()).lower().strip()
    if provider:
        return [requested]
    return [requested] + [item for item in _FALLBACK_CHAIN if item != requested]


async def stream_direct(
    messages: List[Dict[str, str]],
    provider: str,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    key = (provider or "").lower().strip()
    fn = _PROVIDER_STREAM_MAP.get(key)
    if fn is None:
        raise RuntimeError(f"Unsupported provider: {provider}")
    if not _provider_ready(key):
        raise RuntimeError(f"Provider not configured: {key}")

    normalized_messages = _normalize_messages(messages)
    if not normalized_messages:
        raise RuntimeError("No valid messages were provided to the AI service")

    resolved_model = model or _provider_default_model(key)
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
) -> str:
    tokens: List[str] = []
    async for token in stream_direct(messages, provider, model, temperature, max_tokens):
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
) -> AsyncGenerator[str, None]:
    normalized_messages = _normalize_messages(messages)
    if not normalized_messages:
        raise RuntimeError("No valid messages were provided to the AI service")

    chain = _provider_chain(provider)
    ready_chain = [item for item in chain if _provider_ready(item)]
    if not ready_chain:
        if provider:
            raise RuntimeError(f"Provider not configured: {provider}")
        logger.warning("No configured AI providers were available")
        yield _OFFLINE_TEXT
        return

    requested_provider = (provider or _resolve_provider()).lower().strip()
    errors: List[str] = []

    for current_provider in ready_chain:
        fn = _PROVIDER_STREAM_MAP.get(current_provider)
        if fn is None:
            errors.append(f"{current_provider}: unsupported provider")
            continue

        model_for_provider = _model_for_provider(current_provider, requested_provider, model) or _provider_default_model(current_provider)
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
            errors.append(f"{current_provider}: {exc}")
            if chunks:
                partial = "".join(chunks).strip()
                if partial:
                    _log_response(current_provider, model_for_provider, partial)
                    return

        if provider:
            break

    raise RuntimeError("All configured AI providers failed or returned empty responses: " + "; ".join(errors))


async def _complete_non_stream(
    messages: List[Dict[str, str]],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    tokens: List[str] = []
    async for token in _stream_with_fallback(messages, provider, model, temperature, max_tokens):
        tokens.append(token)
    text = "".join(tokens).strip()
    if not text:
        raise RuntimeError("AI completion returned an empty response")
    return text


class AIService:
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        provider: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        if stream:
            async for token in _stream_with_fallback(messages, provider, model, temperature, max_tokens):
                yield token
        else:
            result = await _complete_non_stream(messages, provider, model, temperature, max_tokens)
            yield result

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        async for token in _stream_with_fallback(messages, provider, model, temperature, max_tokens):
            yield token

    async def generate_code(self, prompt: str, language: str = "python") -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert programmer. Generate clean, well-documented "
                    f"{language} code. Do not invent APIs or library behavior."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        return await _complete_non_stream(messages)

    async def explain_code(self, code: str, language: str = "python") -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert programming instructor. Explain the code clearly, "
                    "step by step, and say when any behavior depends on external context."
                ),
            },
            {"role": "user", "content": f"Explain this {language} code:\n\n{code}"},
        ]
        return await _complete_non_stream(messages)

    async def debug_code(self, code: str, error: str = "") -> str:
        prompt = f"Debug this code:\n\n{code}"
        if error:
            prompt += f"\n\nError message:\n{error}"
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert debugger. Identify the real issue, avoid guessing, "
                    "and provide a corrected solution with a concise explanation."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        return await _complete_non_stream(messages)

    async def optimize_code(self, code: str, language: str = "python") -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are an expert in {language} optimization. Suggest accurate, justified "
                    "performance improvements and avoid speculative claims."
                ),
            },
            {"role": "user", "content": f"Optimize this code:\n\n{code}"},
        ]
        return await _complete_non_stream(messages)

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
            system = (
                "You are NOVA AI's Safe Reasoning assistant. Provide a structured answer with the sections "
                "Answer, Safety Notes, and Next Steps. If you are unsure, say so."
            )
        elif mode == "knowledge":
            system = (
                "You are NOVA AI's Knowledge Assistant. Provide a concise, factual answer and distinguish "
                "clearly between facts and uncertainty."
            )
        elif mode == "summary":
            system = "You are NOVA AI's Summarizer. Provide a clear summary with key points only."
        else:
            system = (
                "You are NOVA AI's Deep Explanation Engine. Explain step by step with clear logic, "
                "but do not invent missing facts."
            )

        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"Audience: {audience}\nDetail Level: {detail}\nRequest: {prompt}",
            },
        ]
        return await _complete_non_stream(messages)

    async def summarize_document(self, text: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert at summarizing documents. Summarize only what is supported by the text "
                    "and do not add unsupported claims."
                ),
            },
            {"role": "user", "content": f"Summarize this document:\n\n{str(text)[:8000]}"},
        ]
        return await _complete_non_stream(messages)

    async def answer_question_from_document(self, question: str, context: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "Answer questions only from the provided context. If the answer is not in the context, say "
                    "\"I don't know based on the provided document.\""
                ),
            },
            {"role": "user", "content": f"Context:\n{str(context)[:8000]}\n\nQuestion: {question}"},
        ]
        return await _complete_non_stream(messages)

    async def generate_learning_roadmap(self, topic: str, level: str = "beginner") -> Dict:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert learning advisor. Create a structured roadmap with realistic milestones "
                    "and avoid unsupported claims about external resources."
                ),
            },
            {"role": "user", "content": f"Create a {level} learning roadmap for: {topic}"},
        ]
        roadmap = await _complete_non_stream(messages)
        return {"topic": topic, "level": level, "roadmap": roadmap}

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
    ) -> List[str]:
        cleaned_prompt = " ".join((prompt or "").split()).strip()[:4000]
        if not cleaned_prompt:
            return []

        openai_key = getattr(settings, "OPENAI_API_KEY", "")
        if not openai_key:
            logger.warning("Image generation skipped because OPENAI_API_KEY is not configured")
            return []

        from openai import AsyncOpenAI

        try:
            client = AsyncOpenAI(api_key=openai_key, timeout=_request_timeout_seconds())
            model_name = getattr(settings, "OPENAI_IMAGE_MODEL", "dall-e-3")
            request_args = {
                "model": model_name,
                "prompt": cleaned_prompt,
                "size": size,
                "n": n,
                "response_format": "b64_json",
            }
            if model_name == "dall-e-3":
                request_args["quality"] = getattr(settings, "OPENAI_IMAGE_QUALITY", "hd") or "hd"
            response = await client.images.generate(**request_args)
            images = [
                item.b64_json
                if str(item.b64_json or "").startswith("data:")
                else f"data:image/png;base64,{item.b64_json}"
                for item in response.data
                if getattr(item, "b64_json", None)
            ]
            if not images:
                logger.warning(
                    "Image API returned no image data prompt=%s",
                    cleaned_prompt[:180],
                )
            return images
        except Exception as exc:
            logger.warning("Image API failed prompt=%s error=%s", cleaned_prompt[:180], exc)
            return []

    async def get_available_providers(self) -> List[Dict]:
        providers = []

        if _openai_api_key():
            openai_models = [
                getattr(settings, "OPENAI_CHAT_MODEL", ""),
                getattr(settings, "OPENAI_CODE_MODEL", ""),
                getattr(settings, "OPENAI_EXPLAIN_MODEL", ""),
            ]
            providers.append(
                {
                    "id": "openai",
                    "name": "OpenAI",
                    "models": [model for model in dict.fromkeys(openai_models) if model] or ["gpt-4-turbo-preview"],
                }
            )

        if _deepseek_api_key():
            providers.append(
                {
                    "id": "deepseek",
                    "name": "DeepSeek",
                    "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
                }
            )

        if _google_api_key():
            providers.append(
                {
                    "id": "google",
                    "name": "Gemini (Google)",
                    "models": ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"],
                }
            )

        if getattr(settings, "GROQ_API_KEY", ""):
            providers.append(
                {
                    "id": "groq",
                    "name": "Groq",
                    "models": ["llama-3.3-70b-versatile", "llama3-8b-8192", "mixtral-8x7b-32768", "gemma2-9b-it"],
                }
            )

        if getattr(settings, "ANTHROPIC_API_KEY", ""):
            providers.append(
                {
                    "id": "anthropic",
                    "name": "Claude",
                    "models": ["claude-opus-4-5", "claude-sonnet-4-5", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
                }
            )

        providers.append({"id": "ollama", "name": "Ollama (Local)", "models": ["llama3", "mistral", "codellama"]})
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
) -> AsyncGenerator[str, None]:
    async for token in _stream_with_fallback(messages, provider, model, temperature, max_tokens):
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
