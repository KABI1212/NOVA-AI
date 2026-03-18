from typing import List, Dict


class ConversationMemory:
    """Simple in-memory buffer for chat history (optional)."""
    def __init__(self):
        self._messages: List[Dict[str, str]] = []

    def add(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})

    def clear(self) -> None:
        self._messages = []

    def messages(self) -> List[Dict[str, str]]:
        return list(self._messages)


memory = ConversationMemory()
