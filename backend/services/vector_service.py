import logging
import re
from typing import List, Tuple
import math

from openai import AsyncOpenAI
from config.settings import settings

try:
    import faiss
    import numpy as np
    HAS_FAISS = True
except Exception:
    faiss = None
    np = None
    HAS_FAISS = False


class VectorService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.dimension = settings.OPENAI_EMBEDDING_DIM
        self.index = faiss.IndexFlatL2(self.dimension) if HAS_FAISS else None
        self.documents = []  # Store document chunks
        self.embeddings = []  # Fallback storage when FAISS is unavailable
        self.embeddings_enabled = bool((settings.OPENAI_API_KEY or "").strip())
        self.logger = logging.getLogger(__name__)

    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text using OpenAI"""
        if not self.embeddings_enabled:
            raise RuntimeError("Embeddings are disabled because no OpenAI API key is configured.")
        try:
            response = await self.client.embeddings.create(
                input=text,
                model=settings.OPENAI_EMBEDDING_MODEL
            )
            return response.data[0].embedding
        except Exception as e:
            self.embeddings_enabled = False
            raise RuntimeError(f"Error getting embedding: {str(e)}")

    def chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """Split text into chunks for embedding"""
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)

        return chunks

    async def add_document(self, text: str, doc_id: int) -> None:
        """Add document to vector database"""
        chunks = self.chunk_text(text)

        for chunk in chunks:
            if self.embeddings_enabled:
                try:
                    embedding = await self.get_embedding(chunk)
                    if HAS_FAISS:
                        embedding_array = np.array([embedding], dtype=np.float32)
                        self.index.add(embedding_array)
                    else:
                        self.embeddings.append(embedding)
                except Exception as exc:
                    self.logger.warning(
                        "vector_add_embedding_failed doc_id=%s error=%s; falling back to lexical retrieval",
                        doc_id,
                        exc,
                    )

            self.documents.append({
                "doc_id": doc_id,
                "text": chunk
            })

    def _tokenize(self, text: str) -> set[str]:
        return set(re.findall(r"[A-Za-z0-9_]+", (text or "").lower()))

    def _lexical_search(self, query: str, k: int = 5, doc_id: int = None) -> List[Tuple[str, float]]:
        query_tokens = self._tokenize(query)
        scored: List[Tuple[str, float]] = []

        for document in self.documents:
            if doc_id is not None and document["doc_id"] != doc_id:
                continue

            text = document["text"]
            document_tokens = self._tokenize(text)
            if not document_tokens:
                continue

            overlap = len(query_tokens & document_tokens)
            if overlap == 0:
                continue

            score = overlap / max(len(query_tokens), 1)
            scored.append((text, float(score)))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]

    async def search(self, query: str, k: int = 5, doc_id: int = None) -> List[Tuple[str, float]]:
        """Search for similar documents"""
        if not self.documents:
            return []

        if not self.embeddings_enabled:
            return self._lexical_search(query, k=k, doc_id=doc_id)

        try:
            query_embedding = await self.get_embedding(query)
        except Exception as exc:
            self.logger.warning(
                "vector_query_embedding_failed error=%s; using lexical retrieval fallback",
                exc,
            )
            return self._lexical_search(query, k=k, doc_id=doc_id)
        results: List[Tuple[str, float]] = []

        if HAS_FAISS:
            query_array = np.array([query_embedding], dtype=np.float32)
            distances, indices = self.index.search(query_array, k)

            for idx, distance in zip(indices[0], distances[0]):
                if idx < len(self.documents):
                    if doc_id is None or self.documents[idx]["doc_id"] == doc_id:
                        results.append((self.documents[idx]["text"], float(distance)))
            return results

        # Fallback: cosine similarity over stored embeddings
        def cosine_similarity(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        scored = []
        for idx, embedding in enumerate(self.embeddings):
            if doc_id is not None and self.documents[idx]["doc_id"] != doc_id:
                continue
            score = cosine_similarity(query_embedding, embedding)
            scored.append((idx, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        for idx, score in scored[:k]:
            results.append((self.documents[idx]["text"], float(score)))

        return results

    def save_index(self, file_path: str) -> None:
        """Save FAISS index to disk"""
        if not HAS_FAISS:
            return
        faiss.write_index(self.index, file_path)

    def load_index(self, file_path: str) -> None:
        """Load FAISS index from disk"""
        if not HAS_FAISS:
            return
        self.index = faiss.read_index(file_path)


# Singleton instance
vector_service = VectorService()
