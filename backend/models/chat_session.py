from __future__ import annotations

from models.base import Field, MongoModel, utc_now


class ChatSession(MongoModel):
    __collection__ = "chat_sessions"
    __primary_field__ = "id"

    id = Field(default="")
    user_id = Field(default=None)
    conversation_id = Field(default=None)
    file_ids = Field(default_factory=list)
    last_active_at = Field(default_factory=utc_now)
    created_at = Field(default_factory=utc_now)
    updated_at = Field(default_factory=utc_now)

    def __repr__(self) -> str:
        return f"<ChatSession {self.id}>"
