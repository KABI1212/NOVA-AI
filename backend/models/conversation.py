from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel

from models.base import Field, MongoModel


class Conversation(MongoModel):
    __collection__ = "conversations"
    __primary_field__ = "id"

    id = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id = Field(default=None)
    title = Field(default="New Chat")
    legacy_messages = Field(default_factory=list)
    model = Field(default="gpt-4")
    is_shared = Field(default=False)
    share_id = Field(default=None)
    share_title = Field(default=None)
    shared_at = Field(default=None)
    view_count = Field(default="0")
    created_at = Field(default_factory=datetime.utcnow)
    updated_at = Field(default_factory=datetime.utcnow)


class Message(BaseModel):
    role: str
    content: str


class ConversationCreate(BaseModel):
    title: str = "New Chat"
    model: str = "gpt-4"


class ConversationResponse(BaseModel):
    id: str
    title: str
    model: str
    messages: List[dict] = []
    created_at: str | None = None

    class Config:
        from_attributes = True
