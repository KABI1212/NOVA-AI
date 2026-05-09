from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from config.database import MongoSession
from models.chat import ChatMessage
from models.conversation import Conversation


def _message_meta(payload: dict) -> Optional[dict]:
    meta = payload.get("meta")
    if isinstance(meta, dict):
        meta = dict(meta)
    else:
        meta = None

    images = payload.get("images")
    if images:
        meta = meta or {}
        meta.setdefault("images", images)

    return meta


def _message_query(db: MongoSession, conversation: Conversation):
    return db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation.id
    ).order_by(ChatMessage.created_at.asc())


def ensure_conversation_messages(db: MongoSession, conversation: Conversation) -> List[ChatMessage]:
    existing_messages = _message_query(db, conversation).all()
    if existing_messages:
        return existing_messages

    legacy_messages = list(conversation.legacy_messages or [])
    if not legacy_messages:
        return []

    base_time = conversation.created_at or datetime.utcnow()
    migrated_messages: list[ChatMessage] = []
    for index, payload in enumerate(legacy_messages):
        message = ChatMessage(
            conversation_id=conversation.id,
            role=payload.get("role") or "assistant",
            content=payload.get("content") or "",
            meta=_message_meta(payload),
            created_at=base_time + timedelta(microseconds=index),
        )
        db.add(message)
        migrated_messages.append(message)

    conversation.legacy_messages = []
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.commit()
    for message in migrated_messages:
        db.refresh(message)
    db.refresh(conversation)
    return _message_query(db, conversation).all()


def append_conversation_message(
    db: MongoSession,
    conversation: Conversation,
    role: str,
    content: str,
    meta: Optional[dict] = None,
) -> ChatMessage:
    ensure_conversation_messages(db, conversation)
    message = ChatMessage(
        conversation_id=conversation.id,
        role=role,
        content=content,
        meta=meta,
    )
    db.add(message)
    return message


def prune_conversation_from_message(
    db: MongoSession,
    conversation: Conversation,
    message_id: str | int | None,
) -> bool:
    if message_id is None:
        return False

    messages = ensure_conversation_messages(db, conversation)
    target_index = next(
        (
            index
            for index, message in enumerate(messages)
            if str(message.id) == str(message_id)
        ),
        None,
    )
    if target_index is None:
        return False

    for message in messages[target_index:]:
        db.delete(message)
    return True


def save_conversation(db: MongoSession, conversation: Conversation) -> Conversation:
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def history_from_conversation(
    db: MongoSession,
    conversation: Conversation,
    limit: Optional[int] = None,
) -> List[dict]:
    messages = ensure_conversation_messages(db, conversation)
    if limit:
        messages = messages[-limit:]

    return [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in messages
    ]


def serialize_message(message: ChatMessage) -> dict:
    meta = message.meta if isinstance(message.meta, dict) else None
    images = (meta or {}).get("images")
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "role": message.role,
        "content": message.content,
        "images": images,
        "meta": meta,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def serialize_conversation_messages(db: MongoSession, conversation: Conversation) -> List[dict]:
    return [serialize_message(message) for message in ensure_conversation_messages(db, conversation)]


def conversation_message_count(db: MongoSession, conversation: Conversation) -> int:
    return len(ensure_conversation_messages(db, conversation))
