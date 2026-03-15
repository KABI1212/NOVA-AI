simple_responses = {
    "hi": "Hello! How can I help you today?",
    "hello": "Hi there! What would you like to know?",
    "hey": "Hey! Ask me anything.",
    "thanks": "You're welcome!",
    "thank you": "Happy to help!",
    "good morning": "Good morning! How can I assist you?",
    "good evening": "Good evening! What can I help you with?",
}


def _strip_tool_prefix(message: str) -> str:
    lines = [line.strip() for line in (message or "").splitlines() if line.strip()]
    cleaned = []
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            continue
        cleaned.append(line)
    return " ".join(cleaned).strip()


def instant_reply(message: str):
    msg = _strip_tool_prefix(message).lower().strip()
    if msg in simple_responses:
        return simple_responses[msg]
    return None
