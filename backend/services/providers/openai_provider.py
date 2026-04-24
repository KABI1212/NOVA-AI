import os
from openai import OpenAI

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

async def ask_openai(query: str):
    if not client:
        return "OpenAI API key not configured. Use another provider."
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": query}]
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"OpenAI error: {str(e)}"
