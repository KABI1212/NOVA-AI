from __future__ import annotations

from datetime import datetime

from models.base import Field, MongoModel


class LearningProgress(MongoModel):
    __collection__ = "learning_progress"
    __primary_field__ = "id"
    __auto_id__ = "counter"

    id = Field(default=None)
    user_id = Field(default=None)
    topic = Field(default="")
    roadmap = Field(default_factory=dict)
    completed_items = Field(default_factory=list)
    current_level = Field(default="beginner")
    notes = Field(default=None)
    is_active = Field(default=True)
    created_at = Field(default_factory=datetime.utcnow)
    updated_at = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<LearningProgress {self.topic}>"
