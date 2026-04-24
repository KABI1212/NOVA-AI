from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import AsyncOpenAI
from models.user import User
from services.ai_service import ai_service
from utils.dependencies import get_current_user
from config.settings import settings
import base64
import httpx
import io

router = APIRouter(prefix="/api/image", tags=["Image Generator"])


class ImageRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    n: int = 1


class ImageGenerateRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"
    style: str = "vivid"
    n: int = 1


class EditRequest(BaseModel):
    prompt: str
    image_b64: str


def _openai_client() -> AsyncOpenAI:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured.")
    return AsyncOpenAI(api_key=api_key)


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


@router.post("/generate")
async def generate_image_v3(
    request: ImageGenerateRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        prompt = (request.prompt or "").strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
        if len(prompt) > 4000:
            raise HTTPException(status_code=400, detail="Prompt too long. Max 4000 chars.")

        valid_sizes = ["1024x1024", "1792x1024", "1024x1792"]
        if request.size not in valid_sizes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid size. Choose from {valid_sizes}",
            )
        if request.quality not in {"standard", "hd"}:
            raise HTTPException(status_code=400, detail="Invalid quality.")
        if request.style not in {"vivid", "natural"}:
            raise HTTPException(status_code=400, detail="Invalid style.")

        client = _openai_client()
        response = await client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=request.size,
            quality=request.quality,
            style=request.style,
            n=1,
            response_format="url",
        )

        image_url = response.data[0].url
        revised_prompt = getattr(response.data[0], "revised_prompt", None)

        return {
            "url": image_url,
            "revised_prompt": revised_prompt,
            "size": request.size,
            "quality": request.quality,
            "style": request.style,
        }
    except HTTPException:
        raise
    except Exception as exc:
        error_msg = str(exc)
        if "content_policy_violation" in error_msg:
            raise HTTPException(
                status_code=400,
                detail="Prompt violates content policy. Please rephrase.",
            )
        if "billing" in error_msg.lower():
            raise HTTPException(status_code=402, detail="OpenAI billing issue.")
        if "rate_limit" in error_msg.lower():
            raise HTTPException(status_code=429, detail="Rate limit hit. Please wait.")
        raise HTTPException(status_code=500, detail=f"Image generation failed: {error_msg}")


@router.get("/proxy")
async def proxy_image(
    url: str,
    current_user: User = Depends(get_current_user)
):
    try:
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Invalid image URL.")
        async with httpx.AsyncClient(timeout=30) as http:
            res = await http.get(url)
            res.raise_for_status()
        return StreamingResponse(
            io.BytesIO(res.content),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image proxy failed: {str(exc)}")


@router.post("/variations")
async def image_variations(
    request: EditRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        if not request.image_b64:
            raise HTTPException(status_code=400, detail="Missing image data.")
        image_bytes = base64.b64decode(request.image_b64)
        image_file = io.BytesIO(image_bytes)
        image_file.name = "image.png"

        client = _openai_client()
        response = await client.images.create_variation(
            model="dall-e-2",
            image=image_file,
            n=1,
            size="1024x1024",
            response_format="url",
        )
        return {"url": response.data[0].url}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Variation failed: {str(exc)}")


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
