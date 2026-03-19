import uuid
from typing import List

from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from config.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), default="New Chat")
    legacy_messages = Column("messages", MutableList.as_mutable(JSON), default=list)
    model = Column(String(50), default="gpt-4")

    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    is_shared = Column(Boolean, default=False)
    share_id = Column(String(12), unique=True, nullable=True)
    share_title = Column(String(200), nullable=True)
    shared_at = Column(DateTime, nullable=True)
    view_count = Column(String, default="0")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class Message(BaseModel):
    role: str
    content: str


class ConversationCreate(BaseModel):
    title: str = "New Chat"
    model: str = "gpt-4"


class ConversationResponse(BaseModel):
    id: str
    title: str
    model: str
    messages: List[dict] = []
    created_at: str | None = None

    class Config:
        from_attributes = True


from models.message import ChatMessage  # noqa: E402,F401
