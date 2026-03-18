from typing import Dict, List

<<<<<<< HEAD
from backend.services.web_search_gemini import search_web
=======
from services.web_search import search_web
>>>>>>> 3520f8c8a820e9822841d33c9bb59a09576e92cf
from services.news_search import search_news
from services.multi_model import multi_model_reasoning, verify_answer

SYSTEM_PROMPT = (
    "You are NOVA AI, an advanced research assistant with live internet access.\n\n"
    "Rules:\n"
    "- Always use provided web results.\n"
    "- Never mention knowledge cutoffs.\n"
    "- Always provide the newest information.\n"
    "- Assume the current year is 2026 and prioritize the most recent sources.\n"
    "- Always cite sources."
)

def build_context(items: List[Dict]) -> str:
    lines = []
    for item in items:
        title = item.get("title", "").strip()
        body = item.get("body", "").strip()
        link = item.get("link", "").strip()
        if not (title or body or link):
            continue
        lines.append(f"{title} - {body} ({link})")
    return "\n\n".join(lines)


def collect_sources(items: List[Dict]) -> List[str]:
    links = []
    for item in items:
        link = (item.get("link") or "").strip()
        if link and link not in links:
            links.append(link)
    return links


def sanitize_answer(text: str) -> str:
    if not text:
        return text
    return text.replace("knowledge cutoff", "").replace("Knowledge cutoff", "")


def format_answer(answer: str, sources: List[str]) -> str:
    cleaned = (answer or "").strip()
    if not cleaned:
        cleaned = "I could not find a reliable answer from the sources provided."

    if not sources:
        return f"Answer: {cleaned}"

    sources_block = "\n".join([f"{idx + 1}. {link}" for idx, link in enumerate(sources)])
    return f"Answer: {cleaned}\n\nSources:\n{sources_block}"


async def run_agent(question: str) -> Dict:
    query = (question or "").strip()
    if not query:
        return {
            "answer": "Please enter a message.",
            "sources": [],
            "news": [],
            "badge": "🌐 Live Internet Answer",
        }

    web_results = search_web(query, max_results=6)
    news_results = search_news(query, max_results=5)

    context_items = web_results + news_results
    context_text = build_context(context_items)

    reasoning_prompt = (
        f"Question: {query}\n\n"
        f"Context:\n{context_text}\n\n"
        "Provide a clear, well-structured answer using the sources."
    )

    reasoning = await multi_model_reasoning(reasoning_prompt, SYSTEM_PROMPT)
    draft_answer = reasoning.get("answer", "")

    verified_answer = await verify_answer(draft_answer, context_text, SYSTEM_PROMPT)
    verified_answer = sanitize_answer(verified_answer).strip() or draft_answer.strip()

    sources = collect_sources(context_items)
    formatted = format_answer(verified_answer, sources)

    return {
        "answer": verified_answer,
        "message": formatted,
        "sources": sources,
        "news": news_results,
        "badge": "🌐 Live Internet Answer",
    }
