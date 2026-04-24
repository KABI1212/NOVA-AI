import os
import httpx

API_KEY = os.getenv("AIzaSyD0kIpYn9LQa5dRMwQG_iRGB-fEENc19b4")

async def ask_gemini(query: str):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}",
            json={"contents": [{"parts": [{"text": query}]}]},
            timeout=30.0
        )
        res.raise_for_status()
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
