from __future__ import annotations

import logging
from datetime import datetime

from config.settings import settings
from models.conversation import Conversation
from services.ai_service import ai_service
from services.conversation_store import ensure_conversation_messages

logger = logging.getLogger(__name__)


def build_summary_history_message(conversation: Conversation) -> dict | None:
    summary = str(getattr(conversation, "context_summary", "") or "").strip()
    if not summary:
        return None
    return {
        "role": "system",
        "content": (
            "Conversation memory for follow-up answers. Use it only as established context and "
            "prefer newer explicit user messages if they conflict.\n"
            f"{summary}"
        ),
    }


def _should_refresh_summary(conversation: Conversation, message_count: int) -> bool:
    if message_count < settings.CONVERSATION_SUMMARY_MIN_MESSAGES:
        return False

    previous_count = int(getattr(conversation, "context_summary_message_count", 0) or 0)
    if not str(getattr(conversation, "context_summary", "") or "").strip():
        return True

    return (
        message_count - previous_count
    ) >= settings.CONVERSATION_SUMMARY_REFRESH_INTERVAL


def _conversation_transcript(db, conversation: Conversation) -> str:
    messages = ensure_conversation_messages(db, conversation)
    recent_messages = messages[-settings.CONVERSATION_SUMMARY_RECENT_MESSAGES :]
    lines: list[str] = []
    for message in recent_messages:
        content = " ".join((message.content or "").split()).strip()
        if not content:
            continue
        role = "User" if message.role == "user" else "Assistant"
        lines.append(f"{role}: {content[:900]}")
    return "\n".join(lines)


async def refresh_conversation_summary(db, conversation: Conversation) -> Conversation:
    messages = ensure_conversation_messages(db, conversation)
    message_count = len(messages)
    if not _should_refresh_summary(conversation, message_count):
        return conversation

    transcript = _conversation_transcript(db, conversation)
    if not transcript:
        return conversation

    existing_summary = (
        str(getattr(conversation, "context_summary", "") or "").strip() or "None"
    )
    prompt_messages = [
        {
            "role": "system",
            "content": (
                "You are maintaining compact memory for an AI assistant. Summarize only facts supported by "
                "the conversation. Keep it under 220 words. Use short bullet points with these sections when "
                "relevant: Goals, Constraints, Preferences, Key facts, Open threads."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Existing memory:\n{existing_summary}\n\n"
                f"Recent conversation:\n{transcript}\n\n"
                "Return the refreshed memory only."
            ),
        },
    ]

    try:
        chunks: list[str] = []
        async for chunk in ai_service.chat_completion(
            prompt_messages,
            stream=False,
            temperature=0.2,
            max_tokens=320,
        ):
            chunks.append(chunk)
        summary = "".join(chunks).strip()
    except Exception as exc:
        logger.warning(
            "conversation_summary_refresh_failed conversation_id=%s error=%s",
            conversation.id,
            exc,
        )
        return conversation

    if not summary:
        return conversation

    conversation.context_summary = summary[:2000]
    conversation.context_summary_message_count = message_count
    conversation.context_summary_updated_at = datetime.utcnow()
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation
