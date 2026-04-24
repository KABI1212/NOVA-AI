def analyze_query(query: str):
    q = (query or "").lower()

    if len(q.split()) <= 3:
        return {"type": "simple", "complexity": "low", "priority": "speed"}

    if any(x in q for x in ["code", "python", "bug", "error", "api"]):
        return {"type": "coding", "complexity": "high", "priority": "accuracy"}

    if any(x in q for x in ["write", "story", "design", "creative"]):
        return {"type": "creative", "complexity": "medium", "priority": "quality"}

    if len(q.split()) > 25:
        return {"type": "complex", "complexity": "high", "priority": "accuracy"}

    return {"type": "factual", "complexity": "medium", "priority": "speed"}
