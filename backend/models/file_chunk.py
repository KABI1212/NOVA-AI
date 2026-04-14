from __future__ import annotations

import uuid

from models.base import Field, MongoModel, utc_now


class FileChunk(MongoModel):
    __collection__ = "file_chunks"
    __primary_field__ = "id"

    id = Field(default_factory=lambda: uuid.uuid4().hex)
    file_id = Field(default="")
    user_id = Field(default=None)
    chunk_index = Field(default=0)
    text = Field(default="")
    embedding = Field(default=None)
    page_number = Field(default=None)
    sheet_name = Field(default=None)
    section_title = Field(default=None)
    language = Field(default=None)
    token_count = Field(default=0)
    created_at = Field(default_factory=utc_now)

    def __repr__(self) -> str:
        return f"<FileChunk {self.file_id}:{self.chunk_index}>"
