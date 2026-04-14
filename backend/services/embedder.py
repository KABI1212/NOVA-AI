from __future__ import annotations

import hashlib
import math
import re
from typing import List

from openai import AsyncOpenAI

from config.settings import settings
from services.redis_store import redis_store


class EmbedderService:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self.dimension = max(256, int(getattr(settings, "OPENAI_EMBEDDING_DIM", 1536) or 1536))
        self.local_dimension = 256

    def enabled(self) -> bool:
        return self.client is not None

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        return f"nova:file-embedding:{self.model}:{digest}"

    def _local_embedding(self, text: str) -> List[float]:
        vector = [0.0] * self.local_dimension
        tokens = re.findall(r"[A-Za-z0-9_]+", (text or "").lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % self.local_dimension
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vector[index] += sign * (1.0 + min(len(token), 12) / 12.0)
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    async def embed_text(self, text: str) -> List[float]:
        cleaned = " ".join((text or "").split()).strip()
        if not cleaned:
            return []
        cache_key = self._cache_key(cleaned)
        cached = await redis_store.get_json(cache_key)
        if isinstance(cached, list) and cached:
            return [float(value) for value in cached]

        if self.enabled():
            response = await self.client.embeddings.create(
                input=cleaned,
                model=self.model,
            )
            embedding = [float(value) for value in response.data[0].embedding]
        else:
            embedding = self._local_embedding(cleaned)

        await redis_store.set_json(
            cache_key,
            embedding,
            ttl_seconds=max(60, int(settings.FILE_EMBED_CACHE_TTL_SECONDS)),
        )
        return embedding

    @staticmethod
    def cosine_similarity(left: List[float] | None, right: List[float] | None) -> float:
        if not left or not right:
            return 0.0
        limit = min(len(left), len(right))
        if limit == 0:
            return 0.0
        dot = sum(float(left[index]) * float(right[index]) for index in range(limit))
        left_norm = math.sqrt(sum(float(left[index]) ** 2 for index in range(limit)))
        right_norm = math.sqrt(sum(float(right[index]) ** 2 for index in range(limit)))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)


embedder_service = EmbedderService()
