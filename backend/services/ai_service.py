"""
ai_service.py - NOVA AI multi-provider service
Priority order: OpenAI -> DeepSeek -> Google Gemini -> Groq -> Anthropic -> Ollama -> Offline
Supports both streaming and non-streaming for all methods.
"""

from __future__ import annotations

import json
from typing import AsyncGenerator, Dict, List, Optional

import httpx

from config.settings import settings


# ---------------------------------------------------------------------------
# Provider constants
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_provider() -> str:
    """Return the configured provider, falling back through the priority chain."""
    p = (getattr(settings, "AI_PROVIDER", "") or "").lower()
    if p:
        return p
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
    return (
        getattr(settings, "GOOGLE_API_KEY", "")
        or getattr(settings, "GEMINI_API_KEY", "")
        or ""
    )


def _openai_api_key() -> str:
    return getattr(settings, "OPENAI_API_KEY", "") or ""


def _deepseek_api_key() -> str:
    return getattr(settings, "DEEPSEEK_API_KEY", "") or ""


def _messages_to_gemini(messages: List[Dict[str, str]]):
    """Convert OpenAI-style messages to Gemini contents + system instruction."""
    from google.genai import types # type: ignore

    system_parts: List[str] = []
    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            if content:
                system_parts.append(content)
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append(
            types.Content(role=gemini_role, parts=[types.Part.from_text(content)])
        )
    system_instruction = "\n\n".join(system_parts).strip()
    return contents, system_instruction


def _model_for_provider(
    provider: str,
    requested_provider: str,
    explicit_model: Optional[str],
) -> Optional[str]:
    if explicit_model and provider == requested_provider:
        return explicit_model
    if provider == requested_provider:
        model = getattr(settings, "AI_MODEL", "")
        if model:
            if provider == "openai":
                return model
            if provider == "deepseek" and not model.startswith("deepseek-"):
                return None
            if provider == "google" and not model.startswith("gemini-"):
                return None
            if provider == "anthropic" and not model.startswith("claude-"):
                return None
            if provider == "groq" and model.startswith(
                ("gemini-", "claude-", "gpt-", "deepseek-")
            ):
                return None
            return model
    return None


# ---------------------------------------------------------------------------
# Core streaming implementations
# ---------------------------------------------------------------------------


async def _stream_google(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    from google import genai
    from google.genai import types # type: ignore

    api_key = _google_api_key()
    if not api_key:
        raise RuntimeError("Missing GOOGLE_API_KEY or GEMINI_API_KEY")

    model_name = model or _DEFAULT_GEMINI_MODEL
    if not model_name.startswith("gemini-"):
        model_name = _DEFAULT_GEMINI_MODEL

    contents, system_instruction = _messages_to_gemini(messages)
    client = genai.Client(api_key=api_key)
    request: Dict = {"model": model_name, "contents": contents}
    if system_instruction:
        request["config"] = types.GenerateContentConfig(
            system_instruction=system_instruction
        )
    stream = await client.aio.models.generate_content_stream(**request)
    async for chunk in stream:
        text = getattr(chunk, "text", None)
        if text:
            yield text


async def _stream_groq(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    api_key = getattr(settings, "GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY")

    groq_model = model or _DEFAULT_GROQ_MODEL
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": groq_model,
        "messages": messages,
        "stream": True,
        "max_tokens": 2048,
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
        ) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"Groq HTTP {resp.status_code}")
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line.replace("data:", "").strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                    token = event["choices"][0]["delta"].get("content")
                    if token:
                        yield token
                except Exception:
                    continue


async def _stream_deepseek(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    from openai import AsyncOpenAI

    api_key = _deepseek_api_key()
    if not api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY")

    deepseek_model = model or _DEFAULT_DEEPSEEK_MODEL
    base_url = getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    stream = await client.chat.completions.create(
        model=deepseek_model,
        messages=messages,
        stream=True,
        temperature=0.7,
        max_tokens=2048,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def _stream_anthropic(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    import anthropic as _anthropic # type: ignore

    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY")

    anthropic_model = model or _DEFAULT_ANTHROPIC_MODEL
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs = [m for m in messages if m["role"] != "system"]

    client = _anthropic.AsyncAnthropic(api_key=api_key)
    async with client.messages.stream(
        model=anthropic_model,
        max_tokens=2000,
        system=system,
        messages=user_msgs,
    ) as stream:
        async for text in stream.text_stream:
            if text:
                yield text


async def _stream_ollama(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    model_name = model or _DEFAULT_OLLAMA_MODEL
    base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
    num_predict = getattr(settings, "OLLAMA_NUM_PREDICT", 512)
    num_ctx = getattr(settings, "OLLAMA_NUM_CTX", 4096)

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            f"{base_url}/api/chat",
            json={
                "model": model_name,
                "messages": messages,
                "stream": True,
                "options": {"num_predict": num_predict, "num_ctx": num_ctx},
            },
        ) as resp:
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                except Exception:
                    continue


async def _stream_openai(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    from openai import AsyncOpenAI

    api_key = _openai_api_key()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")

    openai_model = model or getattr(settings, "OPENAI_CHAT_MODEL", "gpt-4-turbo-preview")
    client = AsyncOpenAI(api_key=api_key)
    stream = await client.chat.completions.create(
        model=openai_model,
        messages=messages,
        stream=True,
        temperature=0.7,
        max_tokens=2048,
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


async def _stream_with_fallback(
    messages: List[Dict[str, str]],
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    requested = (provider or _resolve_provider()).lower()
    chain = [requested] + [p for p in _FALLBACK_CHAIN if p != requested]

    for p in chain:
        fn = _PROVIDER_STREAM_MAP.get(p)
        if fn is None:
            continue

        if p == "openai" and not _openai_api_key():
            continue
        if p == "deepseek" and not _deepseek_api_key():
            continue
        if p == "google" and not _google_api_key():
            continue
        if p == "groq" and not getattr(settings, "GROQ_API_KEY", ""):
            continue
        if p == "anthropic" and not getattr(settings, "ANTHROPIC_API_KEY", ""):
            continue

        model_for_provider = _model_for_provider(p, requested, model)
        got_token = False
        try:
            async for token in fn(messages, model_for_provider):
                got_token = True
                yield token
            return
        except Exception:
            if got_token:
                return
            continue

    yield _OFFLINE_TEXT


async def _complete_non_stream(
    messages: List[Dict[str, str]],
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    tokens: List[str] = []
    async for token in _stream_with_fallback(messages, provider, model):
        tokens.append(token)
    return "".join(tokens)


# ---------------------------------------------------------------------------
# AIService class
# ---------------------------------------------------------------------------


class AIService:
    """
    Unified AI service. All methods support the provider chain:
    Google Gemini -> Groq -> Anthropic -> Ollama -> Offline
    """

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        provider: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Primary chat entry-point."""
        if stream:
            async for token in _stream_with_fallback(messages, provider, model):
                yield token
        else:
            result = await _complete_non_stream(messages, provider, model)
            yield result

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming alias kept for backward compatibility."""
        async for token in _stream_with_fallback(messages, provider, model):
            yield token

    async def generate_code(self, prompt: str, language: str = "python") -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are an expert programmer. Generate clean, well-documented "
                    f"{language} code based on the user's request. "
                    "Include comments explaining the code."
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
                    "You are an expert programming instructor. "
                    "Explain the provided code clearly, step-by-step, "
                    "highlighting key concepts and best practices."
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
                    "You are an expert debugger. Analyze the code, "
                    "identify issues, and provide corrected code with explanations."
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
                    f"You are an expert in {language} optimization. "
                    "Analyze the code and suggest performance improvements, "
                    "better patterns, and best practices."
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
                "You are NOVA AI's Safe Reasoning assistant. Provide a structured, safe answer. "
                "Use the sections: Answer, Reasoning Summary, Safety or Edge Cases, Next Steps. "
                "Be helpful and refuse unsafe requests."
            )
        elif mode == "knowledge":
            system = (
                "You are NOVA AI's Knowledge Assistant. Provide a concise, factual answer. "
                "Add a short summary, key points, and one example when helpful."
            )
        elif mode == "summary":
            system = (
                "You are NOVA AI's Summarizer. Provide a clear, concise summary with key points."
            )
        else:
            system = (
                "You are NOVA AI's Deep Explanation Engine. Provide a step-by-step explanation "
                "with logical reasoning, concept breakdowns, and a worked example. "
                "Use clear section headings and a teaching tone."
            )

        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Audience: {audience}\nDetail Level: {detail}\nRequest: {prompt}"
                ),
            },
        ]
        return await _complete_non_stream(messages)

    async def summarize_document(self, text: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert at summarizing documents. "
                    "Provide a clear, concise summary highlighting key points and insights."
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
                    "You are a helpful assistant. Answer questions based on the provided context. "
                    "If the answer is not in the context, say so clearly."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n{str(context)[:8000]}\n\nQuestion: {question}",
            },
        ]
        return await _complete_non_stream(messages)

    async def generate_learning_roadmap(
        self, topic: str, level: str = "beginner"
    ) -> Dict:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert learning advisor. Create a structured learning roadmap "
                    "with clear milestones, resources, and progression steps."
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
        """
        Generate images via OpenAI DALL-E.
        Falls back to the SVG placeholder if no OpenAI key is configured.
        """
        openai_key = getattr(settings, "OPENAI_API_KEY", "")
        if not openai_key:
            return [generate_image_url(prompt)]

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=openai_key)
        image_model = getattr(settings, "OPENAI_IMAGE_MODEL", "dall-e-3")
        response = await client.images.generate(
            model=image_model,
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
            unique_models = [m for m in dict.fromkeys(openai_models) if m]
            providers.append({
                "id": "openai",
                "name": "OpenAI",
                "models": unique_models or ["gpt-4-turbo-preview"],
            })

        if _deepseek_api_key():
            providers.append({
                "id": "deepseek",
                "name": "DeepSeek",
                "models": [
                    "deepseek-chat",
                    "deepseek-coder",
                    "deepseek-reasoner",
                ],
            })

        if _google_api_key():
            providers.append({
                "id": "google",
                "name": "Gemini (Google)",
                "models": [
                    "gemini-1.5-flash",
                    "gemini-1.5-pro",
                    "gemini-2.0-flash-exp",
                ],
            })

        if getattr(settings, "GROQ_API_KEY", ""):
            providers.append({
                "id": "groq",
                "name": "Groq (Fast)",
                "models": [
                    "llama-3.3-70b-versatile",
                    "llama3-8b-8192",
                    "mixtral-8x7b-32768",
                    "gemma2-9b-it",
                ],
            })

        if getattr(settings, "ANTHROPIC_API_KEY", ""):
            providers.append({
                "id": "anthropic",
                "name": "Claude",
                "models": [
                    "claude-opus-4-5",
                    "claude-sonnet-4-5",
                    "claude-3-sonnet-20240229",
                    "claude-3-haiku-20240307",
                ],
            })

        providers.append({
            "id": "ollama",
            "name": "Ollama (Local)",
            "models": ["llama2", "mistral", "codellama"],
        })

        return providers


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

ai_service = AIService()


# ---------------------------------------------------------------------------
# Standalone helpers (kept for backward compatibility)
# ---------------------------------------------------------------------------


def generate_response(message: str) -> str:
    """Local fallback response generator."""
    cleaned = (message or "").strip()
    if not cleaned:
        return "NOVA AI: Ask me anything."
    return f"NOVA AI: {cleaned}"


async def stream_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Standalone stream_chat function used by routes/search.py and routes/chat.py.
    Wraps _stream_with_fallback for backward compatibility.
    """
    async for token in _stream_with_fallback(messages, provider, model):
        yield token


def generate_image_url(prompt: str) -> str:
    """Return a self-contained SVG data URL for image previews."""
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
