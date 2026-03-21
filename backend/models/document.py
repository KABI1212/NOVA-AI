from __future__ import annotations

from datetime import datetime

from models.base import Field, MongoModel


class Document(MongoModel):
    __collection__ = "documents"
    __primary_field__ = "id"
    __auto_id__ = "counter"

    id = Field(default=None)
    user_id = Field(default=None)
    filename = Field(default="")
    file_path = Field(default="")
    file_type = Field(default="")
    file_size = Field(default=0)
    text_content = Field(default=None)
    summary = Field(default=None)
    is_processed = Field(default=False)
    created_at = Field(default_factory=datetime.utcnow)
    updated_at = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Document {self.filename}>"
