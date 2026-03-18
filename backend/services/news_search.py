from duckduckgo_search import DDGS


def search_news(query: str, max_results: int = 5):
    results = []
    if not query:
        return results

    with DDGS() as ddgs:
        for r in ddgs.news(query, max_results=max_results):
            results.append(
                {
                    "title": r.get("title") or "",
                    "body": r.get("body") or "",
                    "link": r.get("url") or "",
                }
            )

    return results