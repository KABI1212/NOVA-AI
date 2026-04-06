from __future__ import annotations

from models.base import Field, MongoModel, utc_now


class ChatMessage(MongoModel):
    __collection__ = "messages"
    __primary_field__ = "id"
    __auto_id__ = "counter"

    id = Field(default=None)
    conversation_id = Field(default="")
    role = Field(default="assistant")
    content = Field(default="")
    meta = Field(default=None)
    created_at = Field(default_factory=utc_now)

    def __repr__(self) -> str:
        return f"<ChatMessage {self.id} {self.role}>"
