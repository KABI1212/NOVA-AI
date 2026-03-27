import logging
import math
import re
from typing import List, Tuple

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
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.dimension = settings.OPENAI_EMBEDDING_DIM
        self.index = faiss.IndexFlatL2(self.dimension) if HAS_FAISS else None
        self.documents = []
        self.vector_entries = []
        self.vector_embeddings = []
        self.embeddings_enabled = bool((settings.OPENAI_API_KEY or "").strip())
        self.indexed_doc_ids = set()
        self.logger = logging.getLogger(__name__)

    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text using OpenAI"""
        if not self.embeddings_enabled or self.client is None:
            raise RuntimeError(
                "Embeddings are disabled because no OpenAI API key is configured."
            )
        try:
            response = await self.client.embeddings.create(
                input=text,
                model=settings.OPENAI_EMBEDDING_MODEL,
            )
            return response.data[0].embedding
        except Exception as exc:
            self.embeddings_enabled = False
            raise RuntimeError(f"Error getting embedding: {str(exc)}") from exc

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 220,
        overlap: int = 40,
    ) -> List[str]:
        """Split text into overlapping chunks for retrieval."""
        words = text.split()
        if not words:
            return []

        step = max(1, chunk_size - overlap)
        chunks = []
        for start in range(0, len(words), step):
            chunk_words = words[start : start + chunk_size]
            if not chunk_words:
                continue
            chunk = " ".join(chunk_words).strip()
            if chunk:
                chunks.append(chunk)
            if start + chunk_size >= len(words):
                break
        return chunks

    async def add_document(self, text: str, doc_id: int) -> None:
        await self.upsert_document(text, doc_id)

    async def upsert_document(self, text: str, doc_id: int) -> None:
        """Add or replace a document in the vector database."""
        self.remove_document(doc_id)
        chunks = self.chunk_text(text)
        if not chunks:
            self.indexed_doc_ids.add(doc_id)
            return

        new_vector_entries = []
        new_vector_embeddings = []
        for chunk in chunks:
            entry = {
                "doc_id": doc_id,
                "text": chunk,
            }
            self.documents.append(entry)

            if self.embeddings_enabled:
                try:
                    embedding = await self.get_embedding(chunk)
                    new_vector_entries.append(entry)
                    new_vector_embeddings.append(embedding)
                except Exception as exc:
                    self.logger.warning(
                        "vector_add_embedding_failed doc_id=%s error=%s; falling back to lexical retrieval",
                        doc_id,
                        exc,
                    )

        if new_vector_entries:
            self.vector_entries.extend(new_vector_entries)
            self.vector_embeddings.extend(new_vector_embeddings)
            self._rebuild_index()

        self.indexed_doc_ids.add(doc_id)

    async def ensure_document(self, text: str, doc_id: int) -> None:
        if doc_id in self.indexed_doc_ids:
            return
        await self.upsert_document(text, doc_id)

    def remove_document(self, doc_id: int) -> None:
        self.documents = [
            entry for entry in self.documents if entry["doc_id"] != doc_id
        ]

        retained_entries = []
        retained_embeddings = []
        for index, entry in enumerate(self.vector_entries):
            if entry["doc_id"] == doc_id:
                continue
            retained_entries.append(entry)
            if index < len(self.vector_embeddings):
                retained_embeddings.append(self.vector_embeddings[index])

        self.vector_entries = retained_entries
        self.vector_embeddings = retained_embeddings
        self.indexed_doc_ids.discard(doc_id)
        self._rebuild_index()

    def _tokenize(self, text: str) -> set[str]:
        return set(re.findall(r"[A-Za-z0-9_]+", (text or "").lower()))

    def _lexical_search(
        self,
        query: str,
        k: int = 5,
        doc_id: int = None,
    ) -> List[Tuple[str, float]]:
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

    async def search(
        self,
        query: str,
        k: int = 5,
        doc_id: int = None,
    ) -> List[Tuple[str, float]]:
        """Search for similar documents."""
        if not self.documents:
            return []

        if not self.embeddings_enabled or not self.vector_entries:
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

        if HAS_FAISS and self.index is not None and self.index.ntotal:
            query_array = np.array([query_embedding], dtype=np.float32)
            distances, indices = self.index.search(query_array, k)

            for idx, distance in zip(indices[0], distances[0]):
                if idx < len(self.vector_entries):
                    entry = self.vector_entries[idx]
                    if doc_id is None or entry["doc_id"] == doc_id:
                        results.append((entry["text"], float(distance)))
            return results

        def cosine_similarity(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        scored = []
        for idx, embedding in enumerate(self.vector_embeddings):
            if doc_id is not None and self.vector_entries[idx]["doc_id"] != doc_id:
                continue
            score = cosine_similarity(query_embedding, embedding)
            scored.append((idx, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        for idx, score in scored[:k]:
            results.append((self.vector_entries[idx]["text"], float(score)))

        return results

    def _rebuild_index(self) -> None:
        if not HAS_FAISS:
            self.index = None
            return
        self.index = faiss.IndexFlatL2(self.dimension)
        if not self.vector_embeddings:
            return
        embedding_array = np.array(self.vector_embeddings, dtype=np.float32)
        self.index.add(embedding_array)

    def save_index(self, file_path: str) -> None:
        """Save FAISS index to disk."""
        if not HAS_FAISS or self.index is None:
            return
        faiss.write_index(self.index, file_path)

    def load_index(self, file_path: str) -> None:
        """Load FAISS index from disk."""
        if not HAS_FAISS:
            return
        self.index = faiss.read_index(file_path)


vector_service = VectorService()
