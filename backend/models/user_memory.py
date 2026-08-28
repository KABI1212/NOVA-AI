from __future__ import annotations

from models.base import Field, MongoModel, utc_now


class UserMemory(MongoModel):
    """Persistent user memory for preferences, facts, and customized assistant behavior."""
    __collection__ = "user_memories"
    __primary_field__ = "id"
    __auto_id__ = "counter"

    id = Field(default=None)
    user_id = Field(default=None)
    category = Field(default="preference")  # preference, fact, instruction, learning
    key = Field(default="")
    value = Field(default="")
    is_active = Field(default=True)
    created_at = Field(default_factory=utc_now)
    updated_at = Field(default_factory=utc_now)

    def __repr__(self) -> str:
        return f"<UserMemory {self.user_id}:{self.category}:{self.key}>"
