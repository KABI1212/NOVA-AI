from typing import Optional

conversation_history = []

MAX_HISTORY = 1000


def add_message(role: str, content: str):
    conversation_history.append({
        "role": role,
        "content": content,
    })

    if len(conversation_history) > MAX_HISTORY:
        conversation_history.pop(0)


def get_history(limit: Optional[int] = None):
    if limit is None:
        return list(conversation_history)
    return list(conversation_history[-limit:])
