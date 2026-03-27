from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, List, Optional
try:
    from sqlalchemy.orm import Session
except ImportError:
    Session = Any
from config.database import get_db
from models.user import User
from models.learning import LearningProgress
from services.ai_service import ai_service
from utils.dependencies import get_current_user

router = APIRouter(prefix="/api/learning", tags=["Learning Assistant"])


class RoadmapRequest(BaseModel):
    topic: str
    level: str = "beginner"


class UpdateProgressRequest(BaseModel):
    learning_id: int
    completed_item: str


class LearningProgressResponse(BaseModel):
    id: int
    topic: str
    current_level: str
    roadmap: dict
    completed_items: list
    created_at: str


@router.post("/roadmap")
async def generate_roadmap(
    request: RoadmapRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a learning roadmap for a topic"""

    # Check if roadmap already exists
    existing = db.query(LearningProgress).filter(
        LearningProgress.user_id == current_user.id,
        LearningProgress.topic == request.topic,
        LearningProgress.is_active == True
    ).first()

    if existing:
        return {
            "id": existing.id,
            "topic": existing.topic,
            "current_level": existing.current_level,
            "roadmap": existing.roadmap,
            "completed_items": existing.completed_items,
            "created_at": existing.created_at.isoformat(),
            "message": "Roadmap already exists"
        }

    # Generate new roadmap
    roadmap_data = await ai_service.generate_learning_roadmap(
        request.topic,
        request.level
    )

    # Save to database
    learning = LearningProgress(
        user_id=current_user.id,
        topic=request.topic,
        current_level=request.level,
        roadmap=roadmap_data,
        completed_items=[]
    )

    db.add(learning)
    db.commit()
    db.refresh(learning)

    return {
        "id": learning.id,
        "topic": learning.topic,
        "current_level": learning.current_level,
        "roadmap": learning.roadmap,
        "completed_items": learning.completed_items,
        "created_at": learning.created_at.isoformat()
    }


@router.get("/", response_model=List[LearningProgressResponse])
async def get_learning_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all learning progress for current user"""
    progress = db.query(LearningProgress).filter(
        LearningProgress.user_id == current_user.id,
        LearningProgress.is_active == True
    ).order_by(LearningProgress.updated_at.desc()).all()

    return [
        {
            "id": p.id,
            "topic": p.topic,
            "current_level": p.current_level,
            "roadmap": p.roadmap,
            "completed_items": p.completed_items,
            "created_at": p.created_at.isoformat()
        }
        for p in progress
    ]


@router.post("/progress")
async def update_progress(
    request: UpdateProgressRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark an item as completed in the learning roadmap"""
    learning = db.query(LearningProgress).filter(
        LearningProgress.id == request.learning_id,
        LearningProgress.user_id == current_user.id
    ).first()

    if not learning:
        raise HTTPException(status_code=404, detail="Learning progress not found")

    # Add completed item if not already there
    if request.completed_item not in learning.completed_items:
        learning.completed_items.append(request.completed_item)
        db.commit()
        db.refresh(learning)

    return {
        "id": learning.id,
        "topic": learning.topic,
        "completed_items": learning.completed_items,
        "message": "Progress updated successfully"
    }


@router.delete("/{learning_id}")
async def delete_learning_progress(
    learning_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a learning progress"""
    learning = db.query(LearningProgress).filter(
        LearningProgress.id == learning_id,
        LearningProgress.user_id == current_user.id
    ).first()

    if not learning:
        raise HTTPException(status_code=404, detail="Learning progress not found")

    learning.is_active = False
    db.commit()

    return {"message": "Learning progress deleted successfully"}
