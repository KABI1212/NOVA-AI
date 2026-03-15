from ddgs import DDGS
import bs4
import httpx
import asyncio
from typing import List, Dict

# ── Web search ────────────────────────────────────────────
async def search_web(query: str, max_results: int = 5) -> List[Dict]:
    try:
        loop = asyncio.get_event_loop()

        def _search():
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=max_results,
                    safesearch="moderate",
                ))
            return results

        results = await loop.run_in_executor(None, _search)

        return [
            {
                "title":   r.get("title",  ""),
                "url":     r.get("href",   ""),
                "snippet": r.get("body",   ""),
            }
            for r in results if r.get("href")
        ]

    except Exception as e:
        return [{"title": "Search failed", "url": "", "snippet": str(e)}]


# ── Fetch full page content ───────────────────────────────
async def fetch_page_content(url: str, max_chars: int = 3000) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; NOVA-AI/1.0)"
        }
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            res = await client.get(url, headers=headers)
            res.raise_for_status()

        soup = bs4.BeautifulSoup(res.text, "lxml")

        # Remove junk
        for tag in soup(["script", "style", "nav", "footer",
                          "header", "ads", "iframe"]):
            tag.decompose()

        # Get main content
        main = (
            soup.find("article") or
            soup.find("main")    or
            soup.find(id="content") or
            soup.find(class_="content") or
            soup.body
        )

        # ← fixed: proper \n separator instead of broken literal newline
        text = main.get_text(separator="\n", strip=True) if main else ""

        # Clean up blank lines
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        # ← fixed: proper \n join instead of broken literal newline
        content = "\n".join(lines)

        return content[:max_chars] + ("..." if len(content) > max_chars else "")

    except Exception as e:
        return f"Could not fetch page: {str(e)}"


# ── Format search results for AI context ─────────────────
def format_results_for_ai(results: List[Dict]) -> str:
    if not results:
        return "No search results found."

    # ← fixed: proper \n\n instead of broken literal newlines
    formatted = "SEARCH RESULTS:\n\n"
    for i, r in enumerate(results, 1):
        formatted += f"[{i}] {r['title']}\n"
        formatted += f"URL: {r['url']}\n"
        formatted += f"Summary: {r['snippet']}\n\n"

    return formatted
