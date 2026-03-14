from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from models.user import User
from services.ai_service import ai_service
from utils.dependencies import get_current_user
from config.settings import settings

router = APIRouter(prefix="/api/image", tags=["Image Generator"])


class ImageRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    n: int = 1


@router.post("/")
async def generate_image(
    request: ImageRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate images from a text prompt"""
    if not settings.OPENAI_API_KEY:
        return {"error": "OpenAI API key not configured. Image generation unavailable."}
    if request.n < 1 or request.n > 4:
        raise HTTPException(status_code=400, detail="n must be between 1 and 4")

    images = await ai_service.generate_image(
        request.prompt,
        request.size,
        request.n
    )

    return {
        "prompt": request.prompt,
        "size": request.size,
        "images": images
    }


@router.get("/suggestions")
async def image_suggestions(
    current_user: User = Depends(get_current_user)
):
    return {
        "suggestions": [
            "A futuristic city at sunset",
            "A robot reading a book",
            "A neon-lit cyberpunk alley",
            "A serene mountain lake at dawn",
            "A vintage space station interior",
            "A dragon flying over a medieval castle",
            "An astronaut riding a horse on Mars",
            "A cozy cabin in a snowy forest",
            "A watercolor painting of a lighthouse",
            "A cinematic portrait of a jazz musician"
        ]
    }
