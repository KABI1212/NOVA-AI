from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import os
from config.database import get_db
from models.user import User
from models.document import Document
from services.ai_service import ai_service
from services.document_service import document_service
from services.vector_service import vector_service
from utils.dependencies import get_current_user
from config.settings import settings

router = APIRouter(prefix="/api/document", tags=["Document Analyzer"])


class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    summary: str = None
    is_processed: bool
    created_at: str


class AskQuestionRequest(BaseModel):
    document_id: int
    question: str


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and process a document"""

    # Validate file type
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ['.pdf', '.txt', '.docx']:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, TXT, and DOCX files are supported"
        )

    # Validate file size
    file_content = await file.read()
    file_size_mb = len(file_content) / (1024 * 1024)

    if file_size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds {settings.MAX_FILE_SIZE_MB}MB limit"
        )

    # Save file
    file_path = await document_service.save_file(file_content, file.filename)

    # Create document record
    document = Document(
        user_id=current_user.id,
        filename=file.filename,
        file_path=file_path,
        file_type=file_ext[1:],  # Remove dot
        file_size=len(file_content),
        is_processed=False
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    # Process document in background (extract text)
    try:
        text_content = await document_service.process_document(
            file_path,
            document.file_type
        )

        # Update document with extracted text
        document.text_content = text_content
        document.is_processed = True

        # Generate summary
        summary = await ai_service.summarize_document(text_content)
        document.summary = summary

        # Add to vector database for semantic search
        await vector_service.add_document(text_content, document.id)

        db.commit()
        db.refresh(document)

    except Exception as e:
        document.is_processed = False
        db.commit()
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")

    return {
        "id": document.id,
        "filename": document.filename,
        "file_type": document.file_type,
        "file_size": document.file_size,
        "summary": document.summary,
        "is_processed": document.is_processed,
        "created_at": document.created_at.isoformat()
    }


@router.get("/", response_model=List[DocumentResponse])
async def get_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all documents for current user"""
    documents = db.query(Document).filter(
        Document.user_id == current_user.id
    ).order_by(Document.created_at.desc()).all()

    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "summary": doc.summary,
            "is_processed": doc.is_processed,
            "created_at": doc.created_at.isoformat()
        }
        for doc in documents
    ]


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific document"""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "id": document.id,
        "filename": document.filename,
        "file_type": document.file_type,
        "file_size": document.file_size,
        "summary": document.summary,
        "text_content": document.text_content,
        "is_processed": document.is_processed,
        "created_at": document.created_at.isoformat()
    }


@router.post("/ask")
async def ask_question(
    request: AskQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Ask a question about a document"""
    document = db.query(Document).filter(
        Document.id == request.document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not document.is_processed:
        raise HTTPException(status_code=400, detail="Document is still being processed")

    # Use vector search to find relevant context
    search_results = await vector_service.search(request.question, k=3)

    # Combine relevant chunks
    context = "\n\n".join([result[0] for result in search_results])

    # Get answer from AI
    answer = await ai_service.answer_question_from_document(
        request.question,
        context if context else document.text_content[:8000]
    )

    return {
        "question": request.question,
        "answer": answer
    }


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a document"""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete file from disk
    document_service.delete_file(document.file_path)

    # Delete from database
    db.delete(document)
    db.commit()

    return {"message": "Document deleted successfully"}
