from fastapi import APIRouter, Depends, HTTPException, Body
import os
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
import json
from config.database import get_db
from config.settings import settings
from models.user import User
from models.conversation import Conversation
from models.document import Document
from services.ai_service import ai_service
from services.ai_provider import generate_response, stream_response, PROVIDERS
from services.vector_service import vector_service
from services.instant_responses import instant_reply
from services.conversation_memory import add_message, get_history
from services.ai_router import generate_answer
from utils.dependencies import get_current_user, get_current_user_optional
from ai_engine import build_messages, select_model, response_envelope

router = APIRouter(prefix="/api/chat", tags=["Chat"])
MAX_HISTORY_MESSAGES = 12


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


@router.post("")
@router.post("/")
async def chat(
    request: ChatRequest = Body(default=ChatRequest()),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Send a chat message and get AI response"""
    mode = (request.mode or "chat").lower()
    fallback_message = "NOVA AI encountered an issue but is still running."

    def sse_event(payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    if not request.message or not request.message.strip():
        if request.stream:
            async def generate_empty():
                yield sse_event(response_envelope("Please enter a message.") | {"type": "final"})
            return StreamingResponse(generate_empty(), media_type="text/event-stream")
        return response_envelope("Please enter a message.")

    instant = instant_reply(request.message)
    if instant:
        add_message("user", request.message)
        add_message("assistant", instant)
        if request.stream:
            async def generate_instant():
                yield sse_event({"type": "final", "message": instant, "answer": instant})

            return StreamingResponse(generate_instant(), media_type="text/event-stream")
        return {"message": instant, "answer": instant}

    provider_key = (request.provider or "").strip().lower()
    if provider_key in PROVIDERS:
        add_message("user", request.message)
        if request.stream:
            if not request.model:
                async def generate_missing_model():
                    yield sse_event(response_envelope("Model is required.") | {"type": "final"})

                return StreamingResponse(generate_missing_model(), media_type="text/event-stream")

            env_key = PROVIDERS[provider_key]["env_key"]
            if not os.getenv(env_key):
                async def generate_missing_key():
                    yield sse_event(response_envelope("Missing API key for provider.") | {"type": "final"})

                return StreamingResponse(generate_missing_key(), media_type="text/event-stream")

            async def generate_provider_stream():
                full_response = ""
                try:
                    async for chunk in stream_response(provider_key, request.model or "", request.message):
                        full_response += chunk
                        yield sse_event({"type": "delta", "content": chunk})

                    yield sse_event(response_envelope(full_response) | {"type": "final"})
                except Exception as exc:
                    yield sse_event(
                        response_envelope(fallback_message) | {"type": "final", "error": str(exc)}
                    )

            return StreamingResponse(generate_provider_stream(), media_type="text/event-stream")

        answer = await generate_response(provider_key, request.model or "", request.message)
        if isinstance(answer, dict):
            add_message("assistant", answer.get("response", ""))
        return answer

    if mode not in {"documents", "image"}:
        add_message("user", request.message)
        history = get_history(limit=20)
        answer = await generate_answer(request.message, history)
        add_message("assistant", answer)
        payload = {"message": answer, "answer": answer}

        if request.stream:
            async def generate_fast():
                yield sse_event(payload | {"type": "final"})

            return StreamingResponse(generate_fast(), media_type="text/event-stream")

        return payload

    if current_user is None:
        if mode == "documents":
            if request.stream:
                async def generate_login_required():
                    yield sse_event(response_envelope("Please log in to use document mode.") | {"type": "final"})
                return StreamingResponse(generate_login_required(), media_type="text/event-stream")
            return response_envelope("Please log in to use document mode.")

        ai_messages = build_messages([{"role": "user", "content": request.message}], mode)
        provider = (request.provider or settings.AI_PROVIDER or "openai").lower()
        requested_model = (request.model or "").strip() or None
        default_model = select_model(mode)
        model = requested_model or (default_model if provider == "openai" else None)

        if request.stream:
            async def generate_public():
                try:
                    if mode == "image":
                        yield sse_event({"type": "delta", "content": "Generating image..."})
                        images = await ai_service.generate_image(request.message)
                        yield sse_event(response_envelope("Here are your images.", images=images) | {"type": "final"})
                        return

                    full_response = ""
                    async for chunk in ai_service.chat_stream(
                        ai_messages,
                        provider=provider,
                        model=model
                    ):
                        full_response += chunk
                        yield sse_event({"type": "delta", "content": chunk})

                    yield sse_event(response_envelope(full_response) | {"type": "final"})
                except Exception as exc:
                    yield sse_event(
                        response_envelope(fallback_message) | {"type": "final", "error": str(exc)}
                    )

            return StreamingResponse(generate_public(), media_type="text/event-stream")

        if mode == "image":
            images = await ai_service.generate_image(request.message)
            return response_envelope("Here are your images.", images=images)

        try:
            response_text = ""
            async for chunk in ai_service.chat_stream(
                ai_messages,
                provider=provider,
                model=model
            ):
                response_text += chunk
            return response_envelope(response_text)
        except Exception:
            return response_envelope(fallback_message)

    # Get or create conversation
    if request.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id,
            Conversation.user_id == current_user.id
        ).first()
    else:
        conversation = None

    if not conversation:
        # Create new conversation if missing or not provided
        conversation = Conversation(
            user_id=current_user.id,
            title=request.message[:50] + "..." if len(request.message) > 50 else request.message
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # Save user message
    conversation.messages.append({"role": "user", "content": request.message})
    db.add(conversation)
    db.commit()

    # Get conversation history
    history = conversation.messages[-MAX_HISTORY_MESSAGES:]
    doc_context = None
    if mode == "documents":
        if not request.document_id:
            if request.stream:
                async def generate_missing_doc():
                    yield sse_event(response_envelope("Please upload a document first.") | {"type": "final"})
                return StreamingResponse(generate_missing_doc(), media_type="text/event-stream")
            return response_envelope("Please upload a document first.")

        document = db.query(Document).filter(
            Document.id == request.document_id,
            Document.user_id == current_user.id
        ).first()

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        if not document.is_processed:
            raise HTTPException(status_code=400, detail="Document is still being processed")

        search_results = await vector_service.search(request.message, k=3, doc_id=document.id)
        doc_context = "\n\n".join([result[0] for result in search_results]) or document.text_content

    ai_messages = build_messages(history, mode)
    if doc_context:
        ai_messages.insert(1, {"role": "system", "content": f"Document context:\n{doc_context[:8000]}"})
    provider = (request.provider or settings.AI_PROVIDER or "openai").lower()
    requested_model = (request.model or "").strip() or None
    default_model = select_model(mode)
    model = requested_model or (default_model if provider == "openai" else None)

    # Stream response
    if request.stream:
        async def generate():
            try:
                if mode == "image":
                    yield sse_event({"type": "delta", "content": "Generating image..."})
                    images = await ai_service.generate_image(request.message)
                    assistant_message_data = {"role": "assistant", "content": "Here are your images.", "meta": {"mode": mode, "images": images}}
                    conversation.messages.append(assistant_message_data)
                    db.add(conversation)
                    db.commit()
                    yield sse_event(response_envelope("Here are your images.", images=images) | {"type": "final"})
                    return

                full_response = ""
                async for chunk in ai_service.chat_stream(
                    ai_messages,
                    provider=provider,
                    model=model
                ):
                    full_response += chunk
                    yield sse_event({"type": "delta", "content": chunk})

                # Save assistant message after streaming
                conversation.messages.append({"role": "assistant", "content": full_response})
                db.add(conversation)
                db.commit()

                yield sse_event(response_envelope(full_response) | {"type": "final"})
            except Exception as exc:
                yield sse_event(
                    response_envelope(fallback_message) | {"type": "final", "error": str(exc)}
                )

        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        if mode == "image":
            images = await ai_service.generate_image(request.message)
            conversation.messages.append({"role": "assistant", "content": "Here are your images.", "meta": {"mode": mode, "images": images}})
            db.add(conversation)
            db.commit()
            return response_envelope("Here are your images.", images=images)

        try:
            # Non-streaming response (use provider-aware stream and aggregate)
            response_text = ""
            async for chunk in ai_service.chat_stream(
                ai_messages,
                provider=provider,
                model=model
            ):
                response_text += chunk

            # Save assistant message
            conversation.messages.append({"role": "assistant", "content": response_text})
            db.add(conversation)
            db.commit()

            return response_envelope(response_text)
        except Exception:
            return response_envelope(fallback_message)


@router.post("/regenerate")
async def regenerate(
    request: RegenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Regenerate the last assistant response in a conversation"""
    mode = (request.mode or "chat").lower()

    def sse_event(payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    conversation = db.query(Conversation).filter(
        Conversation.id == request.conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Find the last user message from the JSON list
    user_messages = [m for m in conversation.messages if m.get("role") == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message to regenerate")
    
    last_user_message_content = user_messages[-1].get("content", "")
    if not last_user_message_content:
        raise HTTPException(status_code=400, detail="Last user message is empty")

    if conversation.messages and conversation.messages[-1].get("role") == "assistant":
        conversation.messages.pop()
        db.add(conversation)
        db.commit()

    history = conversation.messages[-MAX_HISTORY_MESSAGES:]
    doc_context = None
    if mode == "documents":
        if not request.document_id:
            if request.stream:
                async def generate_missing_doc():
                    yield sse_event(response_envelope("Please upload a document first.") | {"type": "final"})
                return StreamingResponse(generate_missing_doc(), media_type="text/event-stream")
            return response_envelope("Please upload a document first.")

        document = db.query(Document).filter(
            Document.id == request.document_id,
            Document.user_id == current_user.id
        ).first()

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        if not document.is_processed:
            raise HTTPException(status_code=400, detail="Document is still being processed")

        search_results = await vector_service.search(last_user_message_content, k=3, doc_id=document.id)
        doc_context = "\n\n".join([result[0] for result in search_results]) or document.text_content

    ai_messages = build_messages(history, mode)
    if doc_context:
        ai_messages.insert(1, {"role": "system", "content": f"Document context:\n{doc_context[:8000]}"})
    provider = (request.provider or settings.AI_PROVIDER or "openai").lower()
    requested_model = (request.model or "").strip() or None
    default_model = select_model(mode)
    model = requested_model or (default_model if provider == "openai" else None)

    if request.stream:
        async def generate():
            if mode == "image":
                yield sse_event({"type": "delta", "content": "Generating image..."})
                images = await ai_service.generate_image(last_user_message_content)
                assistant_message_data = {"role": "assistant", "content": "Here are your images.", "meta": {"mode": mode, "images": images}}
                conversation.messages.append(assistant_message_data)
                db.add(conversation)
                db.commit()
                yield sse_event(response_envelope("Here are your images.", images=images) | {"type": "final"})
                return

            full_response = ""
            async for chunk in ai_service.chat_stream(
                ai_messages,
                provider=provider,
                model=model
            ):
                full_response += chunk
                yield sse_event({"type": "delta", "content": chunk})

            assistant_message_data = {"role": "assistant", "content": full_response}
            conversation.messages.append(assistant_message_data)
            db.add(conversation)
            db.commit()

            yield sse_event(response_envelope(full_response) | {"type": "final"})

        return StreamingResponse(generate(), media_type="text/event-stream")

    if mode == "image":
        images = await ai_service.generate_image(last_user_message_content)
        conversation.messages.append({"role": "assistant", "content": "Here are your images.", "meta": {"mode": mode, "images": images}})
        db.add(conversation)
        db.commit()
        return response_envelope("Here are your images.", images=images)

    response_text = ""
    async for chunk in ai_service.chat_stream(
        ai_messages,
        provider=provider,
        model=model
    ):
        response_text += chunk

    conversation.messages.append({"role": "assistant", "content": response_text})
    db.add(conversation)
    db.commit()

    return response_envelope(response_text)


@router.get("/providers")
async def get_providers(
    current_user: User = Depends(get_current_user)
):
    """Return available AI providers and models"""
    return await ai_service.get_available_providers()


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all conversations for current user"""
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
    db: Session = Depends(get_db)
):
    """Get a specific conversation with messages"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = conversation.messages

    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else (conversation.created_at.isoformat() if conversation.created_at else None),
        "messages": [
            {
                "role": msg.get("role"),
                "content": msg.get("content"),
                "images": msg.get("images") or (msg.get("meta") or {}).get("images") if msg.get("role") == "assistant" else None,
                "meta": msg.get("meta")
            }
            for msg in messages
        ]
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a conversation"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conversation)
    db.commit()

    return {"message": "Conversation deleted successfully"}
