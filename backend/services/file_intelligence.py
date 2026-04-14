from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from config.database import SessionLocal
from config.settings import settings
from models.chat_session import ChatSession
from models.file_record import FileRecord
from services.file_parser import file_parser_service
from services.redis_store import redis_store
from services.retriever import retriever_service
from services.storage import storage_service


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FileIntelligenceService:
    def __init__(self) -> None:
        self._active_tasks: dict[str, asyncio.Task] = {}

    def _progress_key(self, file_id: str) -> str:
        return f"nova:file-progress:{file_id}"

    def _session_key(self, user_id: int, session_id: str) -> str:
        return f"nova:file-session:{user_id}:{session_id}"

    async def remember_session_files(
        self,
        db,
        *,
        user_id: int,
        session_id: str,
        conversation_id: str | None,
        file_ids: list[str],
    ) -> None:
        cleaned_session_id = str(session_id or "").strip()
        cleaned_file_ids = [str(file_id or "").strip() for file_id in file_ids if str(file_id or "").strip()]
        if not cleaned_session_id or not cleaned_file_ids:
            return

        session = db.query(ChatSession).filter(
            ChatSession.id == cleaned_session_id,
            ChatSession.user_id == user_id,
        ).first()
        if session is None:
            session = ChatSession(
                id=cleaned_session_id,
                user_id=user_id,
                conversation_id=conversation_id,
                file_ids=cleaned_file_ids,
            )
        else:
            existing = [str(file_id or "").strip() for file_id in session.file_ids or [] if str(file_id or "").strip()]
            for file_id in cleaned_file_ids:
                if file_id not in existing:
                    existing.append(file_id)
            session.file_ids = existing
            if conversation_id:
                session.conversation_id = conversation_id
            session.last_active_at = datetime.now(timezone.utc)
        db.add(session)
        db.commit()

        await redis_store.add_set_members(
            self._session_key(user_id, cleaned_session_id),
            *cleaned_file_ids,
            ttl_seconds=max(3600, int(settings.FILE_SESSION_TTL_SECONDS)),
        )

    async def session_file_ids(
        self,
        db,
        *,
        user_id: int,
        session_id: str | None,
        conversation_id: str | None = None,
    ) -> list[str]:
        ids: list[str] = []
        cleaned_session_id = str(session_id or "").strip()
        if cleaned_session_id:
            redis_ids = await redis_store.get_set_members(self._session_key(user_id, cleaned_session_id))
            ids.extend(redis_ids)

            session = db.query(ChatSession).filter(
                ChatSession.id == cleaned_session_id,
                ChatSession.user_id == user_id,
            ).first()
            if session is not None:
                ids.extend(str(file_id or "").strip() for file_id in session.file_ids or [])

        if conversation_id:
            for payload in db.collection_for(FileRecord).find(
                {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                }
            ):
                ids.append(str(payload.get("id") or "").strip())

        deduped: list[str] = []
        for file_id in ids:
            if file_id and file_id not in deduped:
                deduped.append(file_id)
        return deduped

    async def update_progress(self, file_id: str, *, status: str, progress: int, stage: str, message: str) -> None:
        await redis_store.set_json(
            self._progress_key(file_id),
            {
                "status": status,
                "progress": max(0, min(int(progress), 100)),
                "stage": stage,
                "message": message,
                "updated_at": utc_now_iso(),
            },
            ttl_seconds=max(3600, int(settings.FILE_SESSION_TTL_SECONDS)),
        )

    async def get_progress(self, file_id: str) -> dict[str, Any]:
        return await redis_store.get_json(
            self._progress_key(file_id),
            default={
                "status": "unknown",
                "progress": 0,
                "stage": "pending",
                "message": "Pending",
                "updated_at": utc_now_iso(),
            },
        )

    async def enqueue_processing(self, file_id: str) -> None:
        cleaned_file_id = str(file_id or "").strip()
        if not cleaned_file_id:
            return
        await redis_store.push_queue(settings.FILE_QUEUE_NAME, cleaned_file_id)
        await self.update_progress(
            cleaned_file_id,
            status="queued",
            progress=18,
            stage="queued",
            message="Queued for analysis",
        )
        existing_task = self._active_tasks.get(cleaned_file_id)
        if existing_task is not None and not existing_task.done():
            return
        self._active_tasks[cleaned_file_id] = asyncio.create_task(self.process_file(cleaned_file_id))

    async def process_file(self, file_id: str) -> None:
        cleaned_file_id = str(file_id or "").strip()
        if not cleaned_file_id:
            return
        try:
            db = SessionLocal()
            file_record = db.query(FileRecord).filter(FileRecord.id == cleaned_file_id).first()
            if file_record is None:
                return

            file_record.status = "analyzing"
            db.add(file_record)
            db.commit()
            await self.update_progress(
                cleaned_file_id,
                status="analyzing",
                progress=42,
                stage="extracting",
                message="Extracting file content",
            )

            parsed_file = await file_parser_service.parse(
                file_record.storage_path,
                original_name=file_record.original_name or file_record.filename,
                mime_type=file_record.mime_type,
            )

            await self.update_progress(
                cleaned_file_id,
                status="analyzing",
                progress=72,
                stage="embedding",
                message="Creating searchable chunks",
            )

            chunks = await retriever_service.index_file(db, file_record, parsed_file)

            file_record.extracted_text = parsed_file.text or None
            file_record.preview_text = parsed_file.preview_text
            file_record.metadata = {
                **(file_record.metadata or {}),
                **parsed_file.metadata,
            }
            file_record.chunk_count = len(chunks)
            file_record.status = "ready" if parsed_file.text else "failed"
            file_record.error = None if parsed_file.text else "No readable text could be extracted from this file."
            db.add(file_record)
            db.commit()

            await self.update_progress(
                cleaned_file_id,
                status=file_record.status,
                progress=100 if file_record.status == "ready" else 100,
                stage="ready" if file_record.status == "ready" else "failed",
                message="Ready to chat" if file_record.status == "ready" else str(file_record.error or "Processing failed"),
            )
        except Exception as exc:
            db = locals().get("db")
            if db is not None:
                file_record = db.query(FileRecord).filter(FileRecord.id == cleaned_file_id).first()
                if file_record is not None:
                    file_record.status = "failed"
                    file_record.error = str(exc)
                    db.add(file_record)
                    db.commit()
            await self.update_progress(
                cleaned_file_id,
                status="failed",
                progress=100,
                stage="failed",
                message=str(exc),
            )
        finally:
            await redis_store.remove_queue_value(settings.FILE_QUEUE_NAME, cleaned_file_id)
            db = locals().get("db")
            if db is not None:
                db.close()
            self._active_tasks.pop(cleaned_file_id, None)

    async def delete_file(self, db, *, file_record: FileRecord) -> None:
        retriever_service.delete_file_chunks(db, file_record.id)
        storage_service.delete_file(file_record.storage_path)
        db.delete(file_record)
        db.commit()
        await redis_store.delete(self._progress_key(file_record.id))

    async def serialize_file(self, db, file_record: FileRecord) -> dict[str, Any]:
        progress = await self.get_progress(file_record.id)
        metadata = file_record.metadata if isinstance(file_record.metadata, dict) else {}
        return {
            "id": file_record.id,
            "user_id": file_record.user_id,
            "session_id": file_record.session_id,
            "conversation_id": file_record.conversation_id,
            "filename": file_record.filename,
            "original_name": file_record.original_name,
            "mime_type": file_record.mime_type,
            "size": file_record.size,
            "metadata": metadata,
            "chunk_count": int(file_record.chunk_count or 0),
            "status": file_record.status,
            "error": file_record.error,
            "progress": progress,
            "preview_text": file_record.preview_text or "",
            "created_at": file_record.created_at.isoformat() if file_record.created_at else None,
            "updated_at": file_record.updated_at.isoformat() if file_record.updated_at else None,
        }


file_intelligence_service = FileIntelligenceService()
