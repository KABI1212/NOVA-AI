from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
import json
from config.database import get_db
from config.settings import settings
from models.user import User
from models.conversation import Conversation, Message
from models.document import Document
from services.ai_service import ai_service
from services.vector_service import vector_service
from utils.dependencies import get_current_user
from ai_engine import build_messages, select_model, response_envelope

router = APIRouter(prefix="/api/chat", tags=["Chat"])
MAX_HISTORY_MESSAGES = 12


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    conversation_id: Optional[int] = None
    message: str = ""
    mode: str = "chat"
    provider: Optional[str] = None
    document_id: Optional[int] = None
    stream: bool = True

    model_config = ConfigDict(extra="ignore")


class RegenerateRequest(BaseModel):
    conversation_id: int
    mode: str = "chat"
    provider: Optional[str] = None
    document_id: Optional[int] = None
    stream: bool = True

    model_config = ConfigDict(extra="ignore")


class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str


@router.post("")
@router.post("/")
async def chat(
    request: ChatRequest = Body(default=ChatRequest()),
    current_user: User = Depends(get_current_user),
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
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
        meta={"mode": mode, "document_id": request.document_id}
    )
    db.add(user_message)
    db.commit()

    # Get conversation history
    messages = db.query(Message).filter(
        Message.conversation_id == conversation.id
    ).order_by(Message.created_at.desc()).limit(MAX_HISTORY_MESSAGES).all()
    messages = list(reversed(messages))

    # Prepare messages for AI
    history = [{"role": msg.role, "content": msg.content} for msg in messages]
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
    model = select_model(mode)

    provider = (request.provider or settings.AI_PROVIDER or "openai").lower()

    # Stream response
    if request.stream:
        async def generate():
            try:
                if mode == "image":
                    yield sse_event({"type": "delta", "content": "Generating image..."})
                    images = await ai_service.generate_image(request.message)
                    assistant_message = Message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content="Here are your images.",
                        meta={"mode": mode, "images": images}
                    )
                    db.add(assistant_message)
                    db.commit()
                    yield sse_event(response_envelope("Here are your images.", images=images) | {"type": "final"})
                    return

                full_response = ""
                async for chunk in ai_service.chat_stream(
                    ai_messages,
                    provider=provider,
                    model=model if provider == "openai" else None
                ):
                    full_response += chunk
                    yield sse_event({"type": "delta", "content": chunk})

                # Save assistant message after streaming
                assistant_message = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_response,
                    meta={"mode": mode, "document_id": request.document_id}
                )
                db.add(assistant_message)
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
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content="Here are your images.",
                meta={"mode": mode, "images": images}
            )
            db.add(assistant_message)
            db.commit()
            return response_envelope("Here are your images.", images=images)

        try:
            # Non-streaming response (use provider-aware stream and aggregate)
            response_text = ""
            async for chunk in ai_service.chat_stream(
                ai_messages,
                provider=provider,
                model=model if provider == "openai" else None
            ):
                response_text += chunk

            # Save assistant message
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=response_text,
                meta={"mode": mode, "document_id": request.document_id}
            )
            db.add(assistant_message)
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

    last_user_message = db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.role == "user"
    ).order_by(Message.created_at.desc()).first()

    if not last_user_message:
        raise HTTPException(status_code=400, detail="No user message to regenerate")

    last_assistant_message = db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.role == "assistant"
    ).order_by(Message.created_at.desc()).first()

    if last_assistant_message and last_assistant_message.created_at >= last_user_message.created_at:
        db.delete(last_assistant_message)
        db.commit()

    messages = db.query(Message).filter(
        Message.conversation_id == conversation.id
    ).order_by(Message.created_at.desc()).limit(MAX_HISTORY_MESSAGES).all()
    messages = list(reversed(messages))

    history = [{"role": msg.role, "content": msg.content} for msg in messages]
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

        search_results = await vector_service.search(last_user_message.content, k=3, doc_id=document.id)
        doc_context = "\n\n".join([result[0] for result in search_results]) or document.text_content

    ai_messages = build_messages(history, mode)
    if doc_context:
        ai_messages.insert(1, {"role": "system", "content": f"Document context:\n{doc_context[:8000]}"})
    model = select_model(mode)
    provider = (request.provider or settings.AI_PROVIDER or "openai").lower()

    if request.stream:
        async def generate():
            if mode == "image":
                yield sse_event({"type": "delta", "content": "Generating image..."})
                images = await ai_service.generate_image(last_user_message.content)
                assistant_message = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content="Here are your images.",
                    meta={"mode": mode, "images": images}
                )
                db.add(assistant_message)
                db.commit()
                yield sse_event(response_envelope("Here are your images.", images=images) | {"type": "final"})
                return

            full_response = ""
            async for chunk in ai_service.chat_stream(
                ai_messages,
                provider=provider,
                model=model if provider == "openai" else None
            ):
                full_response += chunk
                yield sse_event({"type": "delta", "content": chunk})

            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=full_response,
                meta={"mode": mode, "document_id": request.document_id}
            )
            db.add(assistant_message)
            db.commit()

            yield sse_event(response_envelope(full_response) | {"type": "final"})

        return StreamingResponse(generate(), media_type="text/event-stream")

    if mode == "image":
        images = await ai_service.generate_image(last_user_message.content)
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="Here are your images.",
            meta={"mode": mode, "images": images}
        )
        db.add(assistant_message)
        db.commit()
        return response_envelope("Here are your images.", images=images)

    response_text = ""
    async for chunk in ai_service.chat_stream(
        ai_messages,
        provider=provider,
        model=model if provider == "openai" else None
    ):
        response_text += chunk

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
        meta={"mode": mode, "document_id": request.document_id}
    )
    db.add(assistant_message)
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
            "updated_at": conv.updated_at.isoformat()
        }
        for conv in conversations
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: int,
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

    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at).all()

    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
                "meta": msg.meta or {}
            }
            for msg in messages
        ]
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
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
