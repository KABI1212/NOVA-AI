from __future__ import annotations
import asyncio
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

try:
    from sqlalchemy.orm import Session
except ImportError:
    Session = Any

from config.database import get_db
from models.conversation import Conversation
from models.file_record import FileRecord
from models.user import User
from services.ai_service import ai_service, infer_use_case
from services.conversation_store import (
    append_conversation_message,
    history_from_conversation,
    prune_conversation_from_message,
    save_conversation,
)
from services.file_intelligence import file_intelligence_service
from services.file_parser import file_parser_service
from services.retriever import retriever_service
from services.storage import storage_service
from utils.dependencies import get_current_user
from utils.format_ai_response import format_ai_response
from utils.rate_limit import enforce_chat_rate_limit


router = APIRouter(tags=["Files"])

FILE_FIRST_SYSTEM_PROMPT = (
    "You are NOVA, an AI assistant helping users understand, analyze, and solve uploaded documents (spreadsheets, PDFs, Word docs, images, text files).\n\n"
    "### MULTI-QUESTION PROCESSING AND ANSWERING RULES:\n"
    "When the uploaded document contains questions (exam paper, assignment, question bank, spreadsheet with questions, test, or any document with multiple questions), or when the user asks to answer/solve questions from the document:\n"
    "You MUST process and answer ALL questions present in the document. You must NOT randomly select, summarize, filter, or answer only a few questions.\n"
    "- If the document contains 10 questions → answer all 10 questions.\n"
    "- If the document contains 30 questions → answer all 30 questions.\n"
    "- If the document contains 100 questions → answer all 100 questions.\n\n"
    "Required Behavior:\n"
    "1. First, identify and extract EVERY question from the uploaded document.\n"
    "2. Count the total number of questions detected.\n"
    "3. Preserve the original question numbering and order.\n"
    "4. Answer every question one by one, providing both the direct answer and a comprehensive, full detailed explanation.\n"
    "5. Do NOT skip any question.\n"
    "6. Do NOT randomly select questions.\n"
    "7. Do NOT combine multiple questions into one answer unless the user explicitly asks.\n"
    "8. Do NOT summarize the document instead of answering the questions.\n"
    "9. If a question is unclear or unreadable, mention that specific question and explain that it could not be read accurately.\n"
    "10. If the document contains duplicate questions, still process them unless the user asks to remove duplicates.\n"
    "11. If the document has questions across multiple pages/sheets, scan ALL pages/sheets before generating the final answer.\n"
    "12. For Excel files, check ALL relevant sheets and rows containing questions.\n"
    "13. For each question's explanation, provide a FULL, in-depth explanation — never give a brief or one-line explanation. Thoroughly explain the concepts, step-by-step logic, working principles, formulas/derivations, or rationale.\n"
    "14. Before finishing, verify that the number of answered questions matches the number of detected questions.\n\n"
    "Required Output Format:\n"
    "Start with:\n"
    "Total questions detected: X\n\n"
    "Then provide:\n"
    "Question 1: [Original question]\n"
    "Answer: [Answer]\n"
    "Explanation: [Full, detailed, step-by-step explanation covering concepts, reasoning, mechanisms, or derivations in depth]\n\n"
    "Question 2: [Original question]\n"
    "Answer: [Answer]\n"
    "Explanation: [Full, detailed, step-by-step explanation covering concepts, reasoning, mechanisms, or derivations in depth]\n\n"
    "Question 3: [Original question]\n"
    "Answer: [Answer]\n"
    "Explanation: [Full, detailed, step-by-step explanation covering concepts, reasoning, mechanisms, or derivations in depth]\n\n"
    "Continue until EVERY question has been answered with its full detailed explanation.\n\n"
    "If the document contains more questions than can reasonably fit in one response, DO NOT skip questions. Clearly divide the output into parts:\n"
    "Part 1: Questions 1–20\n"
    "Part 2: Questions 21–40\n"
    "Part 3: Questions 41–60\n"
    "Continue until all questions are completed.\n\n"
    "Completeness Check (Self-Verification):\n"
    "- Did I process the entire uploaded document?\n"
    "- Did I check every page/sheet?\n"
    "- Did I identify all questions?\n"
    "- Did I preserve the original order?\n"
    "- Did I answer every detected question?\n"
    "- Did I accidentally skip or merge any questions?\n\n"
    "IMPORTANT: The user's uploaded document is the source of truth. Do not generate questions that are not present in the document, and do not omit questions that are present in the document.\n\n"
    "General Document Guidelines:\n"
    "- Do not expose raw internal database pointers, sheet syntax dumps, or file parsing errors.\n"
    "- For structured question-bank files with answer keys or options (e.g. Columns for A/B/C/D and Correct Answer), resolve the actual human-readable answer clearly.\n"
    "- Speak as a well-prepared expert who has thoroughly read and understood every page and sheet of the document."
)

EXPANDED_FILE_RESPONSE_MAX_TOKENS = 16384
LONG_FILE_RESPONSE_MAX_TOKENS = 8192
LONG_FILE_REQUEST_PATTERN = re.compile(
    r"\b(?:long|detailed|complete|full|comprehensive|all|every|code|program|script|assignment|report|essay|questions?|answers?|solve|solve all)\b",
    re.IGNORECASE,
)


class FileChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    edit_from_message_id: str | None = None
    session_id: str | None = None
    provider: str | None = None
    model: str | None = None
    custom_system_prompt: str | None = None
    file_ids: list[str] | None = None
    stream: bool = True

    model_config = ConfigDict(extra="ignore")


def _conversation_title(message: str) -> str:
    cleaned = " ".join((message or "").split()).strip()
    if not cleaned:
        return "New Chat"
    return cleaned[:57] + "..." if len(cleaned) > 60 else cleaned


def _normalize_custom_system_prompt(value: str | None) -> str:
    return str(value or "").strip()[:2000]


def _create_conversation(db: Session, *, user_id: int, title: str) -> Conversation:
    conversation = Conversation(
        user_id=user_id,
        title=title or "New Chat",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


async def _collect_completion(
    messages: list[dict[str, str]],
    *,
    provider: str | None,
    model: str | None,
    use_case: str,
    max_tokens: int | None = None,
) -> str:
    chunks: list[str] = []
    async for chunk in ai_service.chat_completion(
        messages,
        stream=False,
        provider=provider,
        model=model,
        max_tokens=max_tokens,
        use_case=use_case,
    ):
        if chunk:
            chunks.append(chunk)
    return "".join(chunks).strip()


def _sse_event(payload: dict[str, Any]) -> str:
    import json

    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _stream_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


def _sse_comment(value: str = "keepalive") -> str:
    return f": {value}\n\n"


def _finalize_answer(text: str) -> str:
    answer = str(text or "").strip()
    if answer.count("```") % 2 == 1:
        answer = f"{answer.rstrip()}\n```"
    answer = re.sub(r"(?m)\n?\s*(?:[-*+]|\d+[.)])\s*$", "", answer.rstrip()).strip()
    return answer


def _looks_unfinished_answer(text: str) -> bool:
    answer = str(text or "").strip()
    if not answer:
        return True
    if answer.count("```") % 2 == 1:
        return True
    if re.search(r"(?m)(?:^|\n)\s*(?:[-*+]|\d+[.)])\s*$", answer):
        return True
    if re.search(r"(?:\b(?:and|or|the|a|an|to|with|for|because|while|if|when|where|which|that|this|from)|[,;:])$", answer, re.I):
        return True
    return False


def _continuation_messages(messages: list[dict[str, str]], partial_answer: str) -> list[dict[str, str]]:
    return [
        *messages,
        {"role": "assistant", "content": partial_answer[-6000:]},
        {
            "role": "user",
            "content": (
                "Continue the previous answer exactly from where it stopped. "
                "Do not restart, do not repeat earlier text, and close any open markdown or code blocks."
            ),
        },
    ]


async def _stream_file_completion(
    messages: list[dict[str, str]],
    *,
    provider: str | None,
    model: str | None,
    max_tokens: int | None,
    use_case: str,
):
    heartbeat_seconds = 15
    full_response = ""
    yield _sse_event({"type": "start"}), full_response

    provider_stream = ai_service.chat_stream(
        messages,
        provider=provider,
        model=model,
        max_tokens=max_tokens,
        use_case=use_case,
    ).__aiter__()
    pending_chunk = None
    try:
        while True:
            if pending_chunk is None:
                pending_chunk = asyncio.create_task(provider_stream.__anext__())
            try:
                chunk = await asyncio.wait_for(asyncio.shield(pending_chunk), timeout=heartbeat_seconds)
            except asyncio.TimeoutError:
                yield _sse_comment(), full_response
                continue
            except StopAsyncIteration:
                break

            pending_chunk = None
            if not chunk:
                continue
            full_response += chunk
            yield _sse_event({"type": "delta", "content": chunk}), full_response
    except Exception:
        if not full_response:
            raise

    for _ in range(2):
        if not _looks_unfinished_answer(full_response):
            break
        try:
            async for chunk in ai_service.chat_stream(
                _continuation_messages(messages, full_response),
                provider=None,
                model=None,
                max_tokens=min(8000, max_tokens or 8000),
                use_case=use_case,
            ):
                if not chunk:
                    continue
                full_response += chunk
                yield _sse_event({"type": "delta", "content": chunk}), full_response
        except Exception:
            break


def _file_response_max_tokens(message: str, has_context: bool) -> int:
    if has_context:
        if LONG_FILE_REQUEST_PATTERN.search(message or ""):
            return EXPANDED_FILE_RESPONSE_MAX_TOKENS
        return LONG_FILE_RESPONSE_MAX_TOKENS
    return 8000


async def _serialize_records(db: Session, records: list[FileRecord]) -> list[dict[str, Any]]:
    results = []
    for record in records:
        results.append(await file_intelligence_service.serialize_file(db, record))
    return results


@router.post("/api/files/upload")
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(...),
    session_id: str = Form(""),
    conversation_id: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uploaded_records: list[FileRecord] = []

    for upload in files:
        if upload is None:
            continue
        content = await upload.read()
        try:
            extension, mime_type = file_parser_service.validate_upload(
                filename=upload.filename or "file",
                mime_type=upload.content_type or "",
                size=len(content),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        storage_info = await storage_service.save_upload(
            user_id=current_user.id,
            original_name=upload.filename or "file",
            content=content,
        )
        scan_result = await storage_service.run_malware_scan(storage_info["storage_path"])
        if scan_result.get("status") == "flagged":
            storage_service.delete_file(storage_info["storage_path"])
            raise HTTPException(status_code=400, detail="The uploaded file was blocked by the malware scan policy.")

        record = FileRecord(
            user_id=current_user.id,
            session_id=str(session_id or request.headers.get("X-Session-ID", "") or "").strip(),
            conversation_id=str(conversation_id or "").strip() or None,
            filename=storage_info["filename"],
            original_name=storage_info["original_name"],
            mime_type=mime_type or storage_info["mime_type"],
            extension=extension or storage_info["extension"],
            size=len(content),
            storage_path=storage_info["storage_path"],
            metadata={
                "scan": scan_result,
            },
            status="uploaded",
        )
        db.add(record)
        uploaded_records.append(record)

    if not uploaded_records:
        raise HTTPException(status_code=400, detail="Select at least one file to upload.")

    db.commit()
    for record in uploaded_records:
        db.refresh(record)

    if uploaded_records[0].session_id:
        await file_intelligence_service.remember_session_files(
            db,
            user_id=current_user.id,
            session_id=uploaded_records[0].session_id,
            conversation_id=uploaded_records[0].conversation_id,
            file_ids=[record.id for record in uploaded_records],
        )

    for record in uploaded_records:
        await file_intelligence_service.update_progress(
            record.id,
            status="uploaded",
            progress=10,
            stage="uploaded",
            message="Upload complete",
        )
        await file_intelligence_service.enqueue_processing(record.id)

    return {
        "files": await _serialize_records(db, uploaded_records),
    }


@router.post("/api/files/process/{file_id}")
async def process_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_record = db.query(FileRecord).filter(
        FileRecord.id == file_id,
        FileRecord.user_id == current_user.id,
    ).first()
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found.")

    await file_intelligence_service.enqueue_processing(file_record.id)
    db.refresh(file_record)
    return await file_intelligence_service.serialize_file(db, file_record)


@router.get("/api/files/list")
async def list_files(
    session_id: str = "",
    conversation_id: str = "",
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters: dict[str, Any] = {"user_id": current_user.id}
    if session_id.strip():
        filters["session_id"] = session_id.strip()
    if conversation_id.strip():
        filters["conversation_id"] = conversation_id.strip()

    page_number = max(1, int(page or 1))
    per_page = max(1, min(int(page_size or 20), 50))
    skip = (page_number - 1) * per_page

    collection = db.collection_for(FileRecord)
    total = collection.count_documents(filters)
    payloads = list(
        collection.find(filters).sort("created_at", -1).skip(skip).limit(per_page)
    )
    records = [db.attach(FileRecord.from_mongo(payload, db)) for payload in payloads]
    return {
        "items": await _serialize_records(db, records),
        "page": page_number,
        "page_size": per_page,
        "total": total,
        "has_more": skip + len(records) < total,
    }


@router.get("/api/files/{file_id}")
async def get_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_record = db.query(FileRecord).filter(
        FileRecord.id == file_id,
        FileRecord.user_id == current_user.id,
    ).first()
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found.")
    return await file_intelligence_service.serialize_file(db, file_record)


@router.delete("/api/files/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_record = db.query(FileRecord).filter(
        FileRecord.id == file_id,
        FileRecord.user_id == current_user.id,
    ).first()
    if file_record is None:
        return {"message": "File already removed."}

    await file_intelligence_service.delete_file(db, file_record=file_record)
    return {"message": "File deleted successfully."}


@router.post("/api/chat/with-files")
async def chat_with_files(
    request_body: FileChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    await enforce_chat_rate_limit(request, current_user)

    message_text = " ".join((request_body.message or "").split()).strip()
    if not message_text:
        message_text = "Please process this document and answer all questions present in it."

    conversation = None
    if request_body.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == request_body.conversation_id,
            Conversation.user_id == current_user.id,
        ).first()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")

    if conversation is None:
        conversation = _create_conversation(
            db,
            user_id=current_user.id,
            title=_conversation_title(message_text),
        )

    if request_body.edit_from_message_id:
        prune_conversation_from_message(db, conversation, request_body.edit_from_message_id)

    requested_file_ids = [str(file_id or "").strip() for file_id in request_body.file_ids or [] if str(file_id or "").strip()]
    active_file_ids = requested_file_ids or await file_intelligence_service.session_file_ids(
        db,
        user_id=current_user.id,
        session_id=request_body.session_id or request.headers.get("X-Session-ID", ""),
        conversation_id=conversation.id,
    )

    file_payloads = list(
        db.collection_for(FileRecord).find(
            {
                "id": {"$in": active_file_ids or ["__none__"]},
                "user_id": current_user.id,
            }
        )
    )
    ready_files = [payload for payload in file_payloads if str(payload.get("status") or "") == "ready"]
    pending_files = [payload for payload in file_payloads if str(payload.get("status") or "") in {"uploaded", "queued", "analyzing"}]

    if active_file_ids and not ready_files and pending_files:
        raise HTTPException(status_code=409, detail="Your uploaded files are still being analyzed.")

    append_conversation_message(
        db,
        conversation,
        "user",
        message_text,
        meta={
            "file_ids": [str(payload.get("id")) for payload in ready_files],
            "mode": "files",
        },
    )
    conversation = save_conversation(db, conversation)

    if request_body.session_id:
        await file_intelligence_service.remember_session_files(
            db,
            user_id=current_user.id,
            session_id=request_body.session_id,
            conversation_id=conversation.id,
            file_ids=[str(payload.get("id")) for payload in file_payloads],
        )
        db.collection_for(FileRecord).update_many(
            {
                "user_id": current_user.id,
                "id": {"$in": [str(payload.get("id")) for payload in file_payloads]},
                "$or": [
                    {"conversation_id": None},
                    {"conversation_id": ""},
                ],
            },
            {"$set": {"conversation_id": conversation.id}},
        )

    full_docs_parts: list[str] = []
    total_extracted_len = 0
    for payload in ready_files:
        doc_text = str(payload.get("extracted_text") or "").strip()
        name = str(payload.get("original_name") or payload.get("filename") or "Uploaded document")
        if doc_text:
            full_docs_parts.append(f"=== Document: {name} ===\n{doc_text}")
            total_extracted_len += len(doc_text)

    hits = await retriever_service.retrieve(
        db,
        user_id=current_user.id,
        query=message_text,
        file_ids=[str(payload.get("id")) for payload in ready_files],
        limit=6,
    ) if ready_files else []
    retrieved_context, citations = retriever_service.build_context(hits)

    if full_docs_parts and total_extracted_len <= 120000:
        file_context = "\n\n".join(full_docs_parts)
    elif full_docs_parts:
        expanded_hits = await retriever_service.retrieve(
            db,
            user_id=current_user.id,
            query=message_text,
            file_ids=[str(payload.get("id")) for payload in ready_files],
            limit=40,
        )
        expanded_context, _ = retriever_service.build_context(expanded_hits, max_chars=120000)
        file_context = expanded_context or retrieved_context
    else:
        file_context = retrieved_context

    history = history_from_conversation(db, conversation, limit=12)
    history = history[:-1] if history and history[-1]["role"] == "user" and history[-1]["content"] == message_text else history

    messages = [{"role": "system", "content": FILE_FIRST_SYSTEM_PROMPT}]
    custom_system_prompt = _normalize_custom_system_prompt(request_body.custom_system_prompt)
    if custom_system_prompt:
        messages.append({"role": "system", "content": custom_system_prompt})
    if file_context:
        messages.append({"role": "system", "content": f"Uploaded file context:\n{file_context}"})
    messages.extend(history)
    messages.append({"role": "user", "content": message_text})

    use_case = "document" if file_context else infer_use_case("chat", message_text)
    response_max_tokens = _file_response_max_tokens(message_text, bool(file_context))

    if request_body.stream:
        async def generate() -> Any:
            full_response = ""
            try:
                async for event, full_response in _stream_file_completion(
                    messages,
                    provider=request_body.provider,
                    model=request_body.model,
                    max_tokens=response_max_tokens,
                    use_case=use_case,
                ):
                    yield event

                final_answer = _finalize_answer(full_response)
                if not final_answer:
                    raise RuntimeError("AI provider returned an empty response")
                final_answer = format_ai_response(final_answer) or final_answer
                append_conversation_message(
                    db,
                    conversation,
                    "assistant",
                    final_answer,
                    meta={
                        "sources": citations,
                        "answer_source": "file" if file_context else "general",
                        "mode": "files",
                    },
                )
                save_conversation(db, conversation)
                yield _sse_event(
                    {
                        "type": "final",
                        "answer": final_answer,
                        "conversation_id": conversation.id,
                        "sources": citations,
                        "answer_source": "file" if file_context else "general",
                    }
                )
            except Exception as exc:
                final_answer = _finalize_answer(full_response)
                if final_answer:
                    final_answer = format_ai_response(final_answer) or final_answer
                    append_conversation_message(
                        db,
                        conversation,
                        "assistant",
                        final_answer,
                        meta={
                            "sources": citations,
                            "answer_source": "file" if file_context else "general",
                            "mode": "files",
                            "interrupted": True,
                        },
                    )
                    save_conversation(db, conversation)
                    yield _sse_event(
                        {
                            "type": "final",
                            "answer": final_answer,
                            "conversation_id": conversation.id,
                            "sources": citations,
                            "answer_source": "file" if file_context else "general",
                            "error": "partial",
                        }
                    )
                    return
                yield _sse_event(
                    {
                        "type": "final",
                        "answer": "NOVA AI could not finish that file answer. Please try again.",
                        "conversation_id": conversation.id,
                        "sources": citations,
                        "answer_source": "file" if file_context else "general",
                        "error": "retry",
                    }
                )

        return StreamingResponse(generate(), media_type="text/event-stream", headers=_stream_headers())

    answer = await _collect_completion(
        messages,
        provider=request_body.provider,
        model=request_body.model,
        use_case=use_case,
        max_tokens=response_max_tokens,
    )
    answer = _finalize_answer(answer)
    answer = format_ai_response(answer) or answer
    append_conversation_message(
        db,
        conversation,
        "assistant",
        answer,
        meta={
            "sources": citations,
            "answer_source": "file" if file_context else "general",
            "mode": "files",
        },
    )
    save_conversation(db, conversation)
    return {
        "answer": answer,
        "conversation_id": conversation.id,
        "sources": citations,
        "answer_source": "file" if file_context else "general",
    }
