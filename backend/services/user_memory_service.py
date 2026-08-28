from __future__ import annotations

from contextlib import contextmanager
import logging
import re
from typing import Any, Iterator, List, Optional

from config.database import MongoSession
from models.user_memory import UserMemory

logger = logging.getLogger(__name__)

# Patterns for explicit memory requests
_REMEMBER_PATTERNS = [
    re.compile(r"^\s*(?:please\s+)?remember\s+(?:that\s+)?(.+)$", re.IGNORECASE),
    re.compile(r"^\s*note\s+(?:that\s+)?(.+)$", re.IGNORECASE),
    re.compile(r"^\s*my\s+(?:preferred|favorite)\s+(.+)\s+is\s+(.+)$", re.IGNORECASE),
    re.compile(r"^\s*i\s+(?:prefer|always use|work with|code in)\s+(.+)$", re.IGNORECASE),
]


@contextmanager
def _session_scope() -> Iterator[MongoSession]:
    session = MongoSession()
    try:
        yield session
    finally:
        session.close()


class UserMemoryService:
    """Service to manage long-term user memory across chats."""

    @staticmethod
    def get_memories(user_id: int | str, category: Optional[str] = None) -> List[UserMemory]:
        """Fetch active memories for a given user."""
        try:
            with _session_scope() as db:
                query = (UserMemory.user_id == user_id) & (UserMemory.is_active == True)
                if category:
                    query = query & (UserMemory.category == category)
                return db.query(UserMemory).filter(query).all()
        except Exception as exc:
            logger.warning("Failed to fetch user memories for user %s: %s", user_id, exc)
            return []

    @staticmethod
    def add_memory(
        user_id: int | str,
        key: str,
        value: str,
        category: str = "preference"
    ) -> Optional[UserMemory]:
        """Add or update a persistent memory for a user."""
        if not key or not value or not user_id:
            return None

        clean_key = " ".join(key.strip().split())[:120]
        clean_val = " ".join(value.strip().split())[:1000]

        try:
            with _session_scope() as db:
                existing = (
                    db.query(UserMemory)
                    .filter((UserMemory.user_id == user_id) & (UserMemory.key == clean_key))
                    .first()
                )
                if existing:
                    existing.value = clean_val
                    existing.category = category
                    existing.is_active = True
                    db.commit()
                    return existing

                memory = UserMemory(
                    user_id=user_id,
                    category=category,
                    key=clean_key,
                    value=clean_val,
                    is_active=True,
                )
                db.add(memory)
                db.commit()
                return memory
        except Exception as exc:
            logger.warning("Failed to add user memory: %s", exc)
            return None

    @staticmethod
    def delete_memory(user_id: int | str, memory_id: Any) -> bool:
        """Delete a specific memory belonging to user."""
        try:
            target_id = int(memory_id) if str(memory_id).isdigit() else memory_id
            with _session_scope() as db:
                memory = (
                    db.query(UserMemory)
                    .filter((UserMemory.id == target_id) & (UserMemory.user_id == user_id))
                    .first()
                )
                if memory:
                    db.delete(memory)
                    db.commit()
                    return True
                return False
        except Exception as exc:
            logger.warning("Failed to delete memory %s: %s", memory_id, exc)
            return False

    @staticmethod
    def clear_all(user_id: int | str) -> int:
        """Clear all memories for a user."""
        try:
            with _session_scope() as db:
                memories = db.query(UserMemory).filter(UserMemory.user_id == user_id).all()
                count = len(memories)
                for mem in memories:
                    db.delete(mem)
                db.commit()
                return count
        except Exception as exc:
            logger.warning("Failed to clear memories for user %s: %s", user_id, exc)
            return 0

    @classmethod
    def detect_and_store_preference(cls, user_id: int | str, message: str) -> Optional[UserMemory]:
        """Analyze message to check if user explicitly requested to remember a preference."""
        if not message or not user_id:
            return None

        text = message.strip()
        for pattern in _REMEMBER_PATTERNS:
            match = pattern.match(text)
            if match:
                groups = match.groups()
                if len(groups) == 1:
                    raw_fact = groups[0].strip()
                    key = raw_fact[:40]
                    return cls.add_memory(user_id, key=key, value=raw_fact, category="fact")
                elif len(groups) == 2:
                    k, v = groups[0].strip(), groups[1].strip()
                    return cls.add_memory(user_id, key=k, value=v, category="preference")
        return None

    @classmethod
    def format_memory_context(cls, user_id: int | str) -> str:
        """Format relevant user memories into a concise prompt inject."""
        if not user_id:
            return ""

        memories = cls.get_memories(user_id)
        if not memories:
            return ""

        lines = [f"- {m.key}: {m.value}" for m in memories[:15]]
        return (
            "\n[User Profile & Preferences]\n"
            + "\n".join(lines)
            + "\nUse these preferences naturally to tailor your response without explicitly announcing that you read them unless asked.\n"
        )


user_memory_service = UserMemoryService()
