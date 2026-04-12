import asyncio
from time import perf_counter
from typing import Dict, List

from services.provider_clients import (
    ask_chatgpt,
    ask_claude,
    ask_deepseek,
    ask_gemini,
    ask_groq,
    ask_ollama,
)

TIMEOUT_SECONDS = 3.0

PROVIDER_ORDER = [
    ("chatgpt", ask_chatgpt, "gpt-4o-mini"),
    ("claude", ask_claude, "claude-sonnet-4-5"),
    ("gemini", ask_gemini, "gemini-2.5-flash"),
    ("deepseek", ask_deepseek, "deepseek-chat"),
    ("groq", ask_groq, "llama-3.3-70b-versatile"),
    ("ollama", ask_ollama, "llama3"),
]


async def _timed_call(name: str, func, prompt: str, system_prompt: str, model: str) -> Dict:
    start = perf_counter()
    try:
        result = await asyncio.wait_for(func(prompt, system_prompt, model), timeout=TIMEOUT_SECONDS)
        elapsed = perf_counter() - start
        return {
            "provider": name,
            "model": model,
            "text": (result or "").strip(),
            "elapsed": round(elapsed, 3),
            "ok": True,
        }
    except Exception as exc:
        elapsed = perf_counter() - start
        return {
            "provider": name,
            "model": model,
            "text": "",
            "elapsed": round(elapsed, 3),
            "ok": False,
            "error": str(exc),
        }


async def query_models(prompt: str, system_prompt: str) -> List[Dict]:
    tasks = [
        _timed_call(name, func, prompt, system_prompt, model)
        for name, func, model in PROVIDER_ORDER
    ]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    return results
