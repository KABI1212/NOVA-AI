from __future__ import annotations

import uuid

from models.base import Field, MongoModel, utc_now


class FileRecord(MongoModel):
    __collection__ = "files"
    __primary_field__ = "id"

    id = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id = Field(default=None)
    session_id = Field(default="")
    conversation_id = Field(default=None)
    filename = Field(default="")
    original_name = Field(default="")
    mime_type = Field(default="")
    extension = Field(default="")
    size = Field(default=0)
    storage_path = Field(default="")
    extracted_text = Field(default=None)
    metadata = Field(default_factory=dict)
    chunk_count = Field(default=0)
    status = Field(default="uploaded")
    preview_text = Field(default="")
    error = Field(default=None)
    created_at = Field(default_factory=utc_now)
    updated_at = Field(default_factory=utc_now)

    def __repr__(self) -> str:
        return f"<FileRecord {self.original_name or self.filename}>"
