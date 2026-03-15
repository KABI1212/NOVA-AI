import os
import json
from typing import Dict, AsyncGenerator, Tuple
import httpx
from fastapi import HTTPException

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


def _extract_content(data: Dict) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""

    message = choices[0].get("message") or {}
    content = message.get("content")
    if content:
        return content

    return choices[0].get("text", "")


def _resolve_provider(provider: str, model: str) -> Tuple[str, str, Dict[str, str]]:
    key = (provider or "").strip().lower()
    if key not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    if not model:
        raise HTTPException(status_code=400, detail="Model is required")

    api_key = os.getenv(PROVIDERS[key]["env_key"])
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing API key for provider")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if key == "openrouter":
        headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE", "http://localhost:3000")
        headers["X-Title"] = os.getenv("OPENROUTER_APP", "NOVA AI")

    return key, PROVIDERS[key]["base_url"], headers


async def generate_response(provider: str, model: str, message: str) -> Dict[str, str]:
    _, base_url, headers = _resolve_provider(provider, model)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(base_url, headers=headers, json=payload)

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    data = response.json()
    content = _extract_content(data).strip()

    return {"response": content}


async def stream_response(provider: str, model: str, message: str) -> AsyncGenerator[str, None]:
    _, base_url, headers = _resolve_provider(provider, model)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "temperature": 0.7,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=60) as client:
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
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue

                choices = payload.get("choices") or [{}]
                delta = choices[0].get("delta") or {}
                content = delta.get("content")

                if not content:
                    message_payload = choices[0].get("message") or {}
                    content = message_payload.get("content")

                if content:
                    yield content
