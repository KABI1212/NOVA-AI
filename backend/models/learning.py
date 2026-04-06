from __future__ import annotations

from models.base import Field, MongoModel, utc_now


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
    created_at = Field(default_factory=utc_now)
    updated_at = Field(default_factory=utc_now)

    def __repr__(self) -> str:
        return f"<LearningProgress {self.topic}>"
