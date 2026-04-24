import base64
import io
import ipaddress
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from models.user import User
from services.ai_service import ai_service
from utils.dependencies import get_current_user
from utils.rate_limit import enforce_image_rate_limit

router = APIRouter(prefix="/api/image", tags=["Image Generator"])
_IMAGE_PROXY_MAX_BYTES = 8 * 1024 * 1024
_IMAGE_PROXY_TIMEOUT_SECONDS = 30


def _is_private_or_local_host(hostname: str) -> bool:
    normalized = str(hostname or "").strip().strip("[]").rstrip(".").lower()
    if not normalized:
        return True
    if normalized in {"localhost", "0.0.0.0", "::1"}:
        return True
    if normalized.endswith(".localhost") or normalized.endswith(".local"):
        return True

    try:
        ip_address = ipaddress.ip_address(normalized)
    except ValueError:
        return False

    return (
        ip_address.is_private
        or ip_address.is_loopback
        or ip_address.is_link_local
        or ip_address.is_multicast
        or ip_address.is_reserved
        or ip_address.is_unspecified
    )


def _validate_proxy_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())

    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Invalid image URL.")
    if not parsed.netloc or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Invalid image URL.")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Image URLs cannot contain credentials.")
    if _is_private_or_local_host(parsed.hostname):
        raise HTTPException(
            status_code=400,
            detail="Private, local, and loopback image hosts are not allowed.",
        )

    return parsed.geturl()


def _validate_image_content_type(content_type: str) -> str:
    media_type = str(content_type or "").split(";", 1)[0].strip().lower()
    if not media_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="URL did not return an image.")
    return media_type or "image/png"


async def _fetch_proxy_image(url: str) -> tuple[bytes, str]:
    validated_url = _validate_proxy_url(url)

    async with httpx.AsyncClient(
        timeout=_IMAGE_PROXY_TIMEOUT_SECONDS,
        follow_redirects=False,
    ) as http:
        async with http.stream("GET", validated_url) as res:
            if 300 <= res.status_code < 400:
                raise HTTPException(
                    status_code=400,
                    detail="Redirecting image URLs are not supported.",
                )
            res.raise_for_status()

            content_type = _validate_image_content_type(res.headers.get("content-type", ""))
            raw_content_length = res.headers.get("content-length")
            if raw_content_length:
                try:
                    if int(raw_content_length) > _IMAGE_PROXY_MAX_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail="Image is too large to proxy.",
                        )
                except ValueError:
                    pass

            chunks: list[bytes] = []
            total_bytes = 0
            async for chunk in res.aiter_bytes():
                total_bytes += len(chunk)
                if total_bytes > _IMAGE_PROXY_MAX_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Image is too large to proxy.",
                    )
                chunks.append(chunk)

    return b"".join(chunks), content_type


def _raise_image_http_error(exc: Exception) -> None:
    error_msg = str(exc or "").strip()
    lowered = error_msg.lower()

    if lowered.startswith("all image providers failed."):
        raise HTTPException(status_code=503, detail=error_msg)
    if "user not found" in lowered or "model not found" in lowered or "no such user" in lowered:
        raise HTTPException(
            status_code=503,
            detail=(
                "The selected image provider could not use the configured account or model. "
                "Switch to Auto, Gemini, or ChatGPT, or update the OpenRouter image model."
            ),
        )
    if "content_policy_violation" in lowered or "content policy" in lowered:
        raise HTTPException(
            status_code=400,
            detail="Prompt violates content policy. Please rephrase.",
        )
    if (
        "billing_hard_limit_reached" in lowered
        or "billing hard limit" in lowered
        or "insufficient credits" in lowered
        or "not enough credits" in lowered
        or "requires more credits" in lowered
        or "can only afford" in lowered
        or "billing" in lowered
    ):
        raise HTTPException(
            status_code=402,
            detail="Image generation is blocked by provider billing limits. Please add billing or increase the limit, then try again.",
        )
    if "resource_exhausted" in lowered or "quota exceeded" in lowered or "rate limit" in lowered or "please retry in" in lowered:
        raise HTTPException(
            status_code=429,
            detail="Image generation quota is exhausted for the current provider. Please wait, top up the quota, or switch providers.",
        )
    if "provider not configured" in lowered or "no supported image provider" in lowered:
        raise HTTPException(
            status_code=503,
            detail="No working image provider is configured right now.",
        )

    raise HTTPException(status_code=500, detail=f"Image generation failed: {error_msg or 'Unknown error'}")


class ImageRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    n: int = 1
    quality: str = "standard"
    style: str = "vivid"
    provider: str = "auto"
    enhance_prompt: bool = True
    prompt_target: str = "auto"


class ImageGenerateRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"
    style: str = "vivid"
    n: int = 1
    provider: str = "auto"
    enhance_prompt: bool = True
    prompt_target: str = "auto"


class ImagePromptRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"
    style: str = "vivid"
    provider: str = "auto"
    prompt_target: str = "auto"


class EditRequest(BaseModel):
    prompt: str = ""
    image_b64: str
    mime_type: str = "image/png"


@router.post("/")
async def generate_image(
    http_request: Request,
    request: ImageRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate images from a text prompt"""
    try:
        prompt = " ".join((request.prompt or "").split()).strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
        if len(prompt) > 4000:
            raise HTTPException(status_code=400, detail="Prompt too long. Max 4000 chars.")
        if request.n < 1 or request.n > 4:
            raise HTTPException(status_code=400, detail="n must be between 1 and 4")
        await enforce_image_rate_limit(http_request, current_user, cost=request.n)

        result = await ai_service.generate_image_result(
            prompt,
            size=request.size,
            n=request.n,
            quality=request.quality,
            style=request.style,
            provider=request.provider,
            enhance_prompt=request.enhance_prompt,
            prompt_target=request.prompt_target,
            raise_on_error=True,
        )
        images = result.get("images") or []
        if not images:
            raise HTTPException(
                status_code=502,
                detail="Image generation failed for that prompt. Please try again with a clearer prompt.",
            )

        return {
            "prompt": result.get("prompt") or prompt,
            "revised_prompt": result.get("revised_prompt") or prompt,
            "size": request.size,
            "quality": request.quality,
            "style": request.style,
            "provider": result.get("provider") or request.provider,
            "provider_label": result.get("provider_label"),
            "images": images,
            "url": images[0],
        }
    except HTTPException:
        raise
    except Exception as exc:
        _raise_image_http_error(exc)


@router.post("/generate")
async def generate_image_v3(
    http_request: Request,
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
        if request.n < 1 or request.n > 4:
            raise HTTPException(status_code=400, detail="n must be between 1 and 4")
        if request.quality not in {"standard", "hd"}:
            raise HTTPException(status_code=400, detail="Invalid quality.")
        if request.style not in {"vivid", "natural"}:
            raise HTTPException(status_code=400, detail="Invalid style.")
        if request.provider not in {"auto", "openai", "chatgpt", "google", "gemini", "openrouter"}:
            raise HTTPException(status_code=400, detail="Invalid provider.")
        if request.prompt_target not in {"auto", "chatgpt", "gemini", "canva"}:
            raise HTTPException(status_code=400, detail="Invalid prompt target.")

        await enforce_image_rate_limit(http_request, current_user, cost=request.n)
        result = await ai_service.generate_image_result(
            prompt,
            size=request.size,
            n=request.n,
            quality=request.quality,
            style=request.style,
            provider=request.provider,
            enhance_prompt=bool(request.enhance_prompt),
            prompt_target=request.prompt_target,
            raise_on_error=True,
        )
        images = result.get("images") or []
        if not images:
            raise HTTPException(
                status_code=502,
                detail="Image generation failed for that prompt. Please try again with a clearer prompt.",
            )

        return {
            "url": images[0],
            "images": images,
            "prompt": result.get("prompt") or prompt,
            "revised_prompt": result.get("revised_prompt") or prompt,
            "size": request.size,
            "quality": request.quality,
            "style": request.style,
            "provider": result.get("provider") or request.provider,
            "provider_label": result.get("provider_label"),
            "prompt_target": request.prompt_target,
        }
    except HTTPException:
        raise
    except Exception as exc:
        _raise_image_http_error(exc)


@router.post("/prompt")
async def optimize_image_prompt(
    request: ImagePromptRequest,
    current_user: User = Depends(get_current_user),
):
    prompt = " ".join((request.prompt or "").split()).strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    if len(prompt) > 4000:
        raise HTTPException(status_code=400, detail="Prompt too long. Max 4000 chars.")
    if request.size not in {"1024x1024", "1792x1024", "1024x1792"}:
        raise HTTPException(status_code=400, detail="Invalid size.")
    if request.quality not in {"standard", "hd"}:
        raise HTTPException(status_code=400, detail="Invalid quality.")
    if request.style not in {"vivid", "natural"}:
        raise HTTPException(status_code=400, detail="Invalid style.")
    if request.provider not in {"auto", "openai", "chatgpt", "google", "gemini", "openrouter"}:
        raise HTTPException(status_code=400, detail="Invalid provider.")
    if request.prompt_target not in {"auto", "chatgpt", "gemini", "canva"}:
        raise HTTPException(status_code=400, detail="Invalid prompt target.")

    revised_prompt = await ai_service.enhance_image_prompt(
        prompt,
        size=request.size,
        quality=request.quality,
        style=request.style,
        provider=request.provider,
        prompt_target=request.prompt_target,
    )

    return {
        "prompt": prompt,
        "revised_prompt": revised_prompt or prompt,
        "provider": request.provider,
        "prompt_target": request.prompt_target,
    }


@router.get("/providers")
async def image_providers(
    current_user: User = Depends(get_current_user),
):
    return {
        "providers": await ai_service.get_available_image_providers(),
        "prompt_targets": [
            {"id": "auto", "name": "Auto"},
            {"id": "chatgpt", "name": "ChatGPT"},
            {"id": "gemini", "name": "Gemini"},
            {"id": "canva", "name": "Canva"},
        ],
    }


@router.get("/proxy")
async def proxy_image(
    url: str,
    current_user: User = Depends(get_current_user)
):
    try:
        content, media_type = await _fetch_proxy_image(url)
        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image proxy failed: {str(exc)}")


@router.post("/variations")
async def image_variations(
    http_request: Request,
    request: EditRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        if not request.image_b64:
            raise HTTPException(status_code=400, detail="Missing image data.")
        await enforce_image_rate_limit(http_request, current_user)
        prompt = (request.prompt or "").strip() or "Create a polished new image inspired by this upload."
        if len(prompt) > 4000:
            raise HTTPException(status_code=400, detail="Prompt too long. Max 4000 chars.")
        image_bytes = base64.b64decode(request.image_b64)
        images = await ai_service.edit_image(
            prompt,
            image_bytes,
            mime_type=request.mime_type,
        )

        if not images:
            raise HTTPException(
                status_code=502,
                detail="Image editing returned no image data. Please try again with a clearer prompt.",
            )

        return {
            "prompt": prompt,
            "images": images,
        }
    except HTTPException:
        raise
    except Exception as exc:
        _raise_image_http_error(exc)


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
