from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import services.rate_limit_service as rate_limit_service_module
import utils.rate_limit as rate_limit_module
from config.settings import settings
from services.rate_limit_service import RateLimitService


def _build_request(
    *,
    path: str = "/api/chat",
    client_host: str = "127.0.0.1",
    headers: dict[str, str] | None = None,
) -> Request:
    encoded_headers = [
        (key.lower().encode("utf-8"), value.encode("utf-8"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": path,
        "headers": encoded_headers,
        "client": (client_host, 12345),
        "scheme": "http",
        "server": ("testserver", 80),
        "query_string": b"",
    }
    return Request(scope)


def test_rate_limit_service_counts_cost_and_blocks_in_memory() -> None:
    async def scenario() -> None:
        service = RateLimitService("")
        try:
            first = await service.check_limit(
                "image",
                "user:7",
                limit=3,
                window_seconds=60,
                cost=2,
            )
            assert first.current == 2
            assert first.remaining == 1

            second = await service.check_limit(
                "image",
                "user:7",
                limit=3,
                window_seconds=60,
                cost=2,
            )
            assert second.current == 4
            assert second.remaining == 0
            assert second.retry_after >= 1
        finally:
            await service.close()

    asyncio.run(scenario())


def test_rate_limit_service_resets_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [120.0]
    monkeypatch.setattr(rate_limit_service_module.time, "time", lambda: clock[0])

    async def scenario() -> None:
        service = RateLimitService("")
        try:
            first = await service.check_limit(
                "chat",
                "ip:203.0.113.5",
                limit=1,
                window_seconds=60,
            )
            assert first.current == 1

            clock[0] = 181.0
            second = await service.check_limit(
                "chat",
                "ip:203.0.113.5",
                limit=1,
                window_seconds=60,
            )
            assert second.current == 1
            assert second.remaining == 0
        finally:
            await service.close()

    asyncio.run(scenario())


def test_enforce_chat_rate_limit_uses_forwarded_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    service = RateLimitService("")
    monkeypatch.setattr(rate_limit_module, "rate_limit_service", service)
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_REQUESTS", 1)
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_WINDOW_SECONDS", 60)

    async def scenario() -> None:
        try:
            request = _build_request(
                headers={"x-forwarded-for": "203.0.113.5, 10.0.0.1"},
            )
            await rate_limit_module.enforce_chat_rate_limit(request, None)

            with pytest.raises(HTTPException) as exc_info:
                await rate_limit_module.enforce_chat_rate_limit(request, None)

            exc = exc_info.value
            assert exc.status_code == 429
            assert exc.headers["Retry-After"].isdigit()
            assert exc.headers["X-RateLimit-Scope"] == "chat"
        finally:
            await service.close()

    asyncio.run(scenario())


def test_enforce_chat_rate_limit_prefers_user_id_over_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RateLimitService("")
    monkeypatch.setattr(rate_limit_module, "rate_limit_service", service)
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_REQUESTS", 1)
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_WINDOW_SECONDS", 60)

    class DummyUser:
        id = 42

    async def scenario() -> None:
        try:
            first_request = _build_request(headers={"x-forwarded-for": "203.0.113.5"})
            second_request = _build_request(headers={"x-forwarded-for": "198.51.100.20"})
            await rate_limit_module.enforce_chat_rate_limit(first_request, DummyUser())

            with pytest.raises(HTTPException):
                await rate_limit_module.enforce_chat_rate_limit(
                    second_request,
                    DummyUser(),
                )
        finally:
            await service.close()

    asyncio.run(scenario())
