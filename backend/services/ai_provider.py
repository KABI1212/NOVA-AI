import asyncio
import json
import logging
import os
from typing import AsyncGenerator, Dict, List, Tuple

import httpx
from fastapi import HTTPException

from config.settings import settings


logger = logging.getLogger(__name__)

PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
        "env_key": "GROQ_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "env_key": "OPENROUTER_API_KEY",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1/chat/completions",
        "env_key": "TOGETHER_API_KEY",
    },
}

# Retry config
_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_BASE = 1.5  # seconds; doubles each attempt
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def _default_temperature() -> float:
    value = float(getattr(settings, "AI_TEMPERATURE", 0.3) or 0.3)
    return max(0.0, min(value, 1.0))


def _default_top_p() -> float:
    value = float(getattr(settings, "AI_TOP_P", 1.0) or 1.0)
    return max(0.0, min(value, 1.0))


def _default_max_tokens() -> int:
    value = int(getattr(settings, "AI_MAX_TOKENS", 8192) or 8192)
    return max(4096, value)


def _connect_timeout_seconds() -> float:
    return max(5.0, float(getattr(settings, "AI_CONNECT_TIMEOUT_SECONDS", 10) or 10))


def _read_timeout_seconds() -> float:
    """
    Separate read timeout used for streaming to avoid killing long responses.
    For non-streaming this is the full request timeout.
    """
    return max(300.0, float(getattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 300) or 300))


def _stream_read_timeout_seconds() -> float:
    return max(600.0, float(getattr(settings, "AI_STREAM_TIMEOUT_SECONDS", 600) or 600))


def _preview_text(text: str) -> str:
    limit = int(getattr(settings, "AI_LOG_PREVIEW_CHARS", 400) or 400)
    return " ".join((text or "").split())[:limit]


def _debug_logging_enabled() -> bool:
    return bool(
        getattr(settings, "AI_DEBUG_LOGGING", False)
        or getattr(settings, "DEBUG", False)
    )


# ---------------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------------

def _normalize_messages(messages: List[Dict[str, str]] | str) -> List[Dict[str, str]]:
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]

    normalized = []
    for raw in messages or []:
        role = str(raw.get("role", "user")).strip().lower()
        if role not in {"system", "user", "assistant"}:
            role = "user"
        content = str(raw.get("content", "") or "").strip()
        if not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def _extract_text_part(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif "text" in item:
                    parts.append(str(item.get("text", "")))
        return "".join(parts)
    return ""


def _extract_content(data: Dict) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""

    choice = choices[0] if isinstance(choices, list) and choices else {}
    if not isinstance(choice, dict):
        return ""

    message = choice.get("message") or {}
    content = _extract_text_part(message.get("content"))
    if content:
        return content

    delta = choice.get("delta") or {}
    content = _extract_text_part(delta.get("content"))
    if content:
        return content

    return str(choice.get("text", "") or "")


def _parse_provider_error(response: httpx.Response) -> str:
    """
    Try to extract a human-readable error message from a provider's JSON error
    response. Falls back to raw text if parsing fails.
    """
    try:
        body = response.json()
        # OpenAI-compatible: {"error": {"message": "..."}}
        error = body.get("error") or {}
        if isinstance(error, dict) and error.get("message"):
            return error["message"]
        # Some providers use {"message": "..."}
        if body.get("message"):
            return str(body["message"])
    except Exception:
        pass
    return response.text or f"HTTP {response.status_code}"


# ---------------------------------------------------------------------------
# Provider resolution
# ---------------------------------------------------------------------------

def _resolve_provider(provider: str, model: str) -> Tuple[str, str, Dict[str, str]]:
    key = (provider or "").strip().lower()
    if key not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: '{provider}'")

    if not model:
        raise HTTPException(status_code=400, detail="Model is required")

    api_key = os.getenv(PROVIDERS[key]["env_key"]) or getattr(
        settings, PROVIDERS[key]["env_key"], ""
    )
    if not api_key:
        raise HTTPException(
            status_code=500, detail=f"Missing API key for provider: {key}"
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    base_url = PROVIDERS[key]["base_url"]

    if key == "openrouter":
        headers["HTTP-Referer"] = getattr(settings, "openrouter_referer", "http://localhost:3000")
        headers["X-Title"] = getattr(settings, "openrouter_app_name", "NOVA AI")
        base_url = (
            f"{str(getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')).rstrip('/')}"
            "/chat/completions"
        )

    return key, base_url, headers


# ---------------------------------------------------------------------------
# Logging helpers (never log headers or API keys)
# ---------------------------------------------------------------------------

def _log_request(provider: str, model: str, messages: List[Dict[str, str]]):
    if not _debug_logging_enabled():
        return

    logger.info(
        "Compatible provider request provider=%s model=%s message_count=%s preview=%s",
        provider,
        model,
        len(messages),
        json.dumps(
            [
                {
                    "role": msg["role"],
                    "content": _preview_text(msg["content"]),
                }
                for msg in messages
            ],
            ensure_ascii=False,
        ),
    )


def _log_response(provider: str, model: str, text: str):
    if not _debug_logging_enabled():
        return

    logger.info(
        "Compatible provider response provider=%s model=%s chars=%s preview=%s",
        provider,
        model,
        len(text or ""),
        _preview_text(text or ""),
    )


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

async def _post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: Dict[str, str],
    body: Dict,
) -> httpx.Response:
    """
    POST with exponential backoff retry for transient provider errors.
    Raises HTTPException on final failure.
    """
    last_exc: Exception | None = None

    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            response = await client.post(url, headers=headers, json=body)

            if response.status_code not in _RETRYABLE_STATUS_CODES:
                return response

            detail = _parse_provider_error(response)
            logger.warning(
                "Provider returned retryable status attempt=%s/%s status=%s detail=%s",
                attempt,
                _RETRY_ATTEMPTS,
                response.status_code,
                detail,
            )
            last_exc = HTTPException(status_code=response.status_code, detail=detail)

        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning(
                "Provider request error attempt=%s/%s error=%s",
                attempt,
                _RETRY_ATTEMPTS,
                str(exc),
            )
            last_exc = exc

        if attempt < _RETRY_ATTEMPTS:
            await asyncio.sleep(_RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))

    if isinstance(last_exc, HTTPException):
        raise last_exc
    raise HTTPException(status_code=503, detail=f"Provider unreachable after {_RETRY_ATTEMPTS} attempts")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_response(
    provider: str,
    model: str,
    messages: List[Dict[str, str]] | str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Dict[str, str]:
    normalized_messages = _normalize_messages(messages)
    if not normalized_messages:
        raise HTTPException(status_code=400, detail="No valid messages provided")

    key, base_url, headers = _resolve_provider(provider, model)
    _log_request(key, model, normalized_messages)

    body = {
        "model": model,
        "messages": normalized_messages,
        "temperature": _default_temperature() if temperature is None else temperature,
        "top_p": _default_top_p(),
        "max_tokens": _default_max_tokens() if max_tokens is None else max_tokens,
    }

    timeout = httpx.Timeout(connect=_connect_timeout_seconds(), read=_read_timeout_seconds(), write=10.0, pool=5.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await _post_with_retry(client, base_url, headers, body)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=_parse_provider_error(response),
        )

    data = response.json()
    content = _extract_content(data).strip()
    if not content:
        raise HTTPException(status_code=502, detail=f"{key} returned an empty response")

    _log_response(key, model, content)
    return {
        "provider": key,
        "model": model,
        "response": content,
    }


async def stream_response(
    provider: str,
    model: str,
    messages: List[Dict[str, str]] | str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    normalized_messages = _normalize_messages(messages)
    if not normalized_messages:
        raise HTTPException(status_code=400, detail="No valid messages provided")

    key, base_url, headers = _resolve_provider(provider, model)
    _log_request(key, model, normalized_messages)

    body = {
        "model": model,
        "messages": normalized_messages,
        "temperature": _default_temperature() if temperature is None else temperature,
        "top_p": _default_top_p(),
        "max_tokens": _default_max_tokens() if max_tokens is None else max_tokens,
        "stream": True,
    }

    # Use a longer read timeout for streaming to avoid premature disconnection
    timeout = httpx.Timeout(
        connect=_connect_timeout_seconds(),
        read=_stream_read_timeout_seconds(),
        write=10.0,
        pool=5.0,
    )

    full_response = ""

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", base_url, headers=headers, json=body) as response:
            if response.status_code >= 400:
                error_body = await response.aread()
                try:
                    error_detail = _parse_provider_error(
                        httpx.Response(response.status_code, content=error_body)
                    )
                except Exception:
                    error_detail = error_body.decode(errors="replace")
                raise HTTPException(status_code=response.status_code, detail=error_detail)

            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue

                raw = line.removeprefix("data:").strip()
                if raw == "[DONE]":
                    break

                try:
                    chunk = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                choices = chunk.get("choices")
                if not choices or not isinstance(choices, list):
                    continue

                choice = choices[0]
                if not isinstance(choice, dict):
                    continue

                # Prefer delta (streaming), fall back to message (some providers)
                delta = choice.get("delta") or {}
                content = _extract_text_part(delta.get("content"))

                if not content:
                    message_chunk = choice.get("message") or {}
                    content = _extract_text_part(message_chunk.get("content"))

                if content:
                    full_response += content
                    yield content

    if not full_response.strip():
        raise HTTPException(status_code=502, detail=f"{key} returned an empty response")

    _log_response(key, model, full_response)
