from __future__ import annotations

from models.base import Field, MongoModel, utc_now


class AuthSession(MongoModel):
    __collection__ = "auth_sessions"
    __primary_field__ = "id"
    __auto_id__ = "counter"

    id = Field(default=None)
    user_id = Field(default=None)
    refresh_token_hash = Field(default="")
    csrf_token_hash = Field(default="")
    user_agent = Field(default="")
    ip_address = Field(default="")
    created_at = Field(default_factory=utc_now)
    updated_at = Field(default_factory=utc_now)
    last_used_at = Field(default=None)
    expires_at = Field(default=None)
    revoked_at = Field(default=None)
    revoked_reason = Field(default="")
    rotated_from_session_id = Field(default=None)

    def __repr__(self) -> str:
        return f"<AuthSession user_id={self.user_id} id={self.id}>"
