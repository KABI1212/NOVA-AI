from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from config.database import get_db
from models.conversation import Conversation
from services.conversation_store import conversation_message_count, serialize_conversation_messages
from utils.dependencies import get_current_user
from sqlalchemy.orm import Session
from datetime import datetime
import random
import string

router = APIRouter(prefix="/share", tags=["share"])

# ── Generate short share ID ───────────────────────────────
def generate_share_id(length: int = 10) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))

# ── Request models ────────────────────────────────────────
class ShareRequest(BaseModel):
    conversation_id: str
    share_title:     str = None

class UpdateShareRequest(BaseModel):
    is_shared:   bool
    share_title: str = None

# ── Create / enable share link ────────────────────────────
@router.post("/create")
async def create_share(
    request: ShareRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    convo = db.query(Conversation).filter(
        Conversation.id      == request.conversation_id,
        Conversation.user_id == user.id
    ).first()

    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    if conversation_message_count(db, convo) == 0:
        raise HTTPException(status_code=400, detail="Cannot share an empty conversation.")

    # Generate share ID if not exists
    if not convo.share_id:
        while True:
            share_id = generate_share_id()
            existing = db.query(Conversation).filter(
                Conversation.share_id == share_id
            ).first()
            if not existing:
                break
        convo.share_id = share_id

    convo.is_shared   = True
    convo.share_title = request.share_title or convo.title
    convo.shared_at   = datetime.utcnow()

    db.commit()
    db.refresh(convo)

    return {
        "share_id":   convo.share_id,
        "share_url":  f"/share/{convo.share_id}",
        "share_title": convo.share_title,
        "is_shared":  True,
    }


# ── Disable share link ─────────────────────────────────────
@router.post("/disable/{conversation_id}")
async def disable_share(
    conversation_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    convo = db.query(Conversation).filter(
        Conversation.id      == conversation_id,
        Conversation.user_id == user.id
    ).first()

    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    convo.is_shared = False
    db.commit()

    return {"is_shared": False, "message": "Share link disabled."}


# ── Get share status ──────────────────────────────────────
@router.get("/status/{conversation_id}")
async def get_share_status(
    conversation_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    convo = db.query(Conversation).filter(
        Conversation.id      == conversation_id,
        Conversation.user_id == user.id
    ).first()

    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return {
        "is_shared":   convo.is_shared,
        "share_id":    convo.share_id,
        "share_url":   f"/share/{convo.share_id}" if convo.share_id else None,
        "share_title": convo.share_title,
        "shared_at":   convo.shared_at,
        "view_count":  convo.view_count,
    }


# ── Public: view shared conversation (NO auth needed) ─────
@router.get("/view/{share_id}")
async def view_shared(
    share_id: str,
    db: Session = Depends(get_db)
):
    convo = db.query(Conversation).filter(
        Conversation.share_id == share_id,
        Conversation.is_shared == True
    ).first()

    if not convo:
        raise HTTPException(
            status_code=404,
            detail="Shared conversation not found or link has been disabled."
        )

    # Increment view count
    convo.view_count = str(int(convo.view_count or 0) + 1)
    db.commit()

    # Return sanitized conversation (no user_id etc.)
    return {
        "share_id":    convo.share_id,
        "title":       convo.share_title or convo.title,
        "messages":    serialize_conversation_messages(db, convo),
        "model":       convo.model,
        "shared_at":   convo.shared_at,
        "view_count":  convo.view_count,
    }


# ── List user's shared conversations ─────────────────────
@router.get("/my-shares")
async def my_shares(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    convos = db.query(Conversation).filter(
        Conversation.user_id  == user.id,
        Conversation.is_shared == True
    ).order_by(Conversation.shared_at.desc()).all()

    return {
        "shares": [
            {
                "conversation_id": c.id,
                "share_id":        c.share_id,
                "share_url":       f"/share/{c.share_id}",
                "title":           c.share_title or c.title,
                "shared_at":       c.shared_at,
                "view_count":      c.view_count,
                "message_count":   conversation_message_count(db, c),
            }
            for c in convos
        ]
    }
