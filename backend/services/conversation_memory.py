from typing import Optional

conversation_histories: dict[str, list[dict]] = {}

MAX_HISTORY = 1000


def _session_key(session_id: Optional[str] = None) -> str:
    cleaned = str(session_id or "").strip()
    return cleaned[:120] if cleaned else "anonymous"


def add_message(role: str, content: str, session_id: Optional[str] = None):
    key = _session_key(session_id)
    history = conversation_histories.setdefault(key, [])
    history.append(
        {
            "role": role,
            "content": content,
        }
    )

    if len(history) > MAX_HISTORY:
        del history[: len(history) - MAX_HISTORY]


def get_history(limit: Optional[int] = None, session_id: Optional[str] = None):
    history = conversation_histories.get(_session_key(session_id), [])
    if limit is None:
        return list(history)
    return list(history[-limit:])


def clear_history(session_id: Optional[str] = None):
    conversation_histories.pop(_session_key(session_id), None)
