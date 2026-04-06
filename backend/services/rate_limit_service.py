from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitStatus:
    scope: str
    limit: int
    window_seconds: int
    current: int
    remaining: int
    retry_after: int


class RateLimitService:
    def __init__(
        self,
        redis_url: str = "",
        *,
        redis_retry_cooldown_seconds: int = 30,
    ) -> None:
        self.redis_url = (redis_url or "").strip()
        self.redis_retry_cooldown_seconds = max(1, redis_retry_cooldown_seconds)
        self._redis: Redis | None = None
        self._redis_disabled_until = 0.0
        self._memory_fallback_logged = False
        self._memory: dict[str, tuple[int, float]] = {}
        self._memory_lock = asyncio.Lock()

    async def check_limit(
        self,
        scope: str,
        identifier: str,
        *,
        limit: int,
        window_seconds: int,
        cost: int = 1,
    ) -> RateLimitStatus:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        if window_seconds < 1:
            raise ValueError("window_seconds must be greater than zero")
        if cost < 1:
            raise ValueError("cost must be greater than zero")

        now = time.time()
        window_start = int(now // window_seconds) * window_seconds
        retry_after = max(1, int(window_start + window_seconds - now))

        redis_client = await self._get_redis()
        if redis_client is not None:
            redis_key = f"rate_limit:{scope}:{identifier}:{window_start}"
            try:
                async with redis_client.pipeline(transaction=True) as pipeline:
                    pipeline.incrby(redis_key, cost)
                    pipeline.expire(redis_key, retry_after)
                    current, _ = await pipeline.execute()
                return self._build_status(
                    scope=scope,
                    limit=limit,
                    window_seconds=window_seconds,
                    current=int(current),
                    retry_after=retry_after,
                )
            except RedisError as exc:
                await self._disable_redis(exc)

        memory_key = f"rate_limit:{scope}:{identifier}:{window_seconds}"
        expires_at = float(window_start + window_seconds)
        async with self._memory_lock:
            self._prune_memory(now)
            current, existing_expires_at = self._memory.get(memory_key, (0, 0.0))
            if existing_expires_at <= now:
                current = 0
            current += cost
            self._memory[memory_key] = (current, expires_at)

        return self._build_status(
            scope=scope,
            limit=limit,
            window_seconds=window_seconds,
            current=current,
            retry_after=max(1, int(expires_at - now)),
        )

    async def close(self) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.aclose()
        finally:
            self._redis = None

    async def reset(self) -> None:
        await self.close()
        async with self._memory_lock:
            self._memory.clear()
        self._redis_disabled_until = 0.0
        self._memory_fallback_logged = False

    def _build_status(
        self,
        *,
        scope: str,
        limit: int,
        window_seconds: int,
        current: int,
        retry_after: int,
    ) -> RateLimitStatus:
        return RateLimitStatus(
            scope=scope,
            limit=limit,
            window_seconds=window_seconds,
            current=current,
            remaining=max(0, limit - current),
            retry_after=max(1, retry_after),
        )

    async def _get_redis(self) -> Redis | None:
        if not self.redis_url:
            return None
        if self._redis is not None:
            return self._redis
        if time.monotonic() < self._redis_disabled_until:
            return None

        redis_client = Redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            await redis_client.ping()
        except RedisError as exc:
            try:
                await redis_client.aclose()
            finally:
                await self._disable_redis(exc)
            return None

        self._redis = redis_client
        return redis_client

    async def _disable_redis(self, exc: RedisError) -> None:
        self._redis_disabled_until = time.monotonic() + self.redis_retry_cooldown_seconds
        if settings.RATE_LIMIT_WARN_ON_MEMORY_FALLBACK:
            logger.warning(
                "Redis unavailable for rate limiting; using in-memory fallback error=%s",
                exc,
            )
            self._memory_fallback_logged = True
        elif not self._memory_fallback_logged:
            self._memory_fallback_logged = True
        if self._redis is not None:
            try:
                await self._redis.aclose()
            finally:
                self._redis = None

    def _prune_memory(self, now: float) -> None:
        expired_keys = [
            key for key, (_, expires_at) in self._memory.items() if expires_at <= now
        ]
        for key in expired_keys:
            self._memory.pop(key, None)


rate_limit_service = RateLimitService(settings.REDIS_URL)
