from fastapi import APIRouter, Depends, UploadFile, File
from typing import Any
try:
    from sqlalchemy.orm import Session
except ImportError:
    Session = Any
from config.database import get_db
from models.user import User
from utils.dependencies import get_current_user

from routes.chat import chat as chat_handler, ChatRequest, get_conversations
from routes.image import generate_image, ImageRequest
from routes.document import upload_document

router = APIRouter(tags=["Compat"])


@router.post("/chat")
async def chat_alias(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return await chat_handler(request, current_user, db)


@router.get("/chat-history")
async def chat_history_alias(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return await get_conversations(current_user, db)


@router.post("/generate-image")
async def generate_image_alias(
    request: ImageRequest,
    current_user: User = Depends(get_current_user)
):
    return await generate_image(request, current_user)


@router.post("/upload-document")
async def upload_document_alias(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return await upload_document(file, current_user, db)
