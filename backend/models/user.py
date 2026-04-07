from __future__ import annotations

from models.base import Field, MongoModel, utc_now


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
    login_otp_code_hash = Field(default=None)
    login_otp_expires_at = Field(default=None)
    login_otp_sent_at = Field(default=None)
    login_otp_challenge_hash = Field(default=None)
    created_at = Field(default_factory=utc_now)
    updated_at = Field(default_factory=utc_now)

    def __repr__(self) -> str:
        return f"<User {self.username}>"
