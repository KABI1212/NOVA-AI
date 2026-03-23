from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, Request, status

from config.settings import settings
from models.user import User
from services.rate_limit_service import rate_limit_service


def _client_key(request: Request, current_user: Optional[User]) -> str:
    if current_user is not None and getattr(current_user, "id", None) is not None:
        return f"user:{current_user.id}"

    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
        if client_ip:
            return f"ip:{client_ip}"

    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return f"ip:{real_ip}"

    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


async def _enforce_limit(
    scope: str,
    request: Request,
    current_user: Optional[User],
    *,
    limit: int,
    window_seconds: int,
    cost: int = 1,
    detail: str,
) -> None:
    if not settings.RATE_LIMIT_ENABLED or limit < 1 or window_seconds < 1 or cost < 1:
        return

    result = await rate_limit_service.check_limit(
        scope,
        _client_key(request, current_user),
        limit=limit,
        window_seconds=window_seconds,
        cost=cost,
    )

    if result.current <= result.limit:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail.format(retry_after=result.retry_after),
        headers={
            "Retry-After": str(result.retry_after),
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Scope": result.scope,
        },
    )


async def enforce_chat_rate_limit(
    request: Request,
    current_user: Optional[User],
) -> None:
    await _enforce_limit(
        "chat",
        request,
        current_user,
        limit=settings.CHAT_RATE_LIMIT_REQUESTS,
        window_seconds=settings.CHAT_RATE_LIMIT_WINDOW_SECONDS,
        detail="Too many chat requests. Try again in {retry_after} seconds.",
    )


async def enforce_image_rate_limit(
    request: Request,
    current_user: Optional[User],
    *,
    cost: int = 1,
) -> None:
    await _enforce_limit(
        "image",
        request,
        current_user,
        limit=settings.IMAGE_RATE_LIMIT_REQUESTS,
        window_seconds=settings.IMAGE_RATE_LIMIT_WINDOW_SECONDS,
        cost=cost,
        detail="Too many image generation requests. Try again in {retry_after} seconds.",
    )
