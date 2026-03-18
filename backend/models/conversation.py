from sqlalchemy import Column, String, Boolean, DateTime, JSON, Text, ForeignKey, Integer
from sqlalchemy.sql import func
from config.database import Base
from sqlalchemy.orm import relationship
from pydantic import BaseModel
from typing import List
import uuid

class Conversation(Base):
    __tablename__ = "conversations"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    title        = Column(String(200), default="New Chat")
    messages     = Column(JSON, default=list)
    model        = Column(String(50), default="gpt-4")

    # Relationship to user
    user         = relationship("User", back_populates="conversations")

    # Share fields ← NEW
    is_shared    = Column(Boolean, default=False)
    share_id     = Column(String(12), unique=True, nullable=True)  # short public ID
    share_title  = Column(String(200), nullable=True)
    shared_at    = Column(DateTime, nullable=True)
    view_count   = Column(String, default="0")

    created_at   = Column(DateTime, server_default=func.now())
    updated_at   = Column(DateTime, onupdate=func.now())

# ── Pydantic schemas (used in routes) ────────────────────
class Message(BaseModel):
    role:    str
    content: str

class ConversationCreate(BaseModel):
    title:   str = "New Chat"
    model:   str = "gpt-4"

class ConversationResponse(BaseModel):
    id:         str
    title:      str
    model:      str
    messages:   List[dict] = []
    created_at: str = None

    class Config:
        from_attributes = True
