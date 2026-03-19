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


def _default_temperature() -> float:
    value = float(getattr(settings, "AI_TEMPERATURE", 0.3) or 0.3)
    return max(0.0, min(value, 1.0))


def _default_max_tokens() -> int:
    value = int(getattr(settings, "AI_MAX_TOKENS", 2048) or 2048)
    return max(128, value)


def _request_timeout_seconds() -> int:
    return max(10, int(getattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 60) or 60))


def _preview_text(text: str) -> str:
    limit = int(getattr(settings, "AI_LOG_PREVIEW_CHARS", 400) or 400)
    return " ".join((text or "").split())[:limit]


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

    choice = choices[0] or {}
    message = choice.get("message") or {}
    content = _extract_text_part(message.get("content"))
    if content:
        return content

    delta = choice.get("delta") or {}
    content = _extract_text_part(delta.get("content"))
    if content:
        return content

    return str(choice.get("text", "") or "")


def _resolve_provider(provider: str, model: str) -> Tuple[str, str, Dict[str, str]]:
    key = (provider or "").strip().lower()
    if key not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    if not model:
        raise HTTPException(status_code=400, detail="Model is required")

    api_key = os.getenv(PROVIDERS[key]["env_key"]) or getattr(settings, PROVIDERS[key]["env_key"], "")
    if not api_key:
        raise HTTPException(status_code=500, detail=f"Missing API key for provider: {key}")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if key == "openrouter":
        headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE", "http://localhost:3000")
        headers["X-Title"] = os.getenv("OPENROUTER_APP", "NOVA AI")

    return key, PROVIDERS[key]["base_url"], headers


def _log_request(provider: str, model: str, messages: List[Dict[str, str]]):
    if not (getattr(settings, "AI_DEBUG_LOGGING", False) or getattr(settings, "DEBUG", False)):
        return

    logger.info(
        "Compatible provider request provider=%s model=%s message_count=%s preview=%s",
        provider,
        model,
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


def _log_response(provider: str, model: str, text: str):
    if not (getattr(settings, "AI_DEBUG_LOGGING", False) or getattr(settings, "DEBUG", False)):
        return

    logger.info(
        "Compatible provider response provider=%s model=%s chars=%s preview=%s",
        provider,
        model,
        len(text or ""),
        _preview_text(text or ""),
    )


async def generate_response(
    provider: str,
    model: str,
    messages: List[Dict[str, str]] | str,
) -> Dict[str, str]:
    normalized_messages = _normalize_messages(messages)
    if not normalized_messages:
        raise HTTPException(status_code=400, detail="No valid messages provided")

    key, base_url, headers = _resolve_provider(provider, model)
    _log_request(key, model, normalized_messages)

    payload = {
        "model": model,
        "messages": normalized_messages,
        "temperature": _default_temperature(),
        "max_tokens": _default_max_tokens(),
    }

    async with httpx.AsyncClient(timeout=_request_timeout_seconds()) as client:
        response = await client.post(base_url, headers=headers, json=payload)

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

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
) -> AsyncGenerator[str, None]:
    normalized_messages = _normalize_messages(messages)
    if not normalized_messages:
        raise HTTPException(status_code=400, detail="No valid messages provided")

    key, base_url, headers = _resolve_provider(provider, model)
    _log_request(key, model, normalized_messages)

    payload = {
        "model": model,
        "messages": normalized_messages,
        "temperature": _default_temperature(),
        "max_tokens": _default_max_tokens(),
        "stream": True,
    }

    full_response = ""
    async with httpx.AsyncClient(timeout=_request_timeout_seconds()) as client:
        async with client.stream("POST", base_url, headers=headers, json=payload) as response:
            if response.status_code >= 400:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue

                data = line.replace("data:", "", 1).strip()
                if data == "[DONE]":
                    break

                try:
                    payload_data = json.loads(data)
                except json.JSONDecodeError:
                    continue

                choices = payload_data.get("choices") or [{}]
                choice = choices[0] or {}
                delta = choice.get("delta") or {}
                content = _extract_text_part(delta.get("content"))

                if not content:
                    message_payload = choice.get("message") or {}
                    content = _extract_text_part(message_payload.get("content"))

                if content:
                    full_response += content
                    yield content

    if not full_response.strip():
        raise HTTPException(status_code=502, detail=f"{key} returned an empty response")

    _log_response(key, model, full_response)
