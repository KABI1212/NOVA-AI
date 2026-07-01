from __future__ import annotations

from models.base import Field, MongoModel, utc_now


class AuthAuditEvent(MongoModel):
    __collection__ = "auth_audit_events"
    __primary_field__ = "id"
    __auto_id__ = "counter"

    id = Field(default=None)
    user_id = Field(default=None)
    session_id = Field(default=None)
    event = Field(default="")
    ip_address = Field(default="")
    user_agent = Field(default="")
    reason = Field(default="")
    created_at = Field(default_factory=utc_now)

