from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Any, List
import re
try:
    from sqlalchemy.orm import Session
except ImportError:
    Session = Any
import os
from config.database import get_db
from models.user import User
from models.document import Document
from services.ai_service import ai_service
from services.document_service import document_service
from services.search_service import search_web_images
from services.vector_service import vector_service
from utils.dependencies import get_current_user
from config.settings import settings

router = APIRouter(prefix="/api/document", tags=["Document Analyzer"])
_ALL_QUESTIONS_PATTERN = re.compile(
    r"\b(?:answer|solve|write|give|provide|return|generate)\s+(?:all|every)\s+(?:the\s+)?(?:questions?|answers?)\b"
    r"|\ball questions?\b"
    r"|\ball question answers?\b"
    r"|\bquestion paper\b"
    r"|\bsub-?questions?\b",
    re.IGNORECASE,
)
_MULTI_MARK_REQUEST_PATTERN = re.compile(
    r"\b\d+\s+(?:x\s*)?(?:2|3|4|5|8|10|12|15|16)\s*(?:-)?\s*(?:mark|marks)\b",
    re.IGNORECASE,
)
_QUESTION_LINE_PATTERN = re.compile(
    r"(?m)^\s*(?:q(?:uestion)?\s*)?(?:\d+|[ivxlcdm]+|[a-z])[\).:-]\s+",
    re.IGNORECASE,
)
_DIAGRAM_REQUEST_PATTERN = re.compile(
    r"\b(diagram|flow\s?chart|flowchart|block diagram|architecture diagram|network diagram|sequence diagram|topology|stack diagram|layered diagram|with diagram|draw .*diagram|neat diagram)\b",
    re.IGNORECASE,
)
_COMPARISON_REQUEST_PATTERN = re.compile(
    r"\b(difference between|differences between|difference|compare|comparison|distinguish between|versus|vs\.?)\b",
    re.IGNORECASE,
)
_PROCESS_REQUEST_PATTERN = re.compile(
    r"\b(process|workflow|working|works|flow|steps?|life cycle|lifecycle|handshake)\b",
    re.IGNORECASE,
)
_ARCHITECTURE_REQUEST_PATTERN = re.compile(
    r"\b(architecture|network|protocol|stack|layer|layers|client|server|system|topology)\b",
    re.IGNORECASE,
)
_QUESTION_CLEANUP_PATTERN = re.compile(
    r"\b(draw|show|create|give|provide|write|explain|neat|with|for|assignment|answer|diagram|flowchart|flow chart|block diagram|architecture diagram|network diagram|sequence diagram)\b",
    re.IGNORECASE,
)
_MARKS_CLEANUP_PATTERN = re.compile(
    r"\b\d+\s*(?:-)?\s*(?:mark|marks)\b",
    re.IGNORECASE,
)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "answer",
    "assignment",
    "compare",
    "comparison",
    "difference",
    "diagram",
    "draw",
    "explain",
    "for",
    "give",
    "in",
    "is",
    "it",
    "marks",
    "neat",
    "of",
    "or",
    "show",
    "the",
    "to",
    "with",
    "write",
}
_DEFAULT_DOCUMENT_CONTEXT_CHARS = 8000
_EXPANDED_DOCUMENT_CONTEXT_CHARS = 24000
SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".docx",
    ".md",
    ".csv",
    ".json",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".html",
    ".htm",
    ".css",
    ".xml",
    ".yml",
    ".yaml",
}


def _needs_full_document_context(question: str) -> bool:
    raw_text = str(question or "")
    cleaned_text = " ".join(raw_text.split())
    if not cleaned_text:
        return False

    if _ALL_QUESTIONS_PATTERN.search(cleaned_text):
        return True

    if len(_MULTI_MARK_REQUEST_PATTERN.findall(cleaned_text)) >= 2:
        return True

    if len(_QUESTION_LINE_PATTERN.findall(raw_text)) >= 2:
        return True

    return False


def _looks_like_diagram_request(question: str) -> bool:
    return bool(_DIAGRAM_REQUEST_PATTERN.search(str(question or "")))


def _normalize_image_prompt_text(text: str, limit: int = 2600) -> str:
    return " ".join((text or "").split())[:limit]


def _image_result_url(result: dict) -> str:
    return str(result.get("image_url") or result.get("thumbnail_url") or "").strip()


def _document_diagram_search_suffix(question: str, answer: str) -> str:
    combined = f"{question} {answer}".lower()
    if _COMPARISON_REQUEST_PATTERN.search(combined):
        return "comparison diagram"
    if _PROCESS_REQUEST_PATTERN.search(combined):
        return "flowchart"
    if _ARCHITECTURE_REQUEST_PATTERN.search(combined):
        return "architecture diagram"
    return "textbook diagram"


def _document_diagram_topic(question: str, answer: str) -> str:
    cleaned_question = _MARKS_CLEANUP_PATTERN.sub(" ", str(question or ""))
    cleaned_question = _QUESTION_CLEANUP_PATTERN.sub(" ", cleaned_question)
    cleaned_question = re.sub(r"[^\w\s/+.-]", " ", cleaned_question)
    cleaned_question = _normalize_image_prompt_text(cleaned_question, 180).strip(" -:,.")
    if cleaned_question:
        return cleaned_question

    first_sentence = re.split(r"(?<=[.!?])\s+", str(answer or "").strip(), maxsplit=1)[0]
    return _normalize_image_prompt_text(first_sentence, 180).strip(" -:,.")


def _document_diagram_terms(question: str, answer: str, limit: int = 8) -> List[str]:
    source = f"{question} {answer}"
    raw_terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9/+.-]{1,}", source)
    terms: List[str] = []
    seen: set[str] = set()

    for raw_term in raw_terms:
        term = raw_term.strip().lower()
        if (
            not term
            or term in _STOPWORDS
            or len(term) < 3
            or term.isdigit()
        ):
            continue
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
        if len(terms) >= limit:
            break

    return terms


def _build_document_diagram_queries(question: str, answer: str) -> List[str]:
    topic = _document_diagram_topic(question, answer)
    suffix = _document_diagram_search_suffix(question, answer)
    keyword_terms = _document_diagram_terms(question, answer, limit=5)
    queries = [
        _normalize_image_prompt_text(f"{topic} {suffix}", 260),
        _normalize_image_prompt_text(f"{topic} textbook {suffix}", 260),
        _normalize_image_prompt_text(f"{' '.join(keyword_terms)} {suffix}", 260) if keyword_terms else "",
        _normalize_image_prompt_text(f"{topic} labeled {suffix}", 260),
    ]

    deduped: List[str] = []
    seen: set[str] = set()
    for query in queries:
        cleaned = " ".join((query or "").split()).strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(cleaned)
    return deduped[:4]


def _score_document_diagram_result(result: dict, required_terms: List[str], query_index: int) -> float:
    haystack = " ".join(
        str(result.get(field, "") or "").lower()
        for field in ("title", "url", "source", "image_url", "thumbnail_url")
    )
    if not haystack:
        return 0.0

    score = 0.0
    for term in required_terms:
        if term in haystack:
            score += 2.5

    if "diagram" in haystack or "chart" in haystack or "flow" in haystack:
        score += 1.5
    if "architecture" in haystack or "network" in haystack or "protocol" in haystack:
        score += 1.0

    width = result.get("width")
    height = result.get("height")
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        score += min((width * height) / 1_000_000, 5.0)

    if _image_result_url(result):
        score += 0.75

    score += max(0, 2 - query_index) * 0.35
    return score


async def _search_document_answer_diagrams(question: str, answer: str, limit: int = 2) -> List[str]:
    queries = _build_document_diagram_queries(question, answer)
    if not queries:
        return []

    required_terms = _document_diagram_terms(question, answer, limit=8)
    ranked_candidates: dict[str, float] = {}

    for query_index, query in enumerate(queries):
        results = await search_web_images(query, max_results=6)
        for result in results:
            image_url = _image_result_url(result)
            if not image_url:
                continue
            score = _score_document_diagram_result(result, required_terms, query_index)
            if score <= 0:
                continue
            ranked_candidates[image_url] = max(score, ranked_candidates.get(image_url, float("-inf")))

    ranked = sorted(ranked_candidates.items(), key=lambda item: item[1], reverse=True)
    return [image_url for image_url, _ in ranked[:limit]]


def _build_document_answer_image_prompt(question: str, answer: str) -> str:
    cleaned_question = _normalize_image_prompt_text(question, 600)
    cleaned_answer = _normalize_image_prompt_text(answer, 2200)
    if not cleaned_answer:
        return ""

    prompt_lines = [
        "Create one clean academic textbook diagram that matches the answer below.",
        "Requirements:",
        "- Build one complete integrated figure, not multiple disconnected mini-diagrams.",
        "- Keep labels large, readable, and clearly attached to the right part of the figure.",
        "- Do not use rough ASCII-style boxes, terminal-like layouts, or decorative poster art.",
        "- Use a white background and a flat 2D educational textbook style.",
        "- Use simple rectangles, arrows, and neatly aligned labels.",
        "- If the topic is a process or handshake, show one clear ordered sequence with arrows and step numbers when helpful.",
        "- If the topic is a layered architecture or protocol stack, show one stacked-layer diagram.",
        "- If the topic is a transformation flow, show one clean vertical or horizontal flowchart.",
        "- Use common textbook style only as inspiration; do not copy a specific example exactly.",
        "- Keep the diagram faithful to the answer and do not invent unsupported parts.",
        "",
        f"Question: {cleaned_question}",
        f"Answer: {cleaned_answer}",
    ]
    return "\n".join(prompt_lines)[:3600]


def _dedupe_images(images: List[str], limit: int = 2) -> List[str]:
    deduped: List[str] = []
    seen: set[str] = set()
    for image in images:
        candidate = str(image or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
        if len(deduped) >= limit:
            break
    return deduped


async def _generate_document_answer_images_best_effort(question: str, answer: str, limit: int = 2) -> List[str]:
    web_images = await _search_document_answer_diagrams(question, answer, limit=limit)
    if web_images:
        return web_images

    prompt = _build_document_answer_image_prompt(question, answer)
    if not prompt:
        return []

    return _dedupe_images(await ai_service.generate_image(prompt), limit=limit)


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


class RewriteQuestionRequest(BaseModel):
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
    if file_ext not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Supported files: PDF, DOCX, TXT, Markdown, CSV, JSON, HTML, XML, YAML, and common code files"
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
        await vector_service.upsert_document(text_content, document.id)

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
    await vector_service.ensure_document(document.text_content or "", document.id)
    if _needs_full_document_context(request.question):
        context = str(document.text_content or "")[:_EXPANDED_DOCUMENT_CONTEXT_CHARS]
        context_limit = _EXPANDED_DOCUMENT_CONTEXT_CHARS
    else:
        search_results = await vector_service.search(request.question, k=3, doc_id=document.id)
        context = "\n\n".join([result[0] for result in search_results])
        context_limit = _DEFAULT_DOCUMENT_CONTEXT_CHARS

    # Get answer from AI
    answer = await ai_service.answer_question_from_document(
        request.question,
        context if context else str(document.text_content or ""),
        max_context_chars=context_limit,
    )
    answer_images: List[str] = []
    if _looks_like_diagram_request(request.question):
        answer_images = await _generate_document_answer_images_best_effort(
            request.question,
            answer,
            limit=2,
        )

    return {
        "question": request.question,
        "answer": answer,
        "answer_images": answer_images,
    }


@router.post("/rewrite-question")
async def rewrite_question(
    request: RewriteQuestionRequest,
    current_user: User = Depends(get_current_user),
):
    """Rewrite a question into a cleaner academic prompt"""
    question = " ".join((request.question or "").split()).strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    rewritten_question = await ai_service.rewrite_document_question(question)
    if not rewritten_question:
        raise HTTPException(status_code=500, detail="Could not rewrite the question right now")

    return {
        "question": question,
        "rewritten_question": rewritten_question,
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
    vector_service.remove_document(document.id)

    # Delete from database
    db.delete(document)
    db.commit()

    return {"message": "Document deleted successfully"}
