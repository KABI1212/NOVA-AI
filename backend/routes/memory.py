from __future__ import annotations

import logging
from typing import Any, List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status
from models.user import User
from services.user_memory_service import user_memory_service
from utils.dependencies import get_current_user

router = APIRouter(prefix="/api/memory", tags=["User Memory"])
logger = logging.getLogger(__name__)


class CreateMemoryRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=120)
    value: str = Field(..., min_length=1, max_length=1000)
    category: str = Field(default="preference", max_length=50)


class MemoryResponse(BaseModel):
    id: Any
    category: str
    key: str
    value: str
    is_active: bool
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None


@router.get("", response_model=List[MemoryResponse])
async def list_memories(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Retrieve all persistent memories for the authenticated user."""
    memories = user_memory_service.get_memories(current_user.id, category=category)
    return [
        MemoryResponse(
            id=m.id,
            category=m.category,
            key=m.key,
            value=m.value,
            is_active=m.is_active,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in memories
    ]


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: CreateMemoryRequest,
    current_user: User = Depends(get_current_user),
):
    """Create or update a persistent memory item."""
    memory = user_memory_service.add_memory(
        user_id=current_user.id,
        key=payload.key,
        value=payload.value,
        category=payload.category,
    )
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to save memory item.",
        )
    return MemoryResponse(
        id=memory.id,
        category=memory.category,
        key=memory.key,
        value=memory.value,
        is_active=memory.is_active,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.delete("/{memory_id}", status_code=status.HTTP_200_OK)
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a memory item."""
    success = user_memory_service.delete_memory(current_user.id, memory_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found or access denied.",
        )
    return {"status": "success", "message": "Memory deleted."}


@router.delete("", status_code=status.HTTP_200_OK)
async def clear_all_memories(
    current_user: User = Depends(get_current_user),
):
    """Clear all memories for the authenticated user."""
    count = user_memory_service.clear_all(current_user.id)
    return {"status": "success", "cleared_count": count}
