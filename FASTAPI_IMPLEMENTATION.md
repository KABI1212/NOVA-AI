# 🚀 NOVA-AI FastAPI Implementation Guide

## Complete REST API Server Implementation

---

## Installation

```bash
pip install fastapi uvicorn sqlalchemy aiohttp python-dotenv
```

---

## FastAPI Server Implementation

```python
# nova_ai_api.py
"""
NOVA-AI REST API Server
FastAPI implementation for conversation and learning management
"""

from fastapi import FastAPI, HTTPException, Depends, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import Optional, List, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# 1. DATABASE SETUP
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nova_ai.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# 2. DATABASE MODELS
# ============================================================================

class ConversationDB(Base):
    """Database model for conversations"""
    __tablename__ = "conversations"
    
    conversation_id = Column(String, primary_key=True, index=True)
    title = Column(String, index=True)
    topic = Column(String, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    message_count = Column(Integer, default=0)

class MessageDB(Base):
    """Database model for messages"""
    __tablename__ = "messages"
    
    message_id = Column(String, primary_key=True, index=True)
    conversation_id = Column(String, index=True)
    role = Column(String)  # "user" or "assistant"
    content = Column(Text)
    model = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    sources = Column(String, nullable=True)  # JSON array as string
    created_at = Column(DateTime, default=datetime.utcnow)

class LearningDB(Base):
    """Database model for learning progress"""
    __tablename__ = "learning"
    
    learning_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    topic = Column(String)
    objective = Column(String)
    progress = Column(String, default="0%")
    completed_modules = Column(String, nullable=True)  # JSON array as string
    quiz_scores = Column(String, nullable=True)  # JSON array as string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# ============================================================================
# 3. PYDANTIC MODELS (Request/Response)
# ============================================================================

class ConversationCreate(BaseModel):
    """Create conversation request"""
    title: str = Field(..., min_length=1, max_length=200)
    topic: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    
    @validator('title')
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()

class ConversationUpdate(BaseModel):
    """Update conversation request"""
    title: Optional[str] = Field(None, max_length=200)
    topic: Optional[str] = Field(None, max_length=100)

class ConversationResponse(BaseModel):
    """Conversation response"""
    conversation_id: str
    title: str
    topic: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int
    
    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    """Create message request"""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)
    metadata: Optional[Dict[str, Any]] = None

class MessageResponse(BaseModel):
    """Message response"""
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
    model: Optional[str]
    confidence: Optional[float]
    sources: Optional[List[str]]
    
    class Config:
        from_attributes = True

class LearningCreate(BaseModel):
    """Create learning session request"""
    user_id: str = Field(..., min_length=1)
    topic: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)

class LearningUpdate(BaseModel):
    """Update learning progress request"""
    progress: Optional[str] = None
    completed_modules: Optional[List[str]] = None
    quiz_scores: Optional[List[Dict[str, Any]]] = None

class LearningResponse(BaseModel):
    """Learning progress response"""
    learning_id: int
    user_id: str
    topic: str
    objective: str
    progress: str
    created_at: datetime
    updated_at: datetime
    last_accessed: datetime
    completed_modules: Optional[List[str]]
    quiz_scores: Optional[List[Dict[str, Any]]]
    
    class Config:
        from_attributes = True

class ErrorResponse(BaseModel):
    """Error response"""
    status: str = "error"
    code: int
    detail: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ============================================================================
# 4. FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="NOVA-AI API",
    description="Multi-Model AI Analysis & Response System",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# 5. CONVERSATION ENDPOINTS
# ============================================================================

@app.post("/api/chat/conversations", response_model=ConversationResponse)
async def create_conversation(
    conversation: ConversationCreate,
    db: Session = Depends(get_db)
):
    """Create a new conversation"""
    import uuid
    
    conv_id = str(uuid.uuid4())
    db_conversation = ConversationDB(
        conversation_id=conv_id,
        title=conversation.title,
        topic=conversation.topic,
        description=conversation.description
    )
    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)
    
    return db_conversation

@app.get("/api/chat/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str = Path(..., description="Conversation ID"),
    db: Session = Depends(get_db)
):
    """Get conversation details"""
    conversation = db.query(ConversationDB).filter(
        ConversationDB.conversation_id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation

@app.put("/api/chat/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str = Path(..., description="Conversation ID"),
    update_data: ConversationUpdate = None,
    db: Session = Depends(get_db)
):
    """Update conversation"""
    conversation = db.query(ConversationDB).filter(
        ConversationDB.conversation_id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if update_data.title:
        conversation.title = update_data.title
    if update_data.topic:
        conversation.topic = update_data.topic
    
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conversation)
    
    return conversation

@app.delete("/api/chat/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str = Path(..., description="Conversation ID"),
    db: Session = Depends(get_db)
):
    """Delete conversation"""
    conversation = db.query(ConversationDB).filter(
        ConversationDB.conversation_id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Delete associated messages
    db.query(MessageDB).filter(
        MessageDB.conversation_id == conversation_id
    ).delete()
    
    db.delete(conversation)
    db.commit()
    
    return {"message": "Conversation deleted successfully"}

@app.get("/api/chat/conversations", response_model=Dict[str, Any])
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    topic: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """List conversations"""
    query = db.query(ConversationDB)
    
    if topic:
        query = query.filter(ConversationDB.topic == topic)
    
    total = query.count()
    conversations = query.offset(skip).limit(limit).all()
    
    return {
        "conversations": conversations,
        "total": total,
        "skip": skip,
        "limit": limit
    }

# ============================================================================
# 6. MESSAGE ENDPOINTS
# ============================================================================

@app.post("/api/chat/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def add_message(
    conversation_id: str = Path(..., description="Conversation ID"),
    message: MessageCreate = None,
    db: Session = Depends(get_db)
):
    """Add message to conversation"""
    import uuid
    import json
    
    # Verify conversation exists
    conversation = db.query(ConversationDB).filter(
        ConversationDB.conversation_id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    msg_id = str(uuid.uuid4())
    
    db_message = MessageDB(
        message_id=msg_id,
        conversation_id=conversation_id,
        role=message.role,
        content=message.content,
        model=message.metadata.get("model") if message.metadata else None,
        confidence=message.metadata.get("confidence") if message.metadata else None,
        sources=json.dumps(message.metadata.get("sources", [])) if message.metadata else None
    )
    
    db.add(db_message)
    
    # Update message count
    conversation.message_count += 1
    conversation.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_message)
    
    return db_message

@app.get("/api/chat/conversations/{conversation_id}/messages", response_model=Dict[str, Any])
async def get_messages(
    conversation_id: str = Path(..., description="Conversation ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get message history"""
    total = db.query(MessageDB).filter(
        MessageDB.conversation_id == conversation_id
    ).count()
    
    messages = db.query(MessageDB).filter(
        MessageDB.conversation_id == conversation_id
    ).order_by(MessageDB.created_at).offset(offset).limit(limit).all()
    
    return {
        "messages": messages,
        "total_count": total
    }

# ============================================================================
# 7. LEARNING ENDPOINTS
# ============================================================================

@app.post("/api/learning", response_model=LearningResponse)
async def create_learning_session(
    learning: LearningCreate,
    db: Session = Depends(get_db)
):
    """Create learning session"""
    db_learning = LearningDB(
        user_id=learning.user_id,
        topic=learning.topic,
        objective=learning.objective
    )
    db.add(db_learning)
    db.commit()
    db.refresh(db_learning)
    
    return db_learning

@app.get("/api/learning/{learning_id}", response_model=LearningResponse)
async def get_learning_progress(
    learning_id: int = Path(..., description="Learning ID"),
    db: Session = Depends(get_db)
):
    """Get learning progress"""
    learning = db.query(LearningDB).filter(
        LearningDB.learning_id == learning_id
    ).first()
    
    if not learning:
        raise HTTPException(status_code=404, detail="Learning session not found")
    
    return learning

@app.put("/api/learning/{learning_id}", response_model=LearningResponse)
async def update_learning_progress(
    learning_id: int = Path(..., description="Learning ID"),
    update_data: LearningUpdate = None,
    db: Session = Depends(get_db)
):
    """Update learning progress"""
    import json
    
    learning = db.query(LearningDB).filter(
        LearningDB.learning_id == learning_id
    ).first()
    
    if not learning:
        raise HTTPException(status_code=404, detail="Learning session not found")
    
    if update_data.progress:
        learning.progress = update_data.progress
    if update_data.completed_modules:
        learning.completed_modules = json.dumps(update_data.completed_modules)
    if update_data.quiz_scores:
        learning.quiz_scores = json.dumps(update_data.quiz_scores)
    
    learning.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(learning)
    
    return learning

@app.delete("/api/learning/{learning_id}")
async def delete_learning_progress(
    learning_id: int = Path(..., description="Learning ID"),
    db: Session = Depends(get_db)
):
    """Delete learning progress"""
    learning = db.query(LearningDB).filter(
        LearningDB.learning_id == learning_id
    ).first()
    
    if not learning:
        raise HTTPException(status_code=404, detail="Learning session not found")
    
    db.delete(learning)
    db.commit()
    
    return {"message": "Learning progress deleted successfully"}

@app.get("/api/learning", response_model=Dict[str, Any])
async def list_learning_sessions(
    user_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List learning sessions"""
    query = db.query(LearningDB)
    
    if user_id:
        query = query.filter(LearningDB.user_id == user_id)
    
    total = query.count()
    sessions = query.offset(skip).limit(limit).all()
    
    return {
        "learning_sessions": sessions,
        "total": total
    }

# ============================================================================
# 8. HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "NOVA-AI API",
        "timestamp": datetime.utcnow()
    }

# ============================================================================
# 9. MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )
```

---

## Running the Server

```bash
# Development
python nova_ai_api.py

# Or with uvicorn directly
uvicorn nova_ai_api:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn nova_ai_api:app --workers 4 --host 0.0.0.0 --port 8000
```

---

## Environment Configuration

Create `.env` file:

```
DATABASE_URL=sqlite:///./nova_ai.db
HOST=0.0.0.0
PORT=8000
DEBUG=true
API_KEY=your_secret_key_here
```

---

## Testing Endpoints

### Using curl

```bash
# Create conversation
curl -X POST http://localhost:8000/api/chat/conversations \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","topic":"AI"}'

# Get conversation
curl http://localhost:8000/api/chat/conversations/{conversation_id}

# Delete conversation
curl -X DELETE http://localhost:8000/api/chat/conversations/{conversation_id}

# Create learning session
curl -X POST http://localhost:8000/api/learning \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user1","topic":"Python","objective":"Learn async"}'

# Get learning progress
curl http://localhost:8000/api/learning/{learning_id}
```

### Using Python requests

```python
import requests

BASE_URL = "http://localhost:8000/api"

# Create conversation
response = requests.post(
    f"{BASE_URL}/chat/conversations",
    json={"title":"Test","topic":"AI"}
)
conv_id = response.json()["conversation_id"]

# Add message
requests.post(
    f"{BASE_URL}/chat/conversations/{conv_id}/messages",
    json={
        "role": "user",
        "content": "Hello!",
        "metadata": {"model": "claude"}
    }
)

# Get messages
messages = requests.get(
    f"{BASE_URL}/chat/conversations/{conv_id}/messages"
)
print(messages.json())
```

---

## Summary

This FastAPI implementation provides:

✅ **Full REST API** - All endpoints documented above
✅ **Database Persistence** - SQLite (or any SQLAlchemy DB)
✅ **Request Validation** - Pydantic models
✅ **Error Handling** - Proper HTTP status codes
✅ **CORS Support** - Cross-origin requests
✅ **Async/Await** - High performance
✅ **Auto Documentation** - Swagger UI at /docs

**Ready for production deployment!**
