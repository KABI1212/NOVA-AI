from __future__ import annotations

from datetime import datetime

from models.base import Field, MongoModel


class User(MongoModel):
    __collection__ = "users"
    __primary_field__ = "id"
    __auto_id__ = "counter"

    id = Field(default=None)
    email = Field(default="")
    username = Field(default="")
    hashed_password = Field(default="")
    full_name = Field(default="")
    is_active = Field(default=True)
    is_verified = Field(default=False)
    created_at = Field(default_factory=datetime.utcnow)
    updated_at = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<User {self.username}>"
