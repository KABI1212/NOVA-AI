from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from config.settings import settings


class RedisStore:
    def __init__(self, redis_url: str = "") -> None:
        self.redis_url = (redis_url or settings.REDIS_URL or "").strip()
        self._redis: Redis | None = None
        self._memory: dict[str, tuple[Any, float | None]] = {}
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.aclose()
        finally:
            self._redis = None

    async def get_client(self) -> Redis | None:
        if not self.redis_url:
            return None
        if self._redis is not None:
            return self._redis
        client = Redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            await client.ping()
        except RedisError:
            await client.aclose()
            return None
        self._redis = client
        return client

    async def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        client = await self.get_client()
        if client is not None:
            try:
                await client.set(key, payload, ex=ttl_seconds)
                return
            except RedisError:
                pass
        await self._memory_set(key, payload, ttl_seconds)

    async def get_json(self, key: str, default: Any = None) -> Any:
        client = await self.get_client()
        raw_value = None
        if client is not None:
            try:
                raw_value = await client.get(key)
            except RedisError:
                raw_value = None
        if raw_value is None:
            raw_value = await self._memory_get(key)
        if raw_value is None:
            return default
        try:
            return json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return default

    async def delete(self, *keys: str) -> None:
        cleaned = [str(key or "").strip() for key in keys if str(key or "").strip()]
        if not cleaned:
            return
        client = await self.get_client()
        if client is not None:
            try:
                await client.delete(*cleaned)
            except RedisError:
                pass
        async with self._lock:
            for key in cleaned:
                self._memory.pop(key, None)

    async def push_queue(self, queue_name: str, value: str) -> None:
        client = await self.get_client()
        if client is not None:
            try:
                await client.lpush(queue_name, value)
                return
            except RedisError:
                pass
        queue_key = f"queue:{queue_name}"
        async with self._lock:
            self._prune_locked()
            current = str(self._memory.get(queue_key, ("[]", None))[0] or "[]")
            try:
                values = json.loads(current)
            except json.JSONDecodeError:
                values = []
            if value not in values:
                values.insert(0, value)
            self._memory[queue_key] = (json.dumps(values), None)

    async def remove_queue_value(self, queue_name: str, value: str) -> None:
        client = await self.get_client()
        if client is not None:
            try:
                await client.lrem(queue_name, 0, value)
                return
            except RedisError:
                pass
        queue_key = f"queue:{queue_name}"
        async with self._lock:
            self._prune_locked()
            current = str(self._memory.get(queue_key, ("[]", None))[0] or "[]")
            try:
                values = json.loads(current)
            except json.JSONDecodeError:
                values = []
            values = [item for item in values if item != value]
            self._memory[queue_key] = (json.dumps(values), None)

    async def add_set_members(self, key: str, *members: str, ttl_seconds: int | None = None) -> None:
        normalized = [str(member or "").strip() for member in members if str(member or "").strip()]
        if not normalized:
            return
        client = await self.get_client()
        if client is not None:
            try:
                await client.sadd(key, *normalized)
                if ttl_seconds:
                    await client.expire(key, ttl_seconds)
                return
            except RedisError:
                pass
        async with self._lock:
            self._prune_locked()
            current = self._memory.get(key, (None, None))[0]
            try:
                values = set(json.loads(current)) if current else set()
            except json.JSONDecodeError:
                values = set()
            values.update(normalized)
            expires_at = time.time() + ttl_seconds if ttl_seconds else None
            self._memory[key] = (json.dumps(sorted(values)), expires_at)

    async def get_set_members(self, key: str) -> list[str]:
        client = await self.get_client()
        if client is not None:
            try:
                values = await client.smembers(key)
                return sorted(str(value) for value in values if value)
            except RedisError:
                pass
        current = await self._memory_get(key)
        try:
            values = json.loads(current) if current else []
        except json.JSONDecodeError:
            values = []
        return [str(value) for value in values if value]

    async def _memory_set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        async with self._lock:
            expires_at = time.time() + ttl_seconds if ttl_seconds else None
            self._memory[key] = (value, expires_at)

    async def _memory_get(self, key: str) -> str | None:
        async with self._lock:
            self._prune_locked()
            value = self._memory.get(key)
            if value is None:
                return None
            return str(value[0])

    def _prune_locked(self) -> None:
        now = time.time()
        expired_keys = [
            key
            for key, (_, expires_at) in self._memory.items()
            if expires_at is not None and expires_at <= now
        ]
        for key in expired_keys:
            self._memory.pop(key, None)


redis_store = RedisStore()
