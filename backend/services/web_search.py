from duckduckgo_search import DDGS


def search_web(query: str, max_results: int = 6):
    results = []
    if not query:
        return results

    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(
                {
                    "title": r.get("title") or "",
                    "body": r.get("body") or "",
                    "link": r.get("href") or r.get("link") or "",
                }
            )

    return results