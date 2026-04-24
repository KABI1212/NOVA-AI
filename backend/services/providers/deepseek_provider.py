import os
import httpx

API_KEY = os.getenv("sk-a4fb52ecf86c4da2ae5399e0299d86e2")

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
