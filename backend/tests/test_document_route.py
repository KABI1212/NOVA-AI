from __future__ import annotations

import asyncio
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile

import routes.document as document_module


class _FakeWriteSession:
    def __init__(self) -> None:
        self.saved_document = None
        self.commit_count = 0

    def add(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = 101
        self.saved_document = obj

    def commit(self) -> None:
        self.commit_count += 1

    def refresh(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = 101
        self.saved_document = obj


class _FakeQuery:
    def __init__(self, document) -> None:
        self.document = document

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.document


class _FakeReadSession:
    def __init__(self, document) -> None:
        self.document = document

    def query(self, model):
        return _FakeQuery(self.document)


def test_upload_document_falls_back_to_preview_summary_when_enrichment_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db = _FakeWriteSession()
    current_user = SimpleNamespace(id=7)

    async def fake_save_file(file_content: bytes, filename: str) -> str:
        return f"./uploads/{filename}"

    async def fake_process_document(file_path: str, file_type: str) -> str:
        return "Important course notes about operating systems and process scheduling."

    async def failing_summary(text: str) -> str:
        raise RuntimeError("summary provider unavailable")

    async def failing_upsert(text: str, doc_id: int) -> None:
        raise RuntimeError("embeddings unavailable")

    monkeypatch.setattr(document_module.document_service, "save_file", fake_save_file)
    monkeypatch.setattr(document_module.document_service, "process_document", fake_process_document)
    monkeypatch.setattr(document_module.ai_service, "summarize_document", failing_summary)
    monkeypatch.setattr(document_module.vector_service, "upsert_document", failing_upsert)

    async def scenario() -> None:
        upload = UploadFile(filename="notes.txt", file=BytesIO(b"hello world"))
        result = await document_module.upload_document(
            file=upload,
            current_user=current_user,
            db=fake_db,
        )

        assert result["is_processed"] is True
        assert result["summary"].startswith("Summary is unavailable right now.")
        assert "operating systems" in result["summary"].lower()
        assert fake_db.saved_document.text_content.startswith("Important course notes")

    asyncio.run(scenario())


def test_upload_document_marks_unreadable_files_as_needing_attention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db = _FakeWriteSession()
    current_user = SimpleNamespace(id=7)

    async def fake_save_file(file_content: bytes, filename: str) -> str:
        return f"./uploads/{filename}"

    async def empty_process_document(file_path: str, file_type: str) -> str:
        return "   \n\t"

    monkeypatch.setattr(document_module.document_service, "save_file", fake_save_file)
    monkeypatch.setattr(document_module.document_service, "process_document", empty_process_document)

    async def scenario() -> None:
        upload = UploadFile(filename="scan.pdf", file=BytesIO(b"%PDF-1.4"))
        result = await document_module.upload_document(
            file=upload,
            current_user=current_user,
            db=fake_db,
        )

        assert result["is_processed"] is False
        assert "No readable text could be extracted" in result["summary"]

    asyncio.run(scenario())


def test_ask_question_returns_document_summary_when_document_is_not_ready() -> None:
    current_user = SimpleNamespace(id=7)
    document = SimpleNamespace(
        id=14,
        user_id=7,
        is_processed=False,
        summary="No readable text could be extracted from this file.",
        text_content=None,
        filename="scan.pdf",
    )
    fake_db = _FakeReadSession(document)

    async def scenario() -> None:
        with pytest.raises(HTTPException) as exc_info:
            await document_module.ask_question(
                request=document_module.AskQuestionRequest(document_id=14, question="Explain this"),
                current_user=current_user,
                db=fake_db,
            )

        assert exc_info.value.status_code == 400
        assert "No readable text could be extracted" in exc_info.value.detail

    asyncio.run(scenario())


def test_ask_question_falls_back_to_document_excerpt_when_ai_is_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_user = SimpleNamespace(id=7)
    document = SimpleNamespace(
        id=22,
        user_id=7,
        is_processed=True,
        summary="Scheduling notes",
        text_content=(
            "Process scheduling decides which process should run next on the CPU.\n\n"
            "The scheduler improves responsiveness, throughput, and fair CPU sharing."
        ),
        filename="os-notes.txt",
    )
    fake_db = _FakeReadSession(document)

    async def fake_ensure_document(text: str, doc_id: int) -> None:
        return None

    async def fake_search(question: str, k: int, doc_id: int):
        return [
            ("Process scheduling decides which process should run next on the CPU.", 0.92),
            ("The scheduler improves responsiveness, throughput, and fair CPU sharing.", 0.88),
        ]

    async def offline_answer(question: str, context: str, max_context_chars: int = 20000) -> str:
        return "NOVA AI is running in offline mode. Configure an AI provider."

    monkeypatch.setattr(document_module.vector_service, "ensure_document", fake_ensure_document)
    monkeypatch.setattr(document_module.vector_service, "search", fake_search)
    monkeypatch.setattr(document_module.ai_service, "answer_question_from_document", offline_answer)

    async def scenario() -> None:
        result = await document_module.ask_question(
            request=document_module.AskQuestionRequest(
                document_id=22,
                question="What does process scheduling do?",
            ),
            current_user=current_user,
            db=fake_db,
        )

        assert result["answer_mode"] == "fallback"
        assert "document fallback mode" in result["answer"].lower()
        assert "process scheduling decides which process should run next on the cpu" in result["answer"].lower()

    asyncio.run(scenario())


def test_rewrite_question_falls_back_to_cleaned_question_when_ai_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_user = SimpleNamespace(id=7)

    async def failing_rewrite(question: str) -> str:
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(document_module.ai_service, "rewrite_document_question", failing_rewrite)

    async def scenario() -> None:
        result = await document_module.rewrite_question(
            request=document_module.RewriteQuestionRequest(
                question="  explain ratio and proportion in simple words  "
            ),
            current_user=current_user,
        )

        assert result["rewrite_mode"] == "fallback"
        assert result["rewritten_question"] == "Explain ratio and proportion in simple words?"

    asyncio.run(scenario())
