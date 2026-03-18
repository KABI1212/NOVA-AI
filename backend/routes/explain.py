from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from models.user import User
from services.ai_service import ai_service
from utils.dependencies import get_current_user

router = APIRouter(prefix="/api/explain", tags=["Explanation"])


class ExplainRequest(BaseModel):
    prompt: str
    mode: str = "deep"  # deep, safe, knowledge, summary
    audience: str = "general"
    detail: str = "detailed"


@router.post("")
@router.post("/")
async def explain(
    request: ExplainRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate deep explanations, safe reasoning answers, or knowledge responses"""
    allowed_modes = {"deep", "safe", "knowledge", "summary"}
    if request.mode.lower() not in allowed_modes:
        raise HTTPException(status_code=400, detail="Invalid explanation mode")

    explanation = await ai_service.generate_explanation(
        request.prompt,
        request.mode,
        request.audience,
        request.detail
    )

    return {
        "mode": request.mode,
        "explanation": explanation
    }
