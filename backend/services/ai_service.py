"""
ai_service.py - NOVA AI multi-provider chat service
Provides consistent message formatting, logging, low-temperature generation,
provider fallback, and safer empty-response handling.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator, Dict, List, Optional

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
        openai_key = getattr(settings, "OPENAI_API_KEY", "")
        if not openai_key:
            return [generate_image_url(prompt)]

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=openai_key, timeout=_request_timeout_seconds())
        response = await client.images.generate(
            model=getattr(settings, "OPENAI_IMAGE_MODEL", "dall-e-3"),
            prompt=prompt,
            size=size,
            n=n,
            response_format="b64_json",
        )
        return [item.b64_json for item in response.data]

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

    safe_prompt = str(prompt or "NOVA AI").strip()[:60]
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='1024' height='1024'>"
        "<defs>"
        "<linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0%' stop-color='#0f172a'/>"
        "<stop offset='100%' stop-color='#111827'/>"
        "</linearGradient>"
        "</defs>"
        "<rect width='100%' height='100%' fill='url(#g)'/>"
        "<text x='50%' y='50%' font-size='42' fill='#f8fafc' "
        "font-family='Times New Roman, Times, serif' "
        "text-anchor='middle' dominant-baseline='middle'>"
        f"{safe_prompt}"
        "</text>"
        "</svg>"
    )
    return f"data:image/svg+xml;utf8,{quote(svg)}"
