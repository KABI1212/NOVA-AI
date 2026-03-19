import asyncio
import re
from datetime import datetime
from typing import Dict, List

import bs4
import httpx
from ddgs import DDGS

YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
TEMPORAL_KEYWORDS = (
    "latest",
    "current",
    "today",
    "recent",
    "new",
    "updated",
    "update",
    "news",
    "breaking",
    "this year",
    "last year",
    "trend",
    "trends",
    "happened",
    "released",
    "announced",
)
SPORTS_LEAGUE_KEYWORDS = (
    "ipl",
    "cricket",
    "premier league",
    "champions league",
    "la liga",
    "serie a",
    "bundesliga",
    "nba",
    "nfl",
    "nhl",
    "mlb",
    "f1",
    "formula 1",
    "world cup",
    "t20",
)
SPORTS_STATUS_KEYWORDS = (
    "captain",
    "captains",
    "coach",
    "manager",
    "squad",
    "roster",
    "lineup",
    "standings",
    "standing",
    "points table",
    "fixtures",
    "schedule",
    "transfer",
    "injury",
)
NEWS_KEYWORDS = (
    "news",
    "breaking",
    "headline",
    "headlines",
    "announced",
    "released",
    "launch",
    "launched",
)


def extract_query_years(query: str) -> List[str]:
    return sorted(set(YEAR_PATTERN.findall(query or "")))


def is_temporal_query(query: str) -> bool:
    text = (query or "").lower()
    if extract_query_years(text):
        return True
    if any(keyword in text for keyword in TEMPORAL_KEYWORDS):
        return True
    if any(keyword in text for keyword in SPORTS_LEAGUE_KEYWORDS):
        return True
    return any(keyword in text for keyword in SPORTS_STATUS_KEYWORDS)


def _infer_timelimit(query: str, years: List[str]) -> str | None:
    text = (query or "").lower()
    if years:
        return None
    if "today" in text or "breaking" in text:
        return "d"
    if "this week" in text or "weekly" in text:
        return "w"
    if "this month" in text:
        return "m"
    if is_temporal_query(text):
        return "y"
    return None


def _normalize_text_result(result: Dict) -> Dict:
    return {
        "title": result.get("title", ""),
        "url": result.get("href", ""),
        "snippet": result.get("body", ""),
        "date": result.get("date"),
        "source": result.get("source", "Web"),
        "kind": "text",
    }


def _normalize_news_result(result: Dict) -> Dict:
    return {
        "title": result.get("title", ""),
        "url": result.get("url", ""),
        "snippet": result.get("body", ""),
        "date": result.get("date"),
        "source": result.get("source", "News"),
        "kind": "news",
    }


def _score_result(result: Dict, query: str, query_years: List[str], index: int) -> float:
    haystack = " ".join(
        str(result.get(field, "") or "").lower()
        for field in ("title", "snippet", "url", "date", "source")
    )
    text = (query or "").lower()
    score = 0.0

    for year in query_years:
        if year in haystack:
            score += 10.0

    if result.get("kind") == "news" and is_temporal_query(text):
        score += 3.0
    if result.get("date"):
        score += 1.0

    current_year = str(datetime.utcnow().year)
    if is_temporal_query(text) and current_year in haystack:
        score += 2.0

    score -= index * 0.01
    return score


def _dedupe_and_rank(results: List[Dict], query: str, max_results: int) -> List[Dict]:
    unique_results: List[Dict] = []
    seen_urls = set()

    for result in results:
        url = (result.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        unique_results.append(result)

    query_years = extract_query_years(query)
    indexed_results = list(enumerate(unique_results))
    ranked = sorted(
        indexed_results,
        key=lambda item: _score_result(item[1], query, query_years, item[0]),
        reverse=True,
    )
    return [result for _, result in ranked[:max_results]]


async def search_web(query: str, max_results: int = 5) -> List[Dict]:
    try:
        loop = asyncio.get_running_loop()
        years = extract_query_years(query)
        timelimit = _infer_timelimit(query, years)
        temporal_query = is_temporal_query(query)
        should_include_news = (
            any(keyword in (query or "").lower() for keyword in NEWS_KEYWORDS)
            or temporal_query
        )
        text_limit = max(max_results * 3, 10) if temporal_query else max_results

        def _search():
            combined_results: List[Dict] = []
            with DDGS() as ddgs:
                try:
                    text_results = list(
                        ddgs.text(
                            query,
                            max_results=text_limit,
                            safesearch="moderate",
                            timelimit=timelimit,
                        )
                    )
                    combined_results.extend(_normalize_text_result(result) for result in text_results)
                except Exception:
                    pass

                if should_include_news:
                    try:
                        news_results = list(
                            ddgs.news(
                                query,
                                max_results=max_results * 2,
                                safesearch="moderate",
                                timelimit=timelimit if timelimit in {"d", "w", "m"} else None,
                            )
                        )
                        combined_results.extend(_normalize_news_result(result) for result in news_results)
                    except Exception:
                        pass

            return _dedupe_and_rank(combined_results, query, max_results)

        return await loop.run_in_executor(None, _search)
    except Exception:
        return []


async def fetch_page_content(url: str, max_chars: int = 3000) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NOVA-AI/1.0)"}
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        soup = bs4.BeautifulSoup(response.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "ads", "iframe"]):
            tag.decompose()

        main = (
            soup.find("article")
            or soup.find("main")
            or soup.find(id="content")
            or soup.find(class_="content")
            or soup.body
        )

        text = main.get_text(separator="\n", strip=True) if main else ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        content = "\n".join(lines)
        return content[:max_chars] + ("..." if len(content) > max_chars else "")
    except Exception as error:
        return f"Could not fetch page: {str(error)}"


def format_results_for_ai(results: List[Dict]) -> str:
    if not results:
        return "No search results found."

    formatted = "SEARCH RESULTS:\n\n"
    for index, result in enumerate(results, 1):
        formatted += f"[{index}] {result['title']}\n"
        formatted += f"URL: {result['url']}\n"
        if result.get("date"):
            formatted += f"Date: {result['date']}\n"
        if result.get("source"):
            formatted += f"Source: {result['source']}\n"
        formatted += f"Summary: {result['snippet']}\n\n"

    return formatted
