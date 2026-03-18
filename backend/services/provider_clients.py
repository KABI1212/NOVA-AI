import os
from typing import Optional
import httpx

from config.settings import settings
from services.ai_service import direct_completion

DEFAULT_MODELS = {
    "claude": "claude-sonnet-4-5",
    "gemini": "gemini-1.5-flash",
    "chatgpt": "gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "perplexity": "sonar-pro",
    "groq": "llama-3.3-70b-versatile",
    "ollama": "llama3",
}


def _build_messages(system_prompt: str, prompt: str):
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]


async def ask_chatgpt(prompt: str, system_prompt: str, model: Optional[str] = None) -> str:
    messages = _build_messages(system_prompt, prompt)
    model_name = model or getattr(settings, "OPENAI_CHAT_MODEL", "") or DEFAULT_MODELS["chatgpt"]
    return await direct_completion(messages, provider="openai", model=model_name)


async def ask_gemini(prompt: str, system_prompt: str, model: Optional[str] = None) -> str:
    messages = _build_messages(system_prompt, prompt)
    model_name = model or DEFAULT_MODELS["gemini"]
    return await direct_completion(messages, provider="google", model=model_name)


async def ask_claude(prompt: str, system_prompt: str, model: Optional[str] = None) -> str:
    messages = _build_messages(system_prompt, prompt)
    model_name = model or DEFAULT_MODELS["claude"]
    return await direct_completion(messages, provider="anthropic", model=model_name)


async def ask_deepseek(prompt: str, system_prompt: str, model: Optional[str] = None) -> str:
    messages = _build_messages(system_prompt, prompt)
    model_name = model or DEFAULT_MODELS["deepseek"]
    return await direct_completion(messages, provider="deepseek", model=model_name)


async def ask_groq(prompt: str, system_prompt: str, model: Optional[str] = None) -> str:
    messages = _build_messages(system_prompt, prompt)
    model_name = model or DEFAULT_MODELS["groq"]
    return await direct_completion(messages, provider="groq", model=model_name)


async def ask_ollama(prompt: str, system_prompt: str, model: Optional[str] = None) -> str:
    messages = _build_messages(system_prompt, prompt)
    model_name = model or DEFAULT_MODELS["ollama"]
    return await direct_completion(messages, provider="ollama", model=model_name)


async def ask_perplexity(prompt: str, system_prompt: str, model: Optional[str] = None) -> str:
    api_key = os.getenv("PERPLEXITY_API_KEY") or getattr(settings, "PERPLEXITY_API_KEY", "")
    if not api_key:
        raise RuntimeError("Missing PERPLEXITY_API_KEY")

    model_name = model or DEFAULT_MODELS["perplexity"]
    payload = {
        "model": model_name,
        "messages": _build_messages(system_prompt, prompt),
        "temperature": 0.3,
        "max_tokens": 1024,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
        )

    if response.status_code >= 400:
        raise RuntimeError(response.text)

    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        return ""

    message = choices[0].get("message") or {}
    return message.get("content", "") or ""


async def ask_provider(
    provider: str,
    prompt: str,
    system_prompt: str,
    model: Optional[str] = None,
) -> str:
    key = (provider or "").lower()
    if key == "openai" or key == "chatgpt":
        return await ask_chatgpt(prompt, system_prompt, model)
    if key == "google" or key == "gemini":
        return await ask_gemini(prompt, system_prompt, model)
    if key == "anthropic" or key == "claude":
        return await ask_claude(prompt, system_prompt, model)
    if key == "deepseek":
        return await ask_deepseek(prompt, system_prompt, model)
    if key == "perplexity":
        return await ask_perplexity(prompt, system_prompt, model)
    if key == "groq":
        return await ask_groq(prompt, system_prompt, model)
    if key == "ollama":
        return await ask_ollama(prompt, system_prompt, model)

    raise RuntimeError(f"Unsupported provider: {provider}")