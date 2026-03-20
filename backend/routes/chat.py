import json
import logging
import os
import re
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ai_engine import build_messages, response_envelope, select_model
from config.database import get_db
from config.settings import settings
from models.conversation import Conversation
from models.document import Document
from models.user import User
from services.ai_provider import PROVIDERS, generate_response, stream_response
from services.ai_service import ai_service
from services.conversation_store import (
    append_conversation_message,
    ensure_conversation_messages,
    history_from_conversation,
    save_conversation,
    serialize_conversation_messages,
)
from services.conversation_memory import add_message, get_history
from services.instant_responses import instant_reply
from services.search_service import fetch_page_content, format_results_for_ai, is_temporal_query, search_web
from services.vector_service import vector_service
from utils.dependencies import get_current_user, get_current_user_optional

router = APIRouter(prefix="/api/chat", tags=["Chat"])
MAX_HISTORY_MESSAGES = 12
logger = logging.getLogger(__name__)
FALLBACK_MESSAGE = (
    "I couldn't produce a reliable answer because every configured AI provider failed "
    "and no fresh supporting web results were available."
)
SETUP_RETRY_MESSAGE = "That option isn't ready just yet. Want me to try again?"
REGENERATE_VARIATION_INSTRUCTION = (
    "This is a regenerate request. Give a fresh version of the answer. "
    "Do not repeat the previous wording. Improve clarity, add a useful example, or simplify the explanation."
)
_SEARCHABLE_PROMPT_PREFIXES = (
    "who ",
    "what ",
    "when ",
    "where ",
    "which ",
    "why ",
    "how ",
    "tell me",
    "explain",
    "define",
    "give me",
)
_SPORTS_QUERY_REWRITES = (
    (re.compile(r"\bcaptions\b", re.IGNORECASE), "captains"),
    (re.compile(r"\bcaption\b", re.IGNORECASE), "captain"),
)


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = ""
    mode: str = "chat"
    provider: Optional[str] = None
    model: Optional[str] = None
    document_id: Optional[int] = None
    stream: bool = True

    model_config = ConfigDict(extra="ignore")


class RegenerateRequest(BaseModel):
    conversation_id: str
    mode: str = "chat"
    provider: Optional[str] = None
    model: Optional[str] = None
    document_id: Optional[int] = None
    stream: bool = True

    model_config = ConfigDict(extra="ignore")


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _payload(
    message: str,
    conversation: Optional[Conversation] = None,
    images: Optional[List[str]] = None,
) -> dict:
    payload = {
        "message": message,
        "answer": message,
        "images": images or [],
    }
    if conversation is not None:
        payload["conversation_id"] = conversation.id
        payload["title"] = conversation.title
    return payload


def _final_payload(
    message: str,
    conversation: Optional[Conversation] = None,
    images: Optional[List[str]] = None,
    interrupted: bool = False,
) -> dict:
    payload = _payload(message, conversation, images) | {"type": "final"}
    if interrupted:
        payload["error"] = "retry"
    return payload


def _preview_text(text: str) -> str:
    limit = int(getattr(settings, "AI_LOG_PREVIEW_CHARS", 400) or 400)
    return " ".join((text or "").split())[:limit]


def _resolve_provider_and_model(
    mode: str,
    requested_provider: Optional[str],
    requested_model: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    explicit_provider = (requested_provider or "").strip().lower() or None
    configured_provider = (settings.AI_PROVIDER or "").strip().lower() or None
    provider_for_model = explicit_provider or configured_provider
    explicit_model = (requested_model or "").strip() or None
    if explicit_model:
        return explicit_provider, explicit_model
    if provider_for_model == "openai":
        return explicit_provider, select_model(mode)
    return explicit_provider, None


def _build_ai_messages(
    history: List[dict],
    user_message: str,
    mode: str,
    doc_context: Optional[str] = None,
    extra_instruction: Optional[str] = None,
) -> List[dict]:
    ai_messages = build_messages([*history, {"role": "user", "content": user_message}], mode)
    insert_index = 1
    if extra_instruction:
        ai_messages.insert(insert_index, {"role": "system", "content": extra_instruction})
        insert_index += 1
    if doc_context:
        ai_messages.insert(insert_index, {"role": "system", "content": f"Document context:\n{doc_context[:8000]}"})
    return ai_messages


async def _collect_ai_response(
    ai_messages: List[dict],
    provider: Optional[str],
    model: Optional[str],
) -> str:
    response_text = ""
    async for chunk in ai_service.chat_stream(
        ai_messages,
        provider=provider,
        model=model,
    ):
        response_text += chunk

    response_text = response_text.strip()
    if not response_text:
        raise RuntimeError("AI provider returned an empty response")
    return response_text


def _should_use_search(message: str, force_search: bool = False) -> bool:
    cleaned = " ".join((message or "").split()).strip().lower()
    if not cleaned:
        return False
    if force_search or is_temporal_query(cleaned):
        return True
    if cleaned.endswith("?"):
        return True
    return any(cleaned.startswith(prefix) for prefix in _SEARCHABLE_PROMPT_PREFIXES)


def _build_search_query(message: str) -> str:
    search_query = " ".join((message or "").split())
    for pattern, replacement in _SPORTS_QUERY_REWRITES:
        search_query = pattern.sub(replacement, search_query)

    normalized_query = search_query.lower()
    if "ipl" in normalized_query:
        if "captain" in normalized_query:
            search_query = f"{search_query} current IPL teams and captains"
        elif "team" in normalized_query:
            search_query = f"{search_query} current IPL team list"

    return search_query


def _format_search_fallback_answer(results: List[dict]) -> str:
    top_result = results[0]
    top_summary = (top_result.get("snippet") or top_result.get("title") or "").strip()

    lines: List[str] = []
    if top_summary:
        lines.append("Best current answer I could verify from fresh web results:")
        lines.append(top_summary)
        lines.append("")
    else:
        lines.append("I couldn't use the AI model just now, but I found these current web results:")
        lines.append("")

    lines.append("Sources:")
    for index, result in enumerate(results[:3], start=1):
        title = (result.get("title") or "Untitled result").strip()
        snippet = (result.get("snippet") or "").strip()
        url = (result.get("url") or "").strip()
        meta = " | ".join(value for value in [result.get("source"), result.get("date")] if value)

        line = f"{index}. {title}"
        if meta:
            line += f" ({meta})"
        lines.append(line)
        if snippet:
            lines.append(f"   {snippet}")
        if url:
            lines.append(f"   {url}")

    return "\n".join(lines).strip()


async def _search_backup_answer(message: str, force_search: bool = False) -> Optional[str]:
    if not _should_use_search(message, force_search=force_search):
        return None

    results = await search_web(_build_search_query(message), max_results=5)
    if not results:
        return None

    return _format_search_fallback_answer(results)


async def _best_effort_answer(
    history: List[dict],
    user_message: str,
    mode: str,
    provider: Optional[str],
    model: Optional[str],
    doc_context: Optional[str] = None,
    extra_instruction: Optional[str] = None,
    force_search: bool = False,
) -> str:
    primary_message = await _maybe_enhance_temporal_message(user_message, force_search=force_search)

    try:
        primary_messages = _build_ai_messages(
            history,
            primary_message,
            mode,
            doc_context=doc_context,
            extra_instruction=extra_instruction,
        )
        return await _collect_ai_response(primary_messages, provider, model)
    except Exception as exc:
        logger.warning(
            "Primary AI answer failed mode=%s provider=%s model=%s error=%s",
            mode,
            provider or "<auto>",
            model or "<default>",
            exc,
        )

    if primary_message == user_message:
        searched_message = await _maybe_enhance_temporal_message(user_message, force_search=True)
        if searched_message != user_message:
            try:
                retry_messages = _build_ai_messages(
                    history,
                    searched_message,
                    mode,
                    doc_context=doc_context,
                    extra_instruction=extra_instruction,
                )
                return await _collect_ai_response(retry_messages, provider, model)
            except Exception as exc:
                logger.warning(
                    "Search-backed AI retry failed mode=%s provider=%s model=%s error=%s",
                    mode,
                    provider or "<auto>",
                    model or "<default>",
                    exc,
                )

    search_backup = await _search_backup_answer(user_message, force_search=force_search)
    if search_backup:
        return search_backup

    return FALLBACK_MESSAGE


def _log_chat_request(
    mode: str,
    provider: Optional[str],
    model: Optional[str],
    message: str,
    conversation_id: Optional[str] = None,
):
    logger.info(
        "Chat request mode=%s provider=%s model=%s conversation_id=%s message=%s",
        mode,
        provider or "<auto>",
        model or "<default>",
        conversation_id or "<none>",
        _preview_text(message),
    )


def _log_chat_response(
    mode: str,
    provider: Optional[str],
    model: Optional[str],
    text: str,
):
    logger.info(
        "Chat response mode=%s provider=%s model=%s chars=%s preview=%s",
        mode,
        provider or "<auto>",
        model or "<default>",
        len(text or ""),
        _preview_text(text),
    )


def _append_message(
    db: Session,
    conversation: Conversation,
    role: str,
    content: str,
    meta: Optional[dict] = None,
):
    append_conversation_message(db, conversation, role, content, meta)


def _save_conversation(db: Session, conversation: Conversation) -> Conversation:
    return save_conversation(db, conversation)


def _get_or_create_conversation(
    db: Session,
    current_user: User,
    conversation_id: Optional[str],
    first_message: str,
) -> Conversation:
    conversation = None
    if conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        ).first()

    if conversation is None:
        conversation = Conversation(
            user_id=current_user.id,
            title=first_message[:50] + "..." if len(first_message) > 50 else first_message,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    else:
        ensure_conversation_messages(db, conversation)

    return conversation


def _conversation_history(
    db: Session,
    conversation: Conversation,
    limit: int = MAX_HISTORY_MESSAGES,
    drop_last: bool = False,
) -> List[dict]:
    history = history_from_conversation(db, conversation)
    if drop_last:
        history = history[:-1]
    return history[-limit:] if limit else history


async def _maybe_enhance_temporal_message(message: str, force_search: bool = False) -> str:
    if not _should_use_search(message, force_search=force_search):
        return message

    search_query = _build_search_query(message)
    search_results = await search_web(search_query, max_results=6 if force_search else 5)
    if not search_results:
        return message

    today = datetime.utcnow().strftime("%B %d, %Y")
    search_context = format_results_for_ai(search_results)
    fetched_pages = []
    for index, result in enumerate(search_results[:2], start=1):
        url = (result.get("url") or "").strip()
        if not url:
            continue
        page_text = await fetch_page_content(url, max_chars=2000)
        if not page_text or page_text.startswith("Could not fetch page:"):
            continue
        fetched_pages.append(f"[Page {index}] {url}\n{page_text}")

    page_context = "\n\n".join(fetched_pages).strip()
    if page_context:
        search_context = f"{search_context}\nPAGE EXCERPTS:\n\n{page_context}"

    search_instruction = (
        "Search mode is enabled. Use the search results below as the primary source.\n"
        "Prefer the most recent, source-backed facts.\n"
        "If sources disagree, mention that briefly and give the best-supported answer."
        if force_search
        else "Use the search results below as the primary source for recent or year-specific facts.\n"
        "If the user asks about a specific year or range such as 2024 to 2025, prioritize results that match those years exactly."
    )

    return (
        f"Today's date is {today}.\n"
        f"{search_instruction}\n\n"
        f"{search_context}\n"
        f"User Question: {message}"
    )


@router.post("")
@router.post("/")
async def chat(
    request: ChatRequest = Body(default=ChatRequest()),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Send a chat message and get AI response."""
    mode = (request.mode or "chat").lower()
    provider_key = (request.provider or "").strip().lower()
    fallback_message = FALLBACK_MESSAGE

    if not request.message or not request.message.strip():
        payload = response_envelope("Please enter a message.")
        payload["type"] = "final"
        if request.stream:
            async def generate_empty():
                yield _sse_event(payload)

            return StreamingResponse(generate_empty(), media_type="text/event-stream")
        return payload

    if current_user is None:
        history = get_history(limit=20)
        instant = instant_reply(request.message)
        if instant:
            add_message("user", request.message)
            add_message("assistant", instant)
            payload = _payload(instant)
            if request.stream:
                async def generate_instant():
                    yield _sse_event(_final_payload(instant))

                return StreamingResponse(generate_instant(), media_type="text/event-stream")
            return payload

        force_search = mode == "search"
        enhanced_message = request.message
        if mode not in {"documents", "image"}:
            enhanced_message = await _maybe_enhance_temporal_message(request.message, force_search=force_search)

        public_messages = _build_ai_messages(history, enhanced_message, mode)
        provider, model = _resolve_provider_and_model(mode, request.provider, request.model)
        _log_chat_request(mode, provider, model, request.message)

        if provider_key in PROVIDERS and mode not in {"documents", "image"}:
            if request.stream:
                if not request.model:
                    async def generate_missing_model():
                        yield _sse_event(_final_payload(SETUP_RETRY_MESSAGE))

                    return StreamingResponse(generate_missing_model(), media_type="text/event-stream")

                env_key = PROVIDERS[provider_key]["env_key"]
                if not os.getenv(env_key):
                    async def generate_missing_key():
                        yield _sse_event(_final_payload(SETUP_RETRY_MESSAGE))

                    return StreamingResponse(generate_missing_key(), media_type="text/event-stream")

                async def generate_provider_stream():
                    full_response = ""
                    try:
                        async for chunk in stream_response(provider_key, request.model or "", public_messages):
                            full_response += chunk
                            yield _sse_event({"type": "delta", "content": chunk})
                        full_response = full_response.strip()
                        if not full_response:
                            raise RuntimeError("Provider returned an empty response")
                        _log_chat_response(mode, provider_key, request.model, full_response)
                        yield _sse_event(_final_payload(full_response))
                    except Exception as exc:
                        yield _sse_event(_final_payload(fallback_message, interrupted=True))

                return StreamingResponse(generate_provider_stream(), media_type="text/event-stream")

            if not request.model:
                return _payload(SETUP_RETRY_MESSAGE)

            try:
                answer = await generate_response(provider_key, request.model, public_messages)
                text = (answer.get("response", "") if isinstance(answer, dict) else str(answer)).strip()
                if text:
                    _log_chat_response(mode, provider_key, request.model, text)
                return _payload(text or fallback_message)
            except Exception as exc:
                logger.warning("Compatible provider public chat failed provider=%s model=%s error=%s", provider_key, request.model, exc)
                answer = await _best_effort_answer(history, request.message, mode, None, None, force_search=force_search)
                return _payload(answer)

        if mode == "documents":
            payload = response_envelope("Please log in to use document mode.")
            payload["type"] = "final"
            if request.stream:
                async def generate_login_required():
                    yield _sse_event(payload)

                return StreamingResponse(generate_login_required(), media_type="text/event-stream")
            return response_envelope("Please log in to use document mode.")

        if mode not in {"documents", "image"}:
            add_message("user", request.message)
            answer = await _best_effort_answer(
                history,
                request.message,
                mode,
                provider,
                model,
                force_search=force_search,
            )
            add_message("assistant", answer)
            _log_chat_response(mode, provider, model, answer)
            payload = _payload(answer)
            if request.stream:
                async def generate_fast():
                    yield _sse_event(_final_payload(answer))

                return StreamingResponse(generate_fast(), media_type="text/event-stream")
            return payload

        ai_messages = _build_ai_messages([], request.message, mode)

        if request.stream:
            async def generate_public():
                try:
                    if mode == "image":
                        yield _sse_event({"type": "delta", "content": "Generating image..."})
                        images = await ai_service.generate_image(request.message)
                        yield _sse_event(_final_payload("Here are your images.", images=images))
                        return

                    full_response = ""
                    async for chunk in ai_service.chat_stream(
                        ai_messages,
                        provider=provider,
                        model=model,
                    ):
                        full_response += chunk
                        yield _sse_event({"type": "delta", "content": chunk})

                    full_response = full_response.strip()
                    if not full_response:
                        raise RuntimeError("AI provider returned an empty response")
                    _log_chat_response(mode, provider, model, full_response)
                    yield _sse_event(_final_payload(full_response))
                except Exception as exc:
                    yield _sse_event(_final_payload(fallback_message, interrupted=True))

            return StreamingResponse(generate_public(), media_type="text/event-stream")

        if mode == "image":
            images = await ai_service.generate_image(request.message)
            return _payload("Here are your images.", images=images)

        try:
            response_text = await _collect_ai_response(ai_messages, provider, model)
            _log_chat_response(mode, provider, model, response_text)
            return _payload(response_text)
        except Exception as exc:
            logger.warning("Public structured chat completion failed: %s", exc)
            return _payload(fallback_message)

    conversation = _get_or_create_conversation(
        db,
        current_user,
        request.conversation_id,
        request.message,
    )
    _append_message(db, conversation, "user", request.message)
    conversation = _save_conversation(db, conversation)

    instant = instant_reply(request.message)
    if instant:
        _append_message(db, conversation, "assistant", instant)
        conversation = _save_conversation(db, conversation)
        _log_chat_response(mode, request.provider, request.model, instant)
        payload = _payload(instant, conversation)
        if request.stream:
            async def generate_instant_auth():
                yield _sse_event(_final_payload(instant, conversation))

            return StreamingResponse(generate_instant_auth(), media_type="text/event-stream")
        return payload

    provider, model = _resolve_provider_and_model(mode, request.provider, request.model)
    force_search = mode == "search"
    _log_chat_request(mode, provider, model, request.message, conversation.id)

    if provider_key in PROVIDERS and mode not in {"documents", "image"}:
        history = _conversation_history(db, conversation, drop_last=(mode not in {"documents", "image"}))
        enhanced_message = request.message
        if mode not in {"documents", "image"}:
            enhanced_message = await _maybe_enhance_temporal_message(request.message, force_search=force_search)
        provider_messages = _build_ai_messages(
            history,
            enhanced_message,
            mode,
            extra_instruction=REGENERATE_VARIATION_INSTRUCTION,
        )

        if request.stream:
            if not request.model:
                async def generate_missing_model_auth():
                    yield _sse_event(_final_payload(SETUP_RETRY_MESSAGE, conversation))

                return StreamingResponse(generate_missing_model_auth(), media_type="text/event-stream")

            env_key = PROVIDERS[provider_key]["env_key"]
            if not os.getenv(env_key):
                async def generate_missing_key_auth():
                    yield _sse_event(_final_payload(SETUP_RETRY_MESSAGE, conversation))

                return StreamingResponse(generate_missing_key_auth(), media_type="text/event-stream")

            async def generate_provider_stream_auth():
                full_response = ""
                try:
                    async for chunk in stream_response(provider_key, request.model or "", provider_messages):
                        full_response += chunk
                        yield _sse_event({"type": "delta", "content": chunk})

                    full_response = full_response.strip()
                    if not full_response:
                        raise RuntimeError("Provider returned an empty response")
                    _append_message(db, conversation, "assistant", full_response)
                    saved_conversation = _save_conversation(db, conversation)
                    _log_chat_response(mode, provider_key, request.model, full_response)
                    yield _sse_event(_final_payload(full_response, saved_conversation))
                except Exception as exc:
                    yield _sse_event(_final_payload(fallback_message, conversation, interrupted=True))

            return StreamingResponse(generate_provider_stream_auth(), media_type="text/event-stream")

        if not request.model:
            return _payload(SETUP_RETRY_MESSAGE, conversation)

        try:
            answer = await generate_response(provider_key, request.model, provider_messages)
            text = (answer.get("response", "") if isinstance(answer, dict) else str(answer)).strip()
        except Exception as exc:
            logger.warning("Compatible provider chat failed provider=%s model=%s error=%s", provider_key, request.model, exc)
            text = await _best_effort_answer(
                history,
                request.message,
                mode,
                None,
                None,
                extra_instruction=REGENERATE_VARIATION_INSTRUCTION,
                force_search=force_search,
            )

        _append_message(db, conversation, "assistant", text or fallback_message)
        conversation = _save_conversation(db, conversation)
        if text:
            _log_chat_response(mode, provider_key, request.model, text)
        return _payload(text or fallback_message, conversation)

    if mode not in {"documents", "image"}:
        history = _conversation_history(db, conversation, drop_last=True)
        answer = await _best_effort_answer(
            history,
            request.message,
            mode,
            provider,
            model,
            extra_instruction=REGENERATE_VARIATION_INSTRUCTION,
            force_search=force_search,
        )

        _append_message(db, conversation, "assistant", answer)
        conversation = _save_conversation(db, conversation)
        _log_chat_response(mode, provider, model, answer)
        payload = _payload(answer, conversation)

        if request.stream:
            async def generate_fast_auth():
                yield _sse_event(_final_payload(answer, conversation))

            return StreamingResponse(generate_fast_auth(), media_type="text/event-stream")
        return payload

    history = _conversation_history(db, conversation)
    doc_context = None
    if mode == "documents":
        if not request.document_id:
            payload = _payload("Please upload a document first.", conversation)
            if request.stream:
                async def generate_missing_doc():
                    yield _sse_event(_final_payload("Please upload a document first.", conversation))

                return StreamingResponse(generate_missing_doc(), media_type="text/event-stream")
            return payload

        document = db.query(Document).filter(
            Document.id == request.document_id,
            Document.user_id == current_user.id,
        ).first()

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        if not document.is_processed:
            raise HTTPException(status_code=400, detail="Document is still being processed")

        search_results = await vector_service.search(request.message, k=3, doc_id=document.id)
        doc_context = "\n\n".join([result[0] for result in search_results]) or document.text_content

    ai_messages = build_messages(history, mode)
    ai_messages.insert(1, {"role": "system", "content": REGENERATE_VARIATION_INSTRUCTION})
    if doc_context:
        ai_messages.insert(2, {"role": "system", "content": f"Document context:\n{doc_context[:8000]}"})

    if request.stream:
        async def generate():
            try:
                if mode == "image":
                    yield _sse_event({"type": "delta", "content": "Generating image..."})
                    images = await ai_service.generate_image(request.message)
                    _append_message(
                        db,
                        conversation,
                        "assistant",
                        "Here are your images.",
                        meta={"mode": mode, "images": images},
                    )
                    saved_conversation = _save_conversation(db, conversation)
                    _log_chat_response(mode, provider, model, "Here are your images.")
                    yield _sse_event(_final_payload("Here are your images.", saved_conversation, images=images))
                    return

                full_response = ""
                async for chunk in ai_service.chat_stream(
                    ai_messages,
                    provider=provider,
                    model=model,
                ):
                    full_response += chunk
                    yield _sse_event({"type": "delta", "content": chunk})

                full_response = full_response.strip()
                if not full_response:
                    raise RuntimeError("AI provider returned an empty response")
                _append_message(db, conversation, "assistant", full_response)
                saved_conversation = _save_conversation(db, conversation)
                _log_chat_response(mode, provider, model, full_response)
                yield _sse_event(_final_payload(full_response, saved_conversation))
            except Exception as exc:
                yield _sse_event(_final_payload(fallback_message, conversation, interrupted=True))

        return StreamingResponse(generate(), media_type="text/event-stream")

    if mode == "image":
        images = await ai_service.generate_image(request.message)
        _append_message(
            db,
            conversation,
            "assistant",
            "Here are your images.",
            meta={"mode": mode, "images": images},
        )
        conversation = _save_conversation(db, conversation)
        _log_chat_response(mode, provider, model, "Here are your images.")
        return _payload("Here are your images.", conversation, images=images)

    response_text = await _best_effort_answer(
        history,
        request.message,
        mode,
        provider,
        model,
        doc_context=doc_context,
        extra_instruction=REGENERATE_VARIATION_INSTRUCTION,
    )

    _append_message(db, conversation, "assistant", response_text)
    conversation = _save_conversation(db, conversation)
    _log_chat_response(mode, provider, model, response_text)
    return _payload(response_text, conversation)


@router.post("/regenerate")
async def regenerate(
    request: RegenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Regenerate the last assistant response in a conversation."""
    mode = (request.mode or "chat").lower()
    provider_key = (request.provider or "").strip().lower()
    fallback_message = FALLBACK_MESSAGE

    conversation = db.query(Conversation).filter(
        Conversation.id == request.conversation_id,
        Conversation.user_id == current_user.id,
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    message_records = ensure_conversation_messages(db, conversation)
    user_messages = [message for message in message_records if message.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message to regenerate")

    last_user_message_content = (user_messages[-1].content or "").strip()
    if not last_user_message_content:
        raise HTTPException(status_code=400, detail="Last user message is empty")

    if message_records and message_records[-1].role == "assistant":
        db.delete(message_records[-1])
        conversation = _save_conversation(db, conversation)

    instant = instant_reply(last_user_message_content)
    if instant:
        _append_message(db, conversation, "assistant", instant)
        conversation = _save_conversation(db, conversation)
        _log_chat_response(mode, request.provider, request.model, instant)
        payload = _payload(instant, conversation)
        if request.stream:
            async def generate_instant():
                yield _sse_event(_final_payload(instant, conversation))

            return StreamingResponse(generate_instant(), media_type="text/event-stream")
        return payload

    provider, model = _resolve_provider_and_model(mode, request.provider, request.model)
    force_search = mode == "search"
    _log_chat_request(mode, provider, model, last_user_message_content, conversation.id)

    if provider_key in PROVIDERS and mode not in {"documents", "image"}:
        history = _conversation_history(db, conversation, drop_last=(mode not in {"documents", "image"}))
        enhanced_message = last_user_message_content
        if mode not in {"documents", "image"}:
            enhanced_message = await _maybe_enhance_temporal_message(last_user_message_content, force_search=force_search)
        provider_messages = _build_ai_messages(
            history,
            enhanced_message,
            mode,
            extra_instruction=REGENERATE_VARIATION_INSTRUCTION,
        )

        if request.stream:
            if not request.model:
                async def generate_missing_model():
                    yield _sse_event(_final_payload(SETUP_RETRY_MESSAGE, conversation))

                return StreamingResponse(generate_missing_model(), media_type="text/event-stream")

            env_key = PROVIDERS[provider_key]["env_key"]
            if not os.getenv(env_key):
                async def generate_missing_key():
                    yield _sse_event(_final_payload(SETUP_RETRY_MESSAGE, conversation))

                return StreamingResponse(generate_missing_key(), media_type="text/event-stream")

            async def generate_provider_stream():
                full_response = ""
                try:
                    async for chunk in stream_response(provider_key, request.model or "", provider_messages):
                        full_response += chunk
                        yield _sse_event({"type": "delta", "content": chunk})

                    full_response = full_response.strip()
                    if not full_response:
                        raise RuntimeError("Provider returned an empty response")
                    _append_message(db, conversation, "assistant", full_response)
                    saved_conversation = _save_conversation(db, conversation)
                    _log_chat_response(mode, provider_key, request.model, full_response)
                    yield _sse_event(_final_payload(full_response, saved_conversation))
                except Exception as exc:
                    yield _sse_event(_final_payload(fallback_message, conversation, interrupted=True))

            return StreamingResponse(generate_provider_stream(), media_type="text/event-stream")

        if not request.model:
            return _payload(SETUP_RETRY_MESSAGE, conversation)

        try:
            answer = await generate_response(provider_key, request.model, provider_messages)
            text = (answer.get("response", "") if isinstance(answer, dict) else str(answer)).strip()
        except Exception as exc:
            logger.warning(
                "Compatible provider regenerate failed provider=%s model=%s error=%s",
                provider_key,
                request.model,
                exc,
            )
            text = await _best_effort_answer(
                history,
                last_user_message_content,
                mode,
                None,
                None,
                extra_instruction=REGENERATE_VARIATION_INSTRUCTION,
                force_search=force_search,
            )

        _append_message(db, conversation, "assistant", text or fallback_message)
        conversation = _save_conversation(db, conversation)
        if text:
            _log_chat_response(mode, provider_key, request.model, text)
        return _payload(text or fallback_message, conversation)

    if mode not in {"documents", "image"}:
        history = _conversation_history(db, conversation, drop_last=True)
        answer = await _best_effort_answer(
            history,
            last_user_message_content,
            mode,
            provider,
            model,
            extra_instruction=REGENERATE_VARIATION_INSTRUCTION,
            force_search=force_search,
        )

        _append_message(db, conversation, "assistant", answer)
        conversation = _save_conversation(db, conversation)
        _log_chat_response(mode, provider, model, answer)
        payload = _payload(answer, conversation)

        if request.stream:
            async def generate_fast():
                yield _sse_event(_final_payload(answer, conversation))

            return StreamingResponse(generate_fast(), media_type="text/event-stream")
        return payload

    history = _conversation_history(db, conversation)
    doc_context = None
    if mode == "documents":
        if not request.document_id:
            payload = _payload("Please upload a document first.", conversation)
            if request.stream:
                async def generate_missing_doc():
                    yield _sse_event(_final_payload("Please upload a document first.", conversation))

                return StreamingResponse(generate_missing_doc(), media_type="text/event-stream")
            return payload

        document = db.query(Document).filter(
            Document.id == request.document_id,
            Document.user_id == current_user.id,
        ).first()

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        if not document.is_processed:
            raise HTTPException(status_code=400, detail="Document is still being processed")

        search_results = await vector_service.search(last_user_message_content, k=3, doc_id=document.id)
        doc_context = "\n\n".join([result[0] for result in search_results]) or document.text_content

    ai_messages = build_messages(history, mode)
    ai_messages.insert(1, {"role": "system", "content": REGENERATE_VARIATION_INSTRUCTION})
    if doc_context:
        ai_messages.insert(2, {"role": "system", "content": f"Document context:\n{doc_context[:8000]}"})

    if request.stream:
        async def generate():
            try:
                if mode == "image":
                    yield _sse_event({"type": "delta", "content": "Generating image..."})
                    images = await ai_service.generate_image(last_user_message_content)
                    _append_message(
                        db,
                        conversation,
                        "assistant",
                        "Here are your images.",
                        meta={"mode": mode, "images": images},
                    )
                    saved_conversation = _save_conversation(db, conversation)
                    _log_chat_response(mode, provider, model, "Here are your images.")
                    yield _sse_event(_final_payload("Here are your images.", saved_conversation, images=images))
                    return

                full_response = ""
                async for chunk in ai_service.chat_stream(
                    ai_messages,
                    provider=provider,
                    model=model,
                ):
                    full_response += chunk
                    yield _sse_event({"type": "delta", "content": chunk})

                full_response = full_response.strip()
                if not full_response:
                    raise RuntimeError("AI provider returned an empty response")
                _append_message(db, conversation, "assistant", full_response)
                saved_conversation = _save_conversation(db, conversation)
                _log_chat_response(mode, provider, model, full_response)
                yield _sse_event(_final_payload(full_response, saved_conversation))
            except Exception as exc:
                yield _sse_event(_final_payload(fallback_message, conversation, interrupted=True))

        return StreamingResponse(generate(), media_type="text/event-stream")

    if mode == "image":
        images = await ai_service.generate_image(last_user_message_content)
        _append_message(
            db,
            conversation,
            "assistant",
            "Here are your images.",
            meta={"mode": mode, "images": images},
        )
        conversation = _save_conversation(db, conversation)
        _log_chat_response(mode, provider, model, "Here are your images.")
        return _payload("Here are your images.", conversation, images=images)

    response_text = await _best_effort_answer(
        history,
        last_user_message_content,
        mode,
        provider,
        model,
        doc_context=doc_context,
        extra_instruction=REGENERATE_VARIATION_INSTRUCTION,
    )
    _append_message(db, conversation, "assistant", response_text)
    conversation = _save_conversation(db, conversation)
    _log_chat_response(mode, provider, model, response_text)
    return _payload(response_text, conversation)


@router.get("/providers")
async def get_providers(
    current_user: User = Depends(get_current_user),
):
    """Return available AI providers and models."""
    return await ai_service.get_available_providers()


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all conversations for current user."""
    conversations = db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    ).order_by(Conversation.updated_at.desc()).all()

    return [
        {
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else (conv.created_at.isoformat() if conv.created_at else None),
        }
        for conv in conversations
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific conversation with messages."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    serialized_messages = serialize_conversation_messages(db, conversation)

    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else (conversation.created_at.isoformat() if conversation.created_at else None),
        "messages": serialized_messages,
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a conversation."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conversation)
    db.commit()

    return {"message": "Conversation deleted successfully"}
