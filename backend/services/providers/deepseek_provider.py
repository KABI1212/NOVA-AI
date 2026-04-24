"""
Legacy module retained for backward compatibility.

Do not add secrets here. Use `backend/services/provider_clients.py` and the
standard environment variables instead.
"""

import os
import httpx

LEGACY_PROVIDER_NOTICE = "Use DEEPSEEK_API_KEY via provider_clients.py"

async def ask_deepseek(query: str):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": query}],
                "max_tokens": 1024,
                "temperature": 0.7
            },
            timeout=30.0
        )
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
