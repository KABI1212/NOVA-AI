from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from config.database import MongoSession
from config.settings import settings
from models.file_chunk import FileChunk
from models.file_record import FileRecord
from services.embedder import embedder_service
from services.file_parser import ParsedFile, ParsedSection


@dataclass
class RetrievalHit:
    file_id: str
    file_name: str
    text: str
    score: float
    page_number: int | None = None
    sheet_name: str | None = None
    section_title: str | None = None

    @property
    def label(self) -> str:
        parts = [self.file_name]
        if self.page_number is not None:
            parts.append(f"page {self.page_number}")
        elif self.sheet_name:
            parts.append(f"sheet {self.sheet_name}")
        elif self.section_title:
            parts.append(self.section_title)
        return " ".join(parts)


class RetrieverService:
    def __init__(self) -> None:
        self.chunk_size = max(500, int(settings.FILE_CHUNK_SIZE))
        self.chunk_overlap = max(60, int(settings.FILE_CHUNK_OVERLAP))
        self.default_limit = max(1, int(settings.FILE_RETRIEVAL_LIMIT))

    async def index_file(self, db: MongoSession, file_record: FileRecord, parsed_file: ParsedFile) -> list[FileChunk]:
        collection = db.collection_for(FileChunk)
        collection.delete_many({"file_id": file_record.id})

        chunks: list[FileChunk] = []
        chunk_index = 0
        for section in parsed_file.sections:
            for chunk_text in self._chunk_section(section):
                embedding = await embedder_service.embed_text(chunk_text["text"])
                chunk = FileChunk(
                    file_id=file_record.id,
                    user_id=file_record.user_id,
                    chunk_index=chunk_index,
                    text=chunk_text["text"],
                    embedding=embedding or None,
                    page_number=chunk_text.get("page_number"),
                    sheet_name=chunk_text.get("sheet_name"),
                    section_title=chunk_text.get("section_title"),
                    language=chunk_text.get("language"),
                    token_count=len(chunk_text["text"].split()),
                )
                db.add(chunk)
                chunks.append(chunk)
                chunk_index += 1

        db.commit()
        return chunks

    async def retrieve(
        self,
        db: MongoSession,
        *,
        user_id: int,
        query: str,
        file_ids: list[str],
        limit: int | None = None,
    ) -> list[RetrievalHit]:
        cleaned_file_ids = [str(file_id or "").strip() for file_id in file_ids if str(file_id or "").strip()]
        if not cleaned_file_ids:
            return []

        collection = db.collection_for(FileChunk)
        payloads = list(
            collection.find(
                {
                    "user_id": user_id,
                    "file_id": {"$in": cleaned_file_ids},
                }
            )
        )
        if not payloads:
            return []

        query_embedding = await embedder_service.embed_text(query)
        terms = self._query_terms(query)
        file_lookup = self._file_lookup(db, cleaned_file_ids)

        scored_hits: list[RetrievalHit] = []
        for payload in payloads:
            text = str(payload.get("text") or "").strip()
            if not text:
                continue
            lexical_score = self._lexical_score(text, terms)
            semantic_score = embedder_service.cosine_similarity(query_embedding, payload.get("embedding"))
            combined_score = (semantic_score * 0.72) + (lexical_score * 0.28)
            if combined_score <= 0:
                continue
            file_id = str(payload.get("file_id") or "")
            file_record = file_lookup.get(file_id)
            file_name = str(
                (file_record or {}).get("original_name")
                or (file_record or {}).get("filename")
                or "Uploaded file"
            )
            scored_hits.append(
                RetrievalHit(
                    file_id=file_id,
                    file_name=file_name,
                    text=text,
                    score=combined_score,
                    page_number=payload.get("page_number"),
                    sheet_name=payload.get("sheet_name"),
                    section_title=payload.get("section_title"),
                )
            )

        scored_hits.sort(key=lambda item: item.score, reverse=True)
        deduped: list[RetrievalHit] = []
        seen: set[tuple[str, str]] = set()
        target_limit = max(1, limit or self.default_limit)
        for hit in scored_hits:
            dedupe_key = (hit.file_id, hit.text[:160].lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            deduped.append(hit)
            if len(deduped) >= target_limit:
                break
        return deduped

    def build_context(self, hits: list[RetrievalHit], *, max_chars: int | None = None) -> tuple[str, list[dict[str, Any]]]:
        if not hits:
            return "", []
        limit = max_chars or max(3000, int(settings.FILE_CONTEXT_CHAR_LIMIT))
        blocks: list[str] = []
        citations: list[dict[str, Any]] = []
        current_chars = 0
        for hit in hits:
            excerpt = self._trim_excerpt(hit.text, limit=800)
            block = f"[{hit.label}]\n{excerpt}"
            if blocks and current_chars + len(block) > limit:
                break
            blocks.append(block)
            current_chars += len(block)
            citations.append(
                {
                    "label": hit.label,
                    "title": hit.label,
                    "excerpt": self._trim_excerpt(hit.text, limit=240),
                    "file_id": hit.file_id,
                    "page_number": hit.page_number,
                    "sheet_name": hit.sheet_name,
                    "kind": "file",
                }
            )
        return "\n\n".join(blocks), citations

    def delete_file_chunks(self, db: MongoSession, file_id: str) -> None:
        db.collection_for(FileChunk).delete_many({"file_id": file_id})

    def _chunk_section(self, section: ParsedSection) -> list[dict[str, Any]]:
        text = str(section.text or "").strip()
        if not text:
            return []
        paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
        if not paragraphs:
            paragraphs = [text]

        chunks: list[dict[str, Any]] = []
        current = ""
        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if current and len(candidate) > self.chunk_size:
                chunks.append(self._chunk_payload(current, section))
                overlap = current[-self.chunk_overlap :] if len(current) > self.chunk_overlap else current
                current = f"{overlap}\n\n{paragraph}".strip()
            else:
                current = candidate
        if current:
            chunks.append(self._chunk_payload(current, section))
        return chunks

    def _chunk_payload(self, text: str, section: ParsedSection) -> dict[str, Any]:
        return {
            "text": text.strip(),
            "page_number": section.page_number,
            "sheet_name": section.sheet_name,
            "section_title": section.section_title,
            "language": section.language,
        }

    def _file_lookup(self, db: MongoSession, file_ids: list[str]) -> dict[str, dict[str, Any]]:
        payloads = db.collection_for(FileRecord).find({"id": {"$in": file_ids}})
        return {str(payload.get("id")): payload for payload in payloads}

    def _query_terms(self, query: str) -> list[str]:
        stopwords = {
            "a",
            "an",
            "and",
            "are",
            "compare",
            "document",
            "explain",
            "file",
            "find",
            "from",
            "give",
            "how",
            "in",
            "is",
            "me",
            "of",
            "on",
            "show",
            "summarize",
            "tell",
            "the",
            "this",
            "to",
            "what",
            "where",
            "which",
            "who",
            "with",
        }
        terms: list[str] = []
        for raw_term in re.findall(r"[A-Za-z0-9_]+", (query or "").lower()):
            if raw_term in stopwords or len(raw_term) < 3:
                continue
            if raw_term not in terms:
                terms.append(raw_term)
        return terms[:12]

    def _lexical_score(self, text: str, terms: list[str]) -> float:
        if not terms:
            return 0.0
        lowered = text.lower()
        score = 0.0
        for term in terms:
            if term in lowered:
                score += 1.0 + min(lowered.count(term), 4) * 0.2
        if len(terms) >= 2:
            score += sum(0.4 for first, second in zip(terms, terms[1:]) if f"{first} {second}" in lowered)
        return score / max(len(terms), 1)

    def _trim_excerpt(self, text: str, *, limit: int = 260) -> str:
        cleaned = " ".join(str(text or "").split()).strip()
        if len(cleaned) <= limit:
            return cleaned
        return f"{cleaned[:limit].rstrip()}..."


retriever_service = RetrieverService()
