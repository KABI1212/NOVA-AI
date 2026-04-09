import asyncio
import base64
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
try:
    from sqlalchemy.orm import Session
except ImportError:
    Session = Any

from ai_engine import build_messages, response_envelope
from config.database import get_db, get_db_optional
from config.settings import settings
from models.conversation import Conversation
from models.document import Document
from models.user import User
from prompts import get_presentation_style_prompt
from services.ai_provider import PROVIDERS, generate_response, stream_response
from services.ai_service import LOCAL_FALLBACK_MESSAGE, ai_service, infer_use_case, normalize_image_asset
from services.conversation_summary import (
    build_summary_history_message,
    refresh_conversation_summary,
)
from services.conversation_store import (
    append_conversation_message,
    ensure_conversation_messages,
    history_from_conversation,
    save_conversation,
    serialize_conversation_messages,
)
from services.conversation_memory import add_message, get_history
from services.instant_responses import instant_reply
from services.search_service import fetch_page_content, format_results_for_ai, is_temporal_query, search_web, search_web_images
from services.vector_service import vector_service
from utils.dependencies import get_current_user, get_current_user_optional
from utils.rate_limit import enforce_chat_rate_limit, enforce_image_rate_limit

router = APIRouter(prefix="/api/chat", tags=["Chat"])
MAX_HISTORY_MESSAGES = 12
logger = logging.getLogger(__name__)
FALLBACK_MESSAGE = LOCAL_FALLBACK_MESSAGE
SETUP_RETRY_MESSAGE = "That option isn't ready just yet. Want me to try again?"
REGENERATE_VARIATION_INSTRUCTION = (
    "This is a regenerate request. Give a fresh version of the answer. "
    "Do not repeat the previous wording. Improve clarity, add a useful example, or simplify the explanation."
)
_VOLATILE_FACT_PATTERN = re.compile(
    r"\b(?:weather|forecast|temperature|rain|snow|price|prices|pricing|stock price|share price|market cap|exchange rate|currency rate|flight status)\b",
    re.IGNORECASE,
)
_STALE_KNOWLEDGE_REPLY_PATTERNS = (
    re.compile(r"\b(?:knowledge|training)\s+(?:cutoff|cut-off)\b", re.IGNORECASE),
    re.compile(r"\b(?:as of|up to|through|until)\s+(?:late\s+)?2023\b", re.IGNORECASE),
    re.compile(r"\b(?:do not|don't|cannot|can't)\s+(?:have|know|access).{0,80}\b(?:after|beyond)\s+2023\b", re.IGNORECASE),
    re.compile(r"\b(?:do not|don't|cannot|can't)\s+(?:browse|access)\s+(?:the\s+)?web\b", re.IGNORECASE),
    re.compile(r"\bno real[- ]time (?:data|access|information)\b", re.IGNORECASE),
)
_FRESHNESS_RETRY_INSTRUCTION = (
    "Freshness retry is required. The previous draft relied on an outdated cutoff or missing live data.\n"
    "Use fresh web-backed information if available, and do not answer with a 2023 cutoff disclaimer when newer sources are provided."
)
_VERIFICATION_SOURCE_CHARS = 12000
_VERIFICATION_TEMPERATURE = 0.0
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
    "Analyze",
    "Suggest",
    "Debug",
    "Compare",
    "Summarize",
    "Guide me through",
    "Summarize",
    "Briefly",
    "In detail",
    "With examples",
    "Step-by-step",
    "With code",
    "Help me",
    "What's the best way to",
    "How do I",
    "Why does",
    "What if",
    "I need",
    "i need",
    
)
_SPORTS_QUERY_REWRITES = (
    (re.compile(r"\bcaptions\b", re.IGNORECASE), "captains"),
    (re.compile(r"\bcaption\b", re.IGNORECASE), "captain"),
)
_FILE_TAG_PATTERN = re.compile(r"(?:\s*\+\s*)?\[File:\s*([^\]]+)\]\s*", re.IGNORECASE)
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
_MARKS_PATTERN = re.compile(
    r"\b(?P<marks>2|3|4|5|8|10|12|15|16)\s*(?:-)?\s*(?:mark|marks)\b",
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
_DEFAULT_DOCUMENT_CONTEXT_CHARS = 8000
_EXPANDED_DOCUMENT_CONTEXT_CHARS = 120000
_DEFAULT_DOCUMENT_SEARCH_K = 3
_EXPANDED_RESPONSE_MAX_TOKENS = 16384
_ASSIGNMENT_REQUEST_PATTERN = re.compile(r"\b(?:assignment|assignments)\b", re.IGNORECASE)
_DOCUMENT_GROUNDING_INSTRUCTION = (
    "Document verification mode:\n"
    "- Treat the uploaded document context as the only source of truth.\n"
    "- Answer only from the provided document context.\n"
    "- Do not mix in outside knowledge, web facts, or assumptions.\n"
    "- If the document does not contain the answer, say \"I don't know based on the provided document.\"\n"
    "- Keep the answer exact, grounded, and easy to verify against the file."
)


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = ""
    mode: str = "chat"
    provider: Optional[str] = None
    model: Optional[str] = None
    document_id: Optional[int] = None
    image_b64: Optional[str] = None
    image_mime_type: Optional[str] = None
    generate_prompt_image: Optional[bool] = None
    generate_answer_image: Optional[bool] = None
    stream: bool = True

    model_config = ConfigDict(extra="ignore")


class RegenerateRequest(BaseModel):
    conversation_id: str
    mode: str = "chat"
    provider: Optional[str] = None
    model: Optional[str] = None
    previous_answer: Optional[str] = None
    document_id: Optional[int] = None
    generate_answer_image: Optional[bool] = None
    stream: bool = True

    model_config = ConfigDict(extra="ignore")


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    preview: Optional[str] = None


class ConversationUpdateRequest(BaseModel):
    title: str

    model_config = ConfigDict(extra="ignore")


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _payload(
    message: str,
    conversation: Optional[Conversation] = None,
    images: Optional[List[str]] = None,
    prompt_images: Optional[List[str]] = None,
    answer_images: Optional[List[str]] = None,
    sources: Optional[List[dict]] = None,
) -> dict:
    resolved_answer_images = answer_images if answer_images is not None else images
    payload = {
        "message": message,
        "answer": message,
        "images": resolved_answer_images or [],
        "answer_images": resolved_answer_images or [],
        "prompt_images": prompt_images or [],
        "sources": sources or [],
    }
    if conversation is not None:
        payload["conversation_id"] = conversation.id
        payload["title"] = conversation.title
    return payload


def _final_payload(
    message: str,
    conversation: Optional[Conversation] = None,
    images: Optional[List[str]] = None,
    prompt_images: Optional[List[str]] = None,
    answer_images: Optional[List[str]] = None,
    sources: Optional[List[dict]] = None,
    interrupted: bool = False,
) -> dict:
    payload = _payload(
        message,
        conversation,
        images,
        prompt_images=prompt_images,
        answer_images=answer_images,
        sources=sources,
    ) | {"type": "final"}
    if interrupted:
        payload["error"] = "retry"
    return payload


def _normalize_image_prompt_text(text: str, limit: int = 2600) -> str:
    return " ".join((text or "").split())[:limit]


_IMAGE_INTENT_PATTERNS = (
    re.compile(
        r"\b(?:generate|create|make|draw|design|illustrate|paint|render)\b.{0,80}\b(?:image|picture|photo|art|artwork|illustration|poster|logo|portrait|wallpaper|banner|thumbnail|cover art|sticker|icon|mascot|avatar)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:need|want)\b.{0,24}\b(?:an?|some)\b.{0,12}\b(?:image|picture|photo|art|artwork|illustration|poster|logo|portrait|wallpaper|banner|thumbnail|cover art|sticker|icon|mascot|avatar)\b(?:.{0,24}\b(?:of|for|showing|with)\b|[.!?]?$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:image|picture|photo|art|artwork|illustration|poster|logo|portrait|wallpaper|banner|thumbnail|sticker|icon|mascot|avatar)\b.{0,40}\b(?:of|for|showing|with)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:show me|give me|make me)\b.{0,60}\b(?:image|picture|photo|art|artwork|illustration|poster|logo|portrait|wallpaper|banner|thumbnail|sticker|icon|mascot|avatar)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:can you|could you|please)\b.{0,40}\b(?:generate|create|make|draw|design|illustrate|paint|render|show|give|send)\b.{0,90}\b(?:image|picture|photo|art|artwork|illustration|poster|logo|portrait|wallpaper|banner|thumbnail|cover art|sticker|icon|mascot|avatar)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:paint|illustrate|sketch)\b.{0,220}$",
        re.IGNORECASE,
    ),
)
_IMAGE_PROMPT_DETAIL_PATTERN = re.compile(
    r"\b(?:cinematic|photorealistic|hyperrealistic|realistic(?: style)?|highly detailed|ultra detailed|4k(?: quality)?|8k(?: quality)?|shallow depth of field|depth of field|soft natural lighting|natural lighting|studio lighting|golden hour|bokeh|concept art|watercolor|oil painting|digital art|render|matte painting|volumetric lighting|dramatic lighting)\b",
    re.IGNORECASE,
)
_NON_IMAGE_HELP_PATTERN = re.compile(
    r"\b(?:explain|compare|difference|what|why|how|when|where|who|rewrite|improve|analyze|analysis|summarize)\b",
    re.IGNORECASE,
)


def _image_preferences(
    generate_prompt_image: bool = False,
    generate_answer_image: bool = False,
) -> Optional[dict]:
    meta = {}
    if generate_prompt_image:
        meta["generate_prompt_image"] = True
    if generate_answer_image:
        meta["generate_answer_image"] = True
    return meta or None


def _merge_message_meta(
    meta: Optional[dict],
    *,
    images: Optional[List[str]] = None,
    **extra: object,
) -> Optional[dict]:
    merged = dict(meta) if isinstance(meta, dict) else {}
    for key, value in extra.items():
        if value is True:
            merged[key] = True
        elif value not in (None, False, "", [], {}):
            merged[key] = value
    if images:
        merged["images"] = images
    return merged or None


def _apply_images_to_message(
    message,
    images: Optional[List[str]] = None,
    **extra: object,
) -> None:
    if message is None:
        return
    message.meta = _merge_message_meta(getattr(message, "meta", None), images=images, **extra)
    db_session = getattr(message, "_db_session", None)
    if db_session is not None:
        db_session.add(message)


def _message_images(message) -> List[str]:
    meta = getattr(message, "meta", None)
    if not isinstance(meta, dict):
        return []
    images = meta.get("images")
    if not isinstance(images, list):
        return []
    return [str(image) for image in images if image]


def _chat_image_generation_cost(
    mode: str,
    *,
    generate_prompt_image: bool = False,
    generate_answer_image: bool = False,
) -> int:
    if mode == "image":
        return 1
    return int(bool(generate_prompt_image)) + int(bool(generate_answer_image))


def _build_prompt_image_prompt(user_message: str) -> str:
    cleaned = _normalize_image_prompt_text(user_message, 2400)
    if not cleaned:
        return ""
    return (
        "Create a single polished illustration for this user prompt. "
        "Do not add text, captions, labels, or watermarks.\n"
        f"User prompt: {cleaned}"
    )


def _extract_visual_keywords(text: str, limit: int = 8) -> List[str]:
    stopwords = {
        "about",
        "after",
        "answer",
        "assistant",
        "because",
        "between",
        "briefly",
        "could",
        "create",
        "diagram",
        "difference",
        "explain",
        "explains",
        "explanation",
        "from",
        "give",
        "given",
        "help",
        "helps",
        "illustration",
        "include",
        "including",
        "learn",
        "make",
        "more",
        "question",
        "relevant",
        "show",
        "simple",
        "single",
        "tell",
        "than",
        "that",
        "their",
        "them",
        "these",
        "this",
        "topic",
        "user",
        "using",
        "visual",
        "what",
        "when",
        "where",
        "which",
        "with",
        "would",
    }
    keywords: List[str] = []
    seen: set[str] = set()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+/.-]*", text or ""):
        candidate = token.strip(".,:;!?()[]{}")
        lowered = candidate.lower()
        if len(lowered) < 3 or lowered in stopwords or lowered in seen:
            continue
        seen.add(lowered)
        keywords.append(candidate)
        if len(keywords) >= limit:
            break
    return keywords


def _split_visual_topics(text: str) -> List[str]:
    cleaned = _normalize_image_prompt_text(text, 240)
    if not cleaned:
        return []
    parts = re.split(r"\s*(?:,|/|\band\b|\bvs\.?\b|\bversus\b)\s*", cleaned, flags=re.IGNORECASE)
    topics: List[str] = []
    for part in parts:
        candidate = re.sub(
            r"\b(explain|what is|what are|how does|how do|how is|how are|tell me about|difference between|compare|show me|diagram of)\b",
            "",
            part,
            flags=re.IGNORECASE,
        )
        candidate = re.sub(r"\b(work|works|working|function|functions|process|overview|basics)\b", "", candidate, flags=re.IGNORECASE)
        candidate = " ".join(candidate.split()).strip(" ?!.,")
        if candidate:
            topics.append(candidate)
    return topics[:4]


def _answer_visual_strategy(user_message: str, answer: str) -> tuple[str, str, str]:
    combined = f"{user_message} {answer}".lower()
    topics = _split_visual_topics(user_message)
    multi_topic = len(topics) >= 2

    if re.search(r"\b(compare|comparison|difference|vs|versus|distinguish)\b", combined):
        return (
            "comparison diagram",
            "Use aligned side-by-side sections so the same properties can be compared directly.",
            "Keep the labels factual, symmetrical, and easy to scan.",
        )
    if re.search(r"\b(network|internet|client|server|router|request|response|api|database)\b", combined):
        return (
            "architecture diagram",
            "Use labeled blocks and arrows to show components and data flow.",
            "Prefer a technical schematic instead of decorative illustration.",
        )
    if re.search(r"\b(how|works|working|process|workflow|flow|pipeline|step|steps|procedure|timeline|history|historical|evolution|progression|chronology|cycle|life cycle|lifecycle|phase|phases|loop)\b", combined):
        return (
            "flow diagram",
            "Show the sequence with arrows so the mechanism is easy to follow.",
            "Use only the key stages from the answer and avoid adding extra steps.",
        )
    if re.search(r"\b(layer|layers|architecture|structure|components|parts|types|stack|memory|ram|rom|cache|storage|cpu|gpu|kernel|module)\b", combined):
        return (
            "architecture diagram",
            "Use boxes, layers, and short labels to show the real parts and how they relate.",
            "For technical topics, prefer a clean textbook schematic over character-style illustration.",
        )
    if multi_topic:
        return (
            "comparison diagram",
            "Give each concept its own labeled section with one or two key points.",
            "Make the similarities and differences visually obvious.",
        )
    return (
        "block diagram",
        "Place the main idea clearly and connect it to the most important supporting points.",
        "Keep it educational and specific to the actual answer, not generic poster art.",
    )


def _diagram_topic_text(user_message: str, answer: str) -> str:
    topics = _split_visual_topics(user_message)
    combined = f"{user_message} {answer}".lower()
    if len(topics) >= 2 and re.search(r"\b(compare|comparison|difference|vs|versus|distinguish)\b", combined):
        return " vs ".join(topics[:3])

    cleaned = _normalize_image_prompt_text(user_message, 200)
    cleaned = re.sub(
        r"\b(explain|create|generate|show me|tell me about|diagram of|what is|what are|how does|how do|how is|how are|compare|difference between)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = " ".join(cleaned.split()).strip(" ?!.,:")
    if cleaned:
        return cleaned

    fallback = " ".join(_extract_visual_keywords(answer, limit=4)).strip()
    return fallback or "the topic"


def _extract_diagram_labels(user_message: str, answer: str, limit: int = 6) -> List[str]:
    labels: List[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        candidate = _normalize_image_prompt_text(str(value), 70).strip(" -|,.;:")
        lowered = candidate.lower()
        if not candidate or len(candidate) < 2 or lowered in seen:
            return
        seen.add(lowered)
        labels.append(candidate)

    for line in (answer or "").splitlines():
        stripped = line.strip()
        if stripped.count("|") >= 2:
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if cells and not all(re.fullmatch(r"[-: ]+", cell or "") for cell in cells):
                for cell in cells[:3]:
                    add(cell)
        elif stripped.startswith(("-", "*")) or re.match(r"^\d+[.)]\s", stripped):
            add(re.sub(r"^[-*0-9.\s]+", "", stripped))

    if not labels:
        for chunk in re.split(r"\s*(?:→|->|=>)\s*", answer or ""):
            add(chunk)

    for topic in _split_visual_topics(user_message):
        add(topic)

    for keyword in _extract_visual_keywords(f"{user_message} {answer}", limit=limit * 2):
        add(keyword)

    return labels[:limit]


def _extract_protocol_labels(user_message: str, answer: str, limit: int = 6) -> List[str]:
    protocol_map = {
        "http/https": "HTTP/HTTPS",
        "http": "HTTP",
        "https": "HTTPS",
        "smtp": "SMTP",
        "imap": "IMAP",
        "pop3": "POP3",
        "tcp/ip": "TCP/IP",
        "tcp": "TCP",
        "udp": "UDP",
        "tls/ssl": "TLS/SSL",
        "tls": "TLS",
        "ssl": "SSL",
        "dns": "DNS",
        "ftp": "FTP",
        "ssh": "SSH",
        "websocket": "WebSocket",
        "rest api": "REST API",
        "grpc": "gRPC",
    }
    text = f"{user_message} {answer}".lower()
    found: List[str] = []
    seen: set[str] = set()
    for raw, label in protocol_map.items():
        if raw in text and label.lower() not in seen:
            seen.add(label.lower())
            found.append(label)
            if len(found) >= limit:
                break
    return found


def _extract_component_labels(user_message: str, answer: str, limit: int = 8) -> List[str]:
    component_map = {
        "browser": "Browser",
        "client": "Client",
        "frontend ui": "Frontend UI",
        "frontend": "Frontend UI",
        "backend server": "Backend Server",
        "backend": "Backend Server",
        "application server": "Application Server",
        "server": "Server",
        "email client": "Email Client",
        "email server": "Email Server",
        "database": "Database",
        "api gateway": "API Gateway",
        "gateway": "Gateway",
        "api": "API",
        "cache": "Cache",
        "router": "Router",
        "switch": "Switch",
        "firewall": "Firewall",
        "internet": "Internet",
        "ai model": "AI Model",
        "model api": "AI Model API",
        "load balancer": "Load Balancer",
    }
    text = f"{user_message} {answer}".lower()
    found: List[str] = []
    seen: set[str] = set()
    for raw, label in component_map.items():
        if raw in text and label.lower() not in seen:
            seen.add(label.lower())
            found.append(label)
            if len(found) >= limit:
                break
    return found


def _specific_diagram_requirements(user_message: str, answer: str, diagram_type: str) -> List[str]:
    topics = _split_visual_topics(user_message)
    labels = _extract_diagram_labels(user_message, answer)
    protocols = _extract_protocol_labels(user_message, answer)
    components = _extract_component_labels(user_message, answer)
    normalized = (diagram_type or "").lower()

    if "comparison" in normalized:
        requirements = [
            "Use two aligned comparison sections with consistent labels and matched rows.",
            f'Include comparison points such as: {", ".join(labels[:6]) or "the main supported properties"}.',
        ]
        if len(topics) >= 2:
            requirements.insert(
                0,
                f'Two side-by-side sections labeled "{topics[0]}" and "{topics[1]}".',
            )
        if components:
            requirements.append(f'Use real components when applicable: {", ".join(components[:6])}.')
        if protocols:
            requirements.append(f'Use real protocols when applicable: {", ".join(protocols[:5])}.')
        return requirements

    if "flow" in normalized:
        requirements = [
            "Use a clear left-to-right or top-to-bottom sequence with arrows.",
            f'Steps to include when supported: {" -> ".join(labels[:5]) or "the main supported steps"}.',
            "Show the logical sequence and real data or control flow.",
        ]
        if components:
            requirements.append(f'Include real components where relevant: {", ".join(components[:6])}.')
        if protocols:
            requirements.append(f'Label real protocols where relevant: {", ".join(protocols[:5])}.')
        return requirements

    if "architecture" in normalized:
        requirements = [
            "Use clearly separated rectangular components with arrows showing data flow or relationships.",
            f'Components to include when supported: {", ".join(components[:6] or labels[:6]) or "the main supported components"}.',
            "Show the logical direction of communication or data movement.",
        ]
        if protocols:
            requirements.append(f'Label applicable protocols on the connecting arrows when supported: {", ".join(protocols[:5])}.')
        return requirements

    requirements = [
        "Use a block diagram layout with labeled rectangular blocks and connecting arrows where needed.",
        f'Include concepts or parts such as: {", ".join(labels[:6]) or "the main supported concepts"}.',
    ]
    if components:
        requirements.append(f'Include real components where relevant: {", ".join(components[:6])}.')
    if protocols:
        requirements.append(f'Add real protocols only if they genuinely apply: {", ".join(protocols[:5])}.')
    return requirements


def _diagram_style_requirements(user_message: str, answer: str, diagram_type: str) -> List[str]:
    combined = f"{user_message} {answer}".lower()
    normalized = (diagram_type or "").lower()
    style_requirements = [
        "Create one complete integrated figure, not multiple disconnected mini-diagrams.",
        "Use larger readable labels with enough spacing so the text stays clear.",
        "Keep the layout clean, balanced, and easy to follow at a glance.",
        "Use a polished academic textbook style, not rough ASCII or terminal-style boxes.",
        "Use any familiar textbook diagram style only as inspiration; do not copy an existing example exactly.",
    ]

    if "flow" in normalized or re.search(r"\b(handshake|process|workflow|steps?|procedure|ssl|tls|https)\b", combined):
        style_requirements.extend(
            [
                "Use one directional sequence with arrows and clear numbered stages when helpful.",
                "Place the labels close to the relevant arrows or stages so the flow is easy to follow.",
            ]
        )

    if "architecture" in normalized or re.search(r"\b(layer|layers|stack|ssh|osi|tcp/?ip)\b", combined):
        style_requirements.extend(
            [
                "If the topic is a stack or layered protocol, use one stacked-layer figure with clearly separated boxes.",
                "Keep the layers aligned and ordered top-to-bottom or bottom-to-top in a textbook style.",
            ]
        )

    if re.search(r"\b(header|encapsulation|packet|ipsec|ah|esp)\b", combined):
        style_requirements.append(
            "If the topic is packet or header structure, show the packet layout as one composed labeled figure instead of separate floating blocks."
        )

    if re.search(r"\b(ssl record|fragmentation|compression|mac|encryption)\b", combined):
        style_requirements.append(
            "If the topic is a stage-by-stage transformation, use a single vertical or horizontal flow like a clean textbook flowchart."
        )

    return style_requirements


def _build_answer_image_prompt(user_message: str, answer: str) -> str:
    cleaned_user = _normalize_image_prompt_text(user_message, 900)
    cleaned_answer = _normalize_image_prompt_text(answer, 2400)
    if not cleaned_answer:
        return ""
    diagram_type, layout_note, accuracy_note = _answer_visual_strategy(cleaned_user, cleaned_answer)
    topic = _diagram_topic_text(cleaned_user, cleaned_answer)
    specific_requirements = _specific_diagram_requirements(cleaned_user, cleaned_answer, diagram_type)
    style_requirements = _diagram_style_requirements(cleaned_user, cleaned_answer, diagram_type)
    prompt_lines = [
        f'Create a clean, minimal, textbook-style {diagram_type} explaining "{topic}".',
        "",
        "Diagram rules:",
        f"- Selected type: {diagram_type}",
        "- Include the whole concept in one coherent diagram, not separate detached fragments.",
        "- Keep every main label, step, or layer inside the same integrated figure.",
        "- Use real components and real protocols only when they genuinely apply to the topic.",
        "- Use proper data flow with arrows.",
        "- Use logical sequence from left to right or top to bottom.",
        "",
        "Style requirements:",
        "- White background.",
        "- Flat 2D vector design with no 3D effects, gradients, or shadows.",
        "- Use simple geometric shapes, thin lines, and sharp edges.",
        "- Use a limited academic color palette such as black, blue, and grey.",
        "- Clearly labeled components with readable sans-serif font.",
        "- Balanced spacing and alignment.",
        "- Arrows to show flow or relationships.",
        "- No decorative elements, no icons, no stock images, and no UI cards.",
        "- Professional academic look similar to engineering or CS textbooks.",
        *[f"- {line}" for line in style_requirements],
        "",
        "Specific content requirements:",
        f"- {layout_note}",
        f"- {accuracy_note}",
        *[f"- {line}" for line in specific_requirements],
        "",
        "Accuracy requirements:",
        "- Base the structure, labels, and relationships on the assistant answer below.",
        "- If web grounding is provided, use it only to verify or refine the factual structure.",
        "- Do not invent unsupported components, steps, or relationships.",
        "",
        "Output:",
        "- High resolution.",
        "- Centered layout.",
        "- Diagram only, with no extra text outside the figure.",
        "",
        f"User prompt: {cleaned_user}",
        f"Assistant answer: {cleaned_answer}",
    ]
    return "\n".join(prompt_lines)[:3800]


def _extract_answer_image_context_from_prompt(prompt: str) -> tuple[str, str]:
    source = str(prompt or "").strip()
    user_match = re.search(r"User prompt:\s*(.*?)(?:\nAssistant answer:|\Z)", source, re.S | re.I)
    answer_match = re.search(r"Assistant answer:\s*(.*?)(?:\nWeb grounding for accuracy:|\Z)", source, re.S | re.I)
    user_message = (user_match.group(1).strip() if user_match else "").strip()
    answer = (answer_match.group(1).strip() if answer_match else "").strip()
    return user_message, answer


def _answer_image_search_suffix(diagram_type: str) -> str:
    normalized = (diagram_type or "").lower()
    if "comparison" in normalized:
        return "comparison diagram"
    if "process" in normalized:
        return "process diagram"
    if "flow" in normalized:
        return "flow diagram"
    if "architecture" in normalized or "system" in normalized or "network" in normalized:
        return "architecture diagram"
    if "block" in normalized or "concept" in normalized or "labeled" in normalized:
        return "block diagram"
    return "textbook diagram"


def _build_answer_image_search_query(user_message: str, answer: str) -> str:
    cleaned_user = _normalize_image_prompt_text(user_message, 240)
    cleaned_answer = _normalize_image_prompt_text(answer, 320)
    if not cleaned_user and not cleaned_answer:
        return ""
    diagram_type, _, _ = _answer_visual_strategy(cleaned_user, cleaned_answer)
    topics = _split_visual_topics(cleaned_user)
    keywords = _extract_visual_keywords(f"{cleaned_user} {cleaned_answer}", limit=6)
    search_terms = " ".join(topics[:4] or keywords[:4] or [cleaned_user])
    suffix = _answer_image_search_suffix(diagram_type)
    return _normalize_image_prompt_text(f"{search_terms} {suffix}", 280)


def _contains_search_term(haystack: str, term: str) -> bool:
    normalized_haystack = (haystack or "").lower()
    normalized_term = (term or "").strip().lower()
    if not normalized_haystack or not normalized_term:
        return False
    compact = re.sub(r"[^a-z0-9]", "", normalized_term)
    if compact and len(compact) <= 4:
        return re.search(rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])", normalized_haystack) is not None
    return normalized_term in normalized_haystack


def _build_answer_image_search_queries(user_message: str, answer: str) -> List[str]:
    cleaned_user = _normalize_image_prompt_text(user_message, 220)
    cleaned_answer = _normalize_image_prompt_text(answer, 320)
    if not cleaned_user and not cleaned_answer:
        return []

    diagram_type, _, _ = _answer_visual_strategy(cleaned_user, cleaned_answer)
    suffix = _answer_image_search_suffix(diagram_type)
    topics = _split_visual_topics(cleaned_user)
    protocols = _extract_protocol_labels(cleaned_user, cleaned_answer, limit=4)
    components = _extract_component_labels(cleaned_user, cleaned_answer, limit=4)
    keywords = _extract_visual_keywords(f"{cleaned_user} {cleaned_answer}", limit=8)

    queries = [
        _build_answer_image_search_query(cleaned_user, cleaned_answer),
        _normalize_image_prompt_text(f"{cleaned_user} {suffix}", 280),
        _normalize_image_prompt_text(f"{' '.join(topics[:4])} {suffix}", 280) if topics else "",
        _normalize_image_prompt_text(f"{' '.join(protocols[:4])} {suffix}", 280) if protocols else "",
        _normalize_image_prompt_text(f"{' '.join(components[:4])} {suffix}", 280) if components else "",
        _normalize_image_prompt_text(f"{' '.join(keywords[:5])} {suffix}", 280) if keywords else "",
    ]

    deduped: List[str] = []
    seen: set[str] = set()
    for query in queries:
        cleaned_query = " ".join((query or "").split()).strip()
        if not cleaned_query:
            continue
        lowered = cleaned_query.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(cleaned_query)
    return deduped[:4]


def _score_answer_diagram_result(
    result: dict,
    *,
    diagram_type: str,
    required_terms: List[str],
    query_index: int,
) -> float:
    haystack = " ".join(
        str(result.get(field, "") or "").lower()
        for field in ("title", "url", "source", "image_url", "thumbnail_url")
    )
    if not haystack:
        return 0.0

    match_count = 0
    score = 0.0
    for term in required_terms:
        if _contains_search_term(haystack, term):
            match_count += 1
            score += 3.0

    normalized_type = (diagram_type or "").lower()
    for marker in {
        "diagram",
        "comparison",
        "flow",
        "architecture",
        "block",
        "protocol",
        "system",
        "network",
        "chart",
    }:
        if marker in haystack:
            score += 1.0

    if normalized_type and normalized_type.split()[0] in haystack:
        score += 2.0

    width = result.get("width")
    height = result.get("height")
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        megapixels = (width * height) / 1_000_000
        score += min(megapixels, 6.0)
        if width >= 1200 or height >= 1200:
            score += 1.5

    if str(result.get("image_url") or "").strip():
        score += 1.0

    score += max(0, 2 - query_index) * 0.5
    if match_count == 0:
        score -= 2.5
    return score


async def _search_answer_diagrams(user_message: str, answer: str, limit: int = 2) -> List[str]:
    cleaned_user = _normalize_image_prompt_text(user_message, 220)
    cleaned_answer = _normalize_image_prompt_text(answer, 320)
    if not cleaned_user and not cleaned_answer:
        return []

    diagram_type, _, _ = _answer_visual_strategy(cleaned_user, cleaned_answer)
    required_terms = list(
        dict.fromkeys(
            _split_visual_topics(cleaned_user)
            + _extract_protocol_labels(cleaned_user, cleaned_answer, limit=4)
            + _extract_component_labels(cleaned_user, cleaned_answer, limit=4)
            + _extract_visual_keywords(f"{cleaned_user} {cleaned_answer}", limit=6)
        )
    )[:8]

    candidates: dict[str, float] = {}
    for query_index, query in enumerate(_build_answer_image_search_queries(cleaned_user, cleaned_answer)):
        results = await search_web_images(query, max_results=6)
        for result in results:
            image_url = str(result.get("image_url") or result.get("thumbnail_url") or "").strip()
            if not image_url:
                continue
            score = _score_answer_diagram_result(
                result,
                diagram_type=diagram_type,
                required_terms=required_terms,
                query_index=query_index,
            )
            if score > 0:
                candidates[image_url] = max(score, candidates.get(image_url, float("-inf")))

    ranked = sorted(candidates.items(), key=lambda item: item[1], reverse=True)
    return [image_url for image_url, _ in ranked[:limit]]


async def _ground_answer_image_prompt(prompt: str) -> tuple[str, List[str]]:
    user_message, answer = _extract_answer_image_context_from_prompt(prompt)
    if not answer:
        return prompt, []

    web_images = await _search_answer_diagrams(user_message, answer, limit=2)
    if web_images:
        return prompt, web_images

    grounding_lines = []
    search_query = _build_answer_image_search_query(user_message, answer)
    text_results = await search_web(search_query, max_results=3) if search_query else []
    for index, result in enumerate(text_results[:3], start=1):
        title = _normalize_image_prompt_text(str(result.get("title", "")), 120)
        snippet = _normalize_image_prompt_text(str(result.get("snippet", "")), 220)
        source = _normalize_image_prompt_text(str(result.get("source", "")), 60)
        if not title and not snippet:
            continue
        grounding_lines.append(f"[{index}] {title} | {source} | {snippet}")

    if not grounding_lines:
        return prompt, []

    grounded_prompt = (
        f"{prompt}\n"
        "Web grounding for accuracy:\n"
        + "\n".join(grounding_lines)
        + "\nUse the assistant answer plus this grounding. If they conflict, keep the visual conservative and do not add unsupported details."
    )
    return grounded_prompt[:4200], []


def _dedupe_image_assets(images: List[str], limit: int = 3) -> List[str]:
    deduped: List[str] = []
    seen: set[str] = set()
    for image in images:
        candidate = normalize_image_asset(image)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
        if len(deduped) >= limit:
            break
    return deduped


async def _generate_images_best_effort(prompt: str) -> List[str]:
    cleaned_prompt = (prompt or "").strip()
    if not cleaned_prompt:
        return []
    grounded_prompt = cleaned_prompt
    if "Assistant answer:" in cleaned_prompt:
        grounded_prompt, web_images = await _ground_answer_image_prompt(cleaned_prompt)
        if web_images:
            web_images = _dedupe_image_assets(web_images, limit=3)
        try:
            generated_images = _dedupe_image_assets(
                await _generate_images_for_prompt(grounded_prompt),
                limit=3,
            )
            if generated_images:
                return generated_images
        except Exception as exc:
            logger.warning(
                "Answer image generation failed prompt=%s error=%s",
                _preview_text(grounded_prompt),
                exc,
            )
        return web_images if web_images else []

    try:
        return _dedupe_image_assets(await _generate_images_for_prompt(grounded_prompt), limit=3)
    except Exception as exc:
        logger.warning(
            "Image generation failed prompt=%s error=%s",
            _preview_text(grounded_prompt),
            exc,
        )
        return []


async def _generate_images_for_prompt(prompt: str) -> List[str]:
    if not ai_service.has_available_image_provider():
        return []
    images = await ai_service.generate_image(prompt)
    if images:
        return images
    return []


def _start_prompt_image_task(enabled: bool, user_message: str):
    if not enabled:
        return None
    prompt = _build_prompt_image_prompt(user_message)
    if not prompt:
        return None
    return asyncio.create_task(_generate_images_best_effort(prompt))


async def _await_image_task(task) -> List[str]:
    if task is None:
        return []
    try:
        return await task
    except Exception as exc:
        logger.warning("Image generation task failed error=%s", exc)
        return []


def _resolve_answer_image_request(
    requested: Optional[bool],
    meta: Optional[dict],
    message: Optional[str] = None,
) -> bool:
    if requested is not None:
        return bool(requested)
    if isinstance(meta, dict) and "generate_answer_image" in meta:
        return bool(meta.get("generate_answer_image"))
    return _looks_like_diagram_request(message)


def _strip_inline_file_tags(text: str) -> str:
    return " ".join(_FILE_TAG_PATTERN.sub(" ", text or "").split()).strip()


def _strip_tool_directives(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    cleaned = [line for line in lines if not (line.startswith("[") and line.endswith("]"))]
    return " ".join(cleaned).strip()


def _looks_like_image_request(message: str) -> bool:
    cleaned = _strip_tool_directives(_strip_inline_file_tags(message or ""))
    normalized = " ".join(cleaned.split()).strip()
    if not normalized:
        return False
    if any(pattern.search(normalized) for pattern in _IMAGE_INTENT_PATTERNS):
        return True
    if _NON_IMAGE_HELP_PATTERN.search(normalized):
        return False

    detail_matches = _IMAGE_PROMPT_DETAIL_PATTERN.findall(normalized)
    comma_count = normalized.count(",")
    word_count = len(normalized.split())
    return word_count >= 8 and comma_count >= 2 and len(detail_matches) >= 2


def _resolve_effective_mode(requested_mode: Optional[str], message: str) -> str:
    normalized_mode = (requested_mode or "chat").lower()
    if normalized_mode == "chat" and _looks_like_image_request(message):
        return "image"
    return normalized_mode


def _normalize_user_message(text: str) -> str:
    raw_text = (text or "").strip()
    cleaned_text = _strip_inline_file_tags(raw_text)
    if cleaned_text:
        return cleaned_text
    if _FILE_TAG_PATTERN.search(raw_text):
        return "Summarize this document."
    return raw_text


def _decode_image_b64(image_b64: Optional[str]) -> bytes:
    raw_value = str(image_b64 or "").strip()
    if not raw_value:
        return b""
    if "," in raw_value and raw_value.startswith("data:"):
        raw_value = raw_value.split(",", 1)[-1]
    return base64.b64decode(raw_value)


def _image_data_url(image_b64: Optional[str], mime_type: Optional[str]) -> Optional[str]:
    raw_value = str(image_b64 or "").strip()
    if not raw_value:
        return None
    if raw_value.startswith("data:"):
        return raw_value
    normalized_mime_type = str(mime_type or "").strip() or "image/png"
    return f"data:{normalized_mime_type};base64,{raw_value}"


def _document_reference_from_meta(meta: Optional[dict]) -> tuple[Optional[int], Optional[str]]:
    if not isinstance(meta, dict):
        return None, None

    raw_document_id = meta.get("document_id")
    try:
        document_id = int(raw_document_id) if raw_document_id is not None else None
    except (TypeError, ValueError):
        document_id = None

    document_name = str(meta.get("document_name") or "").strip() or None
    return document_id, document_name


def _resolve_document_id(requested_document_id: Optional[int], *metas: Optional[dict]) -> Optional[int]:
    if requested_document_id is not None:
        return requested_document_id

    for meta in metas:
        document_id, _ = _document_reference_from_meta(meta)
        if document_id is not None:
            return document_id
    return None


def _preview_text(text: str) -> str:
    limit = int(getattr(settings, "AI_LOG_PREVIEW_CHARS", 400) or 400)
    return " ".join((text or "").split())[:limit]


def _normalize_regenerate_answer(text: Optional[str], limit: int = 3200) -> str:
    return " ".join((text or "").split())[:limit].strip()


def _looks_like_diagram_request(message: Optional[str]) -> bool:
    return bool(_DIAGRAM_REQUEST_PATTERN.search(str(message or "")))


def _needs_full_document_context(message: Optional[str]) -> bool:
    raw_text = str(message or "")
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


def _response_max_tokens(message: Optional[str], mode: str, doc_context: Optional[str] = None) -> int:
    base = int(getattr(settings, "AI_MAX_TOKENS", 2048) or 2048)
    fast_cap = int(getattr(settings, "AI_FAST_MAX_TOKENS", 320) or 320)
    cleaned_message = " ".join(str(message or "").split())
    if (mode or "").lower() == "image":
        return base

    if infer_use_case(mode, cleaned_message) == "quick":
        return max(160, min(base, fast_cap))

    marks = [int(match.group("marks")) for match in _MARKS_PATTERN.finditer(cleaned_message)]

    if _needs_full_document_context(message):
        return max(base, _EXPANDED_RESPONSE_MAX_TOKENS)

    if any(mark >= 15 for mark in marks):
        return max(base, 8192)

    if any(mark >= 10 for mark in marks):
        return max(base, 6144)

    if any(mark >= 8 for mark in marks):
        return max(base, 5120)

    if _ASSIGNMENT_REQUEST_PATTERN.search(cleaned_message):
        return max(base, 4096)

    if doc_context and len(doc_context) > _DEFAULT_DOCUMENT_CONTEXT_CHARS:
        return max(base, 8192)

    return base


async def _resolve_document_context(message: Optional[str], document: Document) -> Optional[str]:
    document_text = str(getattr(document, "text_content", "") or "").strip()
    if not document_text:
        return None

    if _needs_full_document_context(message):
        return document_text[:_EXPANDED_DOCUMENT_CONTEXT_CHARS]

    search_results = await vector_service.search(
        str(message or ""),
        k=_DEFAULT_DOCUMENT_SEARCH_K,
        doc_id=document.id,
    )
    if search_results:
        combined = "\n\n".join(result[0] for result in search_results if result and result[0])
        if combined.strip():
            return combined[:_DEFAULT_DOCUMENT_CONTEXT_CHARS]

    return document_text[:_DEFAULT_DOCUMENT_CONTEXT_CHARS]


def _document_question_terms(question: str, limit: int = 10) -> List[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "answer",
        "assignment",
        "compare",
        "comparison",
        "describe",
        "difference",
        "document",
        "draw",
        "explain",
        "for",
        "give",
        "how",
        "in",
        "is",
        "it",
        "me",
        "of",
        "or",
        "please",
        "question",
        "show",
        "simple",
        "step",
        "steps",
        "summarize",
        "tell",
        "the",
        "this",
        "what",
        "with",
        "write",
    }
    raw_terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9/+.-]{1,}", str(question or "").lower())
    terms: List[str] = []
    seen: set[str] = set()

    for term in raw_terms:
        cleaned = term.strip().lower()
        if (
            not cleaned
            or cleaned in stopwords
            or len(cleaned) < 3
            or cleaned.isdigit()
            or cleaned in seen
        ):
            continue
        seen.add(cleaned)
        terms.append(cleaned)
        if len(terms) >= limit:
            break

    return terms


def _document_passages(text: str, chunk_chars: int = 420) -> List[str]:
    passages: List[str] = []
    sections = re.split(r"\n{2,}", str(text or ""))

    for section in sections:
        cleaned_section = " ".join(section.split()).strip()
        if not cleaned_section:
            continue
        if len(cleaned_section) <= chunk_chars:
            passages.append(cleaned_section)
            continue

        sentences = re.split(r"(?<=[.!?])\s+", cleaned_section)
        current_chunk = ""
        for sentence in sentences:
            candidate = f"{current_chunk} {sentence}".strip()
            if current_chunk and len(candidate) > chunk_chars:
                passages.append(current_chunk)
                current_chunk = sentence.strip()
            else:
                current_chunk = candidate

        if current_chunk:
            passages.append(current_chunk)

    if passages:
        return passages

    cleaned_text = " ".join(str(text or "").split()).strip()
    return [cleaned_text] if cleaned_text else []


def _score_document_passage(passage: str, terms: List[str], index: int) -> float:
    lowered = passage.lower()
    score = 0.0

    for term in terms:
        if term in lowered:
            score += 3.0 + min(lowered.count(term), 3)

    if len(terms) >= 2:
        consecutive_matches = sum(
            1 for first, second in zip(terms, terms[1:]) if f"{first} {second}" in lowered
        )
        score += consecutive_matches * 2.5

    score += max(0, 2 - index) * 0.15
    return score


def _trim_document_excerpt(text: str, limit: int = 320) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit].rstrip()}..."


def _rank_document_passages(question: str, context: str) -> List[tuple[float, int, str]]:
    passages = _document_passages(context)
    if not passages:
        return []

    terms = _document_question_terms(question)
    return sorted(
        (
            (_score_document_passage(passage, terms, index), index, passage)
            for index, passage in enumerate(passages)
        ),
        key=lambda item: (item[0], -item[1]),
        reverse=True,
    )


def _document_sources_from_context(question: str, context: Optional[str], limit: int = 3) -> List[dict]:
    ranked_passages = _rank_document_passages(question, str(context or ""))
    if not ranked_passages:
        return []

    selected = [(score, index, passage) for score, index, passage in ranked_passages if score > 0][:limit]
    if not selected:
        selected = ranked_passages[:limit]

    sources: List[dict] = []
    seen: set[str] = set()

    for source_index, (_, _, passage) in enumerate(selected, start=1):
        excerpt = _trim_document_excerpt(passage, limit=280)
        normalized_excerpt = excerpt.lower()
        if not excerpt or normalized_excerpt in seen:
            continue
        seen.add(normalized_excerpt)
        sources.append(
            {
                "kind": "document",
                "title": f"Document Source {source_index}",
                "label": f"Document Source {source_index}",
                "excerpt": excerpt,
            }
        )

    return sources


def _fallback_document_answer_from_context(question: str, context: Optional[str]) -> str:
    ranked_passages = _rank_document_passages(question, str(context or ""))
    if not ranked_passages:
        return "I don't know based on the provided document."

    selected = [passage for score, _, passage in ranked_passages if score > 0][:3]
    if not selected:
        selected = [passage for _, _, passage in ranked_passages[:2]]

    excerpts = [
        f"{index + 1}. {_trim_document_excerpt(passage)}"
        for index, passage in enumerate(selected)
    ]

    if len(excerpts) == 1:
        return (
            "I could not fully verify a complete answer from the uploaded document, but this is the "
            f"most relevant part I found:\n\n{excerpts[0]}"
        )

    return (
        "I could not fully verify a complete answer from the uploaded document, but these are the "
        "most relevant parts I found:\n\n"
        + "\n".join(excerpts)
    )


def _build_regenerate_instruction(previous_answer: Optional[str]) -> str:
    cleaned_answer = _normalize_regenerate_answer(previous_answer)
    if not cleaned_answer:
        return REGENERATE_VARIATION_INSTRUCTION

    return (
        f"{REGENERATE_VARIATION_INSTRUCTION} "
        "Treat the previous assistant answer as a draft to improve. "
        "Preserve the same user intent, keep any correct parts, and rewrite weak or unclear sections. "
        "If the previous answer was an error, apology, fallback notice, or refusal, do not repeat that wording. "
        "Answer the user's original request directly instead.\n\n"
        f"Previous assistant answer draft:\n{cleaned_answer}"
    )


def _resolve_regenerated_text(candidate_text: Optional[str], previous_answer: Optional[str]) -> str:
    cleaned_candidate = str(candidate_text or "").strip()
    cleaned_previous = _normalize_regenerate_answer(previous_answer)

    if cleaned_candidate and cleaned_candidate != FALLBACK_MESSAGE:
        return cleaned_candidate
    if cleaned_previous and cleaned_previous != FALLBACK_MESSAGE:
        return cleaned_previous
    if cleaned_candidate:
        return cleaned_candidate
    if cleaned_previous:
        return cleaned_previous
    return FALLBACK_MESSAGE


def _resolve_provider_and_model(
    mode: str,
    requested_provider: Optional[str],
    requested_model: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    explicit_provider = (requested_provider or "").strip().lower() or None
    explicit_model = (requested_model or "").strip() or None
    return explicit_provider, explicit_model


def _build_ai_messages(
    history: List[dict],
    user_message: str,
    mode: str,
    doc_context: Optional[str] = None,
    extra_instruction: Optional[str] = None,
    instruction_message: Optional[str] = None,
) -> List[dict]:
    ai_messages = build_messages(
        [*history, {"role": "user", "content": user_message}],
        mode,
        instruction_message=instruction_message,
    )
    insert_index = 1
    if extra_instruction:
        ai_messages.insert(insert_index, {"role": "system", "content": extra_instruction})
        insert_index += 1
    if doc_context:
        if (mode or "").lower() == "documents":
            ai_messages.insert(insert_index, {"role": "system", "content": _DOCUMENT_GROUNDING_INSTRUCTION})
            insert_index += 1
        ai_messages.insert(insert_index, {"role": "system", "content": f"Document context:\n{doc_context[:8000]}"})
    return ai_messages


async def _collect_ai_response(
    ai_messages: List[dict],
    provider: Optional[str],
    model: Optional[str],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    use_case: Optional[str] = None,
) -> str:
    response_text = ""
    async for chunk in ai_service.chat_stream(
        ai_messages,
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        use_case=use_case,
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
    if force_search:
        return True
    if _VOLATILE_FACT_PATTERN.search(cleaned):
        return True
    return is_temporal_query(cleaned)


def _verification_max_tokens(max_tokens: Optional[int]) -> int:
    if max_tokens is None:
        return 768
    return max(320, min(int(max_tokens), 1024))


def _merge_extra_instructions(*parts: Optional[str]) -> Optional[str]:
    cleaned_parts = [str(part).strip() for part in parts if str(part or "").strip()]
    if not cleaned_parts:
        return None
    return "\n\n".join(cleaned_parts)


def _looks_like_stale_cutoff_answer(answer: Optional[str]) -> bool:
    cleaned_answer = " ".join((answer or "").split())
    if not cleaned_answer:
        return False
    return any(pattern.search(cleaned_answer) for pattern in _STALE_KNOWLEDGE_REPLY_PATTERNS)


def _should_cross_check_answer(
    user_message: str,
    source_material: Optional[str],
    draft_answer: Optional[str],
) -> bool:
    cleaned_answer = str(draft_answer or "").strip()
    if not cleaned_answer or cleaned_answer == FALLBACK_MESSAGE:
        return False

    normalized_user = " ".join((user_message or "").split()).strip()
    normalized_source = " ".join((source_material or "").split()).strip()
    return bool(normalized_source and normalized_source != normalized_user)


def _build_cross_check_messages(
    user_message: str,
    source_material: str,
    draft_answer: str,
) -> List[dict]:
    verifier_system = (
        "You are verifying a draft answer for factual accuracy.\n"
        "- Use the provided source material as the ground truth for current facts.\n"
        "- Correct unsupported or outdated names, dates, numbers, prices, standings, releases, or claims.\n"
        "- Remove stale knowledge-cutoff or no-browsing disclaimers when the source material already provides fresh facts.\n"
        "- If the source material does not support a detail, remove it or briefly mark it as uncertain.\n"
        "- Preserve the user's language, the draft's useful level of detail, and its helpful Markdown structure.\n"
        "- Do not flatten a structured draft into one dense paragraph.\n"
        "- Keep helpful headings, bullets, numbered steps, tables, and code blocks unless a correction requires changing that specific part.\n"
        f"{get_presentation_style_prompt()}\n"
        "- Return only the final corrected answer."
    )
    verifier_prompt = (
        f"User question:\n{user_message.strip()}\n\n"
        f"Source material:\n{source_material[:_VERIFICATION_SOURCE_CHARS].strip()}\n\n"
        f"Draft answer to verify:\n{draft_answer.strip()}"
    )
    return [
        {"role": "system", "content": verifier_system},
        {"role": "user", "content": verifier_prompt},
    ]


async def _cross_check_answer_if_needed(
    user_message: str,
    source_material: Optional[str],
    draft_answer: str,
    provider: Optional[str],
    model: Optional[str],
    max_tokens: Optional[int] = None,
    compatible_provider: Optional[str] = None,
) -> str:
    if not _should_cross_check_answer(user_message, source_material, draft_answer):
        return draft_answer

    if compatible_provider and not model:
        return draft_answer

    verifier_messages = _build_cross_check_messages(
        user_message,
        str(source_material or ""),
        draft_answer,
    )
    verifier_max_tokens = _verification_max_tokens(max_tokens)

    try:
        if compatible_provider:
            revised = await generate_response(
                compatible_provider,
                model or "",
                verifier_messages,
                temperature=_VERIFICATION_TEMPERATURE,
                max_tokens=verifier_max_tokens,
            )
            verified_text = (revised.get("response", "") if isinstance(revised, dict) else str(revised)).strip()
        else:
            verified_text = await _collect_ai_response(
                verifier_messages,
                provider,
                model,
                temperature=_VERIFICATION_TEMPERATURE,
                max_tokens=verifier_max_tokens,
                use_case="research",
            )
    except Exception as exc:
        logger.warning(
            "Answer cross-check failed provider=%s model=%s compat_provider=%s error=%s",
            provider or "<auto>",
            model or "<default>",
            compatible_provider or "<none>",
            exc,
        )
        return draft_answer

    return verified_text or draft_answer


async def _fetch_page_excerpt(url: str, max_chars: int = 1400, timeout_seconds: float = 4.0) -> Optional[str]:
    try:
        page_text = await asyncio.wait_for(fetch_page_content(url, max_chars=max_chars), timeout=timeout_seconds)
    except Exception:
        return None

    if not page_text or page_text.startswith("Could not fetch page:"):
        return None
    return page_text


async def _retry_stale_answer_with_fresh_sources(
    history: List[dict],
    user_message: str,
    mode: str,
    provider: Optional[str],
    model: Optional[str],
    doc_context: Optional[str] = None,
    extra_instruction: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> Optional[str]:
    refreshed_answer, _ = await _retry_stale_answer_with_fresh_sources_bundle(
        history,
        user_message,
        mode,
        provider,
        model,
        doc_context=doc_context,
        extra_instruction=extra_instruction,
        max_tokens=max_tokens,
    )
    return refreshed_answer


async def _retry_stale_answer_with_fresh_sources_bundle(
    history: List[dict],
    user_message: str,
    mode: str,
    provider: Optional[str],
    model: Optional[str],
    doc_context: Optional[str] = None,
    extra_instruction: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> tuple[Optional[str], List[dict]]:
    searched_message, searched_sources = await _maybe_enhance_temporal_message_with_sources(
        user_message,
        force_search=True,
    )
    if searched_message == user_message:
        return await _search_backup_answer_bundle(user_message, force_search=True)

    retry_messages = _build_ai_messages(
        history,
        searched_message,
        mode,
        doc_context=doc_context,
        extra_instruction=_merge_extra_instructions(extra_instruction, _FRESHNESS_RETRY_INSTRUCTION),
        instruction_message=user_message,
    )

    try:
        retry_answer = await _collect_ai_response(
            retry_messages,
            provider,
            model,
            max_tokens=max_tokens,
            use_case="research",
        )
        retry_answer = await _cross_check_answer_if_needed(
            user_message,
            searched_message,
            retry_answer,
            provider,
            model,
            max_tokens=max_tokens,
        )
        if retry_answer and not _looks_like_stale_cutoff_answer(retry_answer):
            return retry_answer, searched_sources
    except Exception as exc:
        logger.warning(
            "Freshness retry failed mode=%s provider=%s model=%s error=%s",
            mode,
            provider or "<auto>",
            model or "<default>",
            exc,
        )

    return await _search_backup_answer_bundle(user_message, force_search=True)


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


def _visible_search_sources(results: List[dict], max_items: int = 3) -> List[dict]:
    sources: List[dict] = []
    seen_urls = set()

    for result in results:
        if len(sources) >= max_items:
            break

        url = str(result.get("url") or "").strip()
        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        source_item = {
            "title": str(result.get("title") or "Source").strip() or "Source",
            "url": url,
        }
        if result.get("source"):
            source_item["source"] = str(result.get("source")).strip()
        if result.get("date"):
            source_item["date"] = str(result.get("date")).strip()
        if result.get("snippet"):
            source_item["snippet"] = str(result.get("snippet")).strip()[:240]
        sources.append(source_item)

    return sources


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
    answer, _ = await _search_backup_answer_bundle(message, force_search=force_search)
    return answer


async def _search_backup_answer_bundle(
    message: str,
    force_search: bool = False,
) -> tuple[Optional[str], List[dict]]:
    if not _should_use_search(message, force_search=force_search):
        return None, []

    results = await search_web(_build_search_query(message), max_results=5)
    if not results:
        return None, []

    return _format_search_fallback_answer(results), _visible_search_sources(results)


async def _best_effort_answer(
    history: List[dict],
    user_message: str,
    mode: str,
    provider: Optional[str],
    model: Optional[str],
    doc_context: Optional[str] = None,
    extra_instruction: Optional[str] = None,
    force_search: bool = False,
    max_tokens: Optional[int] = None,
) -> str:
    answer, _ = await _best_effort_answer_bundle(
        history,
        user_message,
        mode,
        provider,
        model,
        doc_context=doc_context,
        extra_instruction=extra_instruction,
        force_search=force_search,
        max_tokens=max_tokens,
    )
    return answer


async def _best_effort_answer_bundle(
    history: List[dict],
    user_message: str,
    mode: str,
    provider: Optional[str],
    model: Optional[str],
    doc_context: Optional[str] = None,
    extra_instruction: Optional[str] = None,
    force_search: bool = False,
    max_tokens: Optional[int] = None,
) -> tuple[str, List[dict]]:
    if mode == "documents":
        primary_message = user_message
        primary_sources = _document_sources_from_context(user_message, doc_context)
    else:
        primary_message, primary_sources = await _maybe_enhance_temporal_message_with_sources(
            user_message,
            force_search=force_search,
        )
    use_case = "research" if force_search else infer_use_case(mode, user_message)
    resolved_max_tokens = max_tokens or _response_max_tokens(user_message, mode, doc_context)

    try:
        primary_messages = _build_ai_messages(
            history,
            primary_message,
            mode,
            doc_context=doc_context,
            extra_instruction=extra_instruction,
            instruction_message=user_message,
        )
        primary_answer = await _collect_ai_response(
            primary_messages,
            provider,
            model,
            max_tokens=resolved_max_tokens,
            use_case=use_case,
        )
        primary_answer = await _cross_check_answer_if_needed(
            user_message,
            doc_context if mode == "documents" and doc_context else primary_message,
            primary_answer,
            provider,
            model,
            max_tokens=resolved_max_tokens,
        )
        if mode == "documents" and _looks_like_stale_cutoff_answer(primary_answer):
            return _fallback_document_answer_from_context(user_message, doc_context), primary_sources
        if _looks_like_stale_cutoff_answer(primary_answer):
            refreshed_answer, refreshed_sources = await _retry_stale_answer_with_fresh_sources_bundle(
                history,
                user_message,
                mode,
                provider,
                model,
                doc_context=doc_context,
                extra_instruction=extra_instruction,
                max_tokens=resolved_max_tokens,
            )
            if refreshed_answer:
                return refreshed_answer, refreshed_sources or primary_sources
        return primary_answer, primary_sources
    except Exception as exc:
        logger.warning(
            "Primary AI answer failed mode=%s provider=%s model=%s error=%s",
            mode,
            provider or "<auto>",
            model or "<default>",
            exc,
        )
        if mode == "documents":
            return _fallback_document_answer_from_context(user_message, doc_context), primary_sources

    if mode != "documents" and primary_message == user_message:
        searched_message, searched_sources = await _maybe_enhance_temporal_message_with_sources(
            user_message,
            force_search=True,
        )
        if searched_message != user_message:
            try:
                retry_messages = _build_ai_messages(
                    history,
                    searched_message,
                    mode,
                    doc_context=doc_context,
                    extra_instruction=extra_instruction,
                    instruction_message=user_message,
                )
                retry_answer = await _collect_ai_response(
                    retry_messages,
                    provider,
                    model,
                    max_tokens=resolved_max_tokens,
                    use_case="research" if force_search or searched_message != user_message else use_case,
                )
                retry_answer = await _cross_check_answer_if_needed(
                    user_message,
                    searched_message,
                    retry_answer,
                    provider,
                    model,
                    max_tokens=resolved_max_tokens,
                )
                if _looks_like_stale_cutoff_answer(retry_answer):
                    search_backup, backup_sources = await _search_backup_answer_bundle(
                        user_message,
                        force_search=True,
                    )
                    if search_backup:
                        return search_backup, backup_sources
                return retry_answer, searched_sources
            except Exception as exc:
                logger.warning(
                    "Search-backed AI retry failed mode=%s provider=%s model=%s error=%s",
                    mode,
                    provider or "<auto>",
                    model or "<default>",
                    exc,
                )

    search_backup, backup_sources = await _search_backup_answer_bundle(
        user_message,
        force_search=force_search,
    )

    if not search_backup and mode != "documents" and not force_search:
        search_backup, backup_sources = await _search_backup_answer_bundle(
            user_message,
            force_search=True,
        )

    if search_backup:
        return search_backup, backup_sources

    if mode == "documents":
        return _fallback_document_answer_from_context(user_message, doc_context), primary_sources

    return FALLBACK_MESSAGE, []


async def _rescue_stale_compatible_provider_answer(
    history: List[dict],
    user_message: str,
    draft_answer: str,
    mode: str,
    max_tokens: Optional[int],
    extra_instruction: Optional[str] = None,
) -> str:
    rescued_answer, _ = await _rescue_stale_compatible_provider_answer_bundle(
        history,
        user_message,
        draft_answer,
        mode,
        max_tokens,
        extra_instruction=extra_instruction,
    )
    return rescued_answer


async def _rescue_stale_compatible_provider_answer_bundle(
    history: List[dict],
    user_message: str,
    draft_answer: str,
    mode: str,
    max_tokens: Optional[int],
    extra_instruction: Optional[str] = None,
) -> tuple[str, List[dict]]:
    if not _looks_like_stale_cutoff_answer(draft_answer):
        return draft_answer, []

    rescued_answer, rescued_sources = await _best_effort_answer_bundle(
        history,
        user_message,
        mode,
        None,
        None,
        extra_instruction=_merge_extra_instructions(extra_instruction, _FRESHNESS_RETRY_INSTRUCTION),
        force_search=True,
        max_tokens=max_tokens,
    )
    if rescued_answer and not _looks_like_stale_cutoff_answer(rescued_answer):
        return rescued_answer, rescued_sources
    return draft_answer, []


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
    return append_conversation_message(db, conversation, role, content, meta)


def _save_conversation(db: Session, conversation: Conversation) -> Conversation:
    return save_conversation(db, conversation)


def _conversation_preview_text(
    db: Session,
    conversation: Conversation,
    limit: int = 120,
) -> Optional[str]:
    try:
        messages = ensure_conversation_messages(db, conversation)
    except Exception:
        return None

    for message in reversed(messages):
        content = " ".join(str(getattr(message, "content", "") or "").split()).strip()
        if not content:
            continue
        return content[:limit] + ("..." if len(content) > limit else "")

    summary = " ".join(str(getattr(conversation, "context_summary", "") or "").split()).strip()
    if not summary:
        return None
    return summary[:limit] + ("..." if len(summary) > limit else "")


async def _save_conversation_with_summary(
    db: Session,
    conversation: Conversation,
    *,
    refresh_summary: bool = False,
) -> Conversation:
    conversation = _save_conversation(db, conversation)
    if not refresh_summary:
        return conversation
    return await refresh_conversation_summary(db, conversation)


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

    summary_message = build_summary_history_message(conversation)
    if limit:
        recent_limit = limit
        if summary_message:
            recent_limit = max(6, limit // 2)
        history = history[-recent_limit:]

    return [summary_message, *history] if summary_message else history


def _session_id_from_request(http_request: Request) -> str:
    header_value = (http_request.headers.get("x-session-id") or "").strip()
    return header_value[:120] if header_value else "anonymous"


async def _maybe_enhance_temporal_message(message: str, force_search: bool = False) -> str:
    enhanced_message, _ = await _maybe_enhance_temporal_message_with_sources(
        message,
        force_search=force_search,
    )
    return enhanced_message


async def _maybe_enhance_temporal_message_with_sources(
    message: str,
    force_search: bool = False,
) -> tuple[str, List[dict]]:
    if not _should_use_search(message, force_search=force_search):
        return message, []

    search_query = _build_search_query(message)
    search_results = await search_web(search_query, max_results=5 if force_search else 4)
    if not search_results:
        return message, []

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    search_context = format_results_for_ai(search_results)
    visible_sources = _visible_search_sources(search_results)
    fetched_pages = []
    if force_search:
        page_targets = [
            ((result.get("url") or "").strip(), index)
            for index, result in enumerate(search_results[:1], start=1)
            if (result.get("url") or "").strip()
        ]
        if page_targets:
            page_texts = await asyncio.gather(
                *[_fetch_page_excerpt(url) for url, _ in page_targets],
                return_exceptions=True,
            )
            for (url, index), page_text in zip(page_targets, page_texts):
                if isinstance(page_text, Exception) or not page_text:
                    continue
                fetched_pages.append(f"[Page {index}] {url}\n{page_text}")

    page_context = "\n\n".join(fetched_pages).strip()
    if page_context:
        search_context = f"{search_context}\nPAGE EXCERPTS:\n\n{page_context}"

    search_instruction = (
        "Search mode is enabled. Use the search results below as the primary source.\n"
        "Verify names, dates, prices, rankings, and counts against the freshest source-backed results.\n"
        "Do not answer with a training or knowledge cutoff disclaimer when fresh sources are provided.\n"
        "If sources disagree, mention that briefly and give the best-supported answer."
        if force_search
        else "Use the search results below as the primary source only for recent, volatile, or year-specific facts.\n"
        "Do not answer with a training or knowledge cutoff disclaimer when fresh sources are provided.\n"
        "If the user asks about a specific year or range such as 2024 to 2025, prioritize results that match those years exactly."
    )

    return (
        f"Today's date is {today}.\n"
        f"{search_instruction}\n\n"
        f"{search_context}\n"
        f"User Question: {message}"
    ), visible_sources


@router.post("")
@router.post("/")
async def chat(
    http_request: Request,
    request: ChatRequest = Body(default=ChatRequest()),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Optional[Session] = Depends(get_db_optional),
):
    """Send a chat message and get AI response."""
    mode = _resolve_effective_mode(request.mode, request.message)
    provider_key = (request.provider or "").strip().lower()
    fallback_message = FALLBACK_MESSAGE
    generate_prompt_image = bool(request.generate_prompt_image)
    message_text = _normalize_user_message(request.message)
    image_bytes = _decode_image_b64(request.image_b64)
    has_uploaded_image = bool(image_bytes)
    uploaded_image_preview = _image_data_url(request.image_b64, request.image_mime_type)
    if has_uploaded_image and not message_text:
        message_text = "Describe this image clearly."
    generate_answer_image = mode != "image" and _resolve_answer_image_request(
        request.generate_answer_image,
        None,
        message_text,
    )

    if not message_text and not has_uploaded_image:
        payload = response_envelope("Please enter a message.")
        payload["type"] = "final"
        if request.stream:
            async def generate_empty():
                yield _sse_event(payload)

            return StreamingResponse(generate_empty(), media_type="text/event-stream")
        return payload

    await enforce_chat_rate_limit(http_request, current_user)
    image_generation_cost = _chat_image_generation_cost(
        mode,
        generate_prompt_image=generate_prompt_image,
        generate_answer_image=generate_answer_image,
    )
    if image_generation_cost:
        await enforce_image_rate_limit(
            http_request,
            current_user,
            cost=image_generation_cost,
        )

    if current_user is None or db is None:
        session_id = _session_id_from_request(http_request)
        history = get_history(limit=20, session_id=session_id)
        if has_uploaded_image and mode != "image":
            analysis_prompt = message_text or "Describe this image clearly."
            answer = await ai_service.analyze_image(
                analysis_prompt,
                image_bytes,
                mime_type=request.image_mime_type or "image/png",
                provider=request.provider,
                model=request.model,
                max_tokens=_response_max_tokens(analysis_prompt, mode),
            )
            add_message("user", analysis_prompt, session_id=session_id)
            add_message("assistant", answer, session_id=session_id)
            payload = _payload(answer)
            if request.stream:
                async def generate_public_image_analysis():
                    yield _sse_event({"type": "delta", "content": "Analyzing image..."})
                    yield _sse_event(_final_payload(answer))

                return StreamingResponse(generate_public_image_analysis(), media_type="text/event-stream")
            return payload

        instant = instant_reply(message_text)
        if instant:
            prompt_images = []
            answer_images = []
            if generate_prompt_image and mode != "image":
                prompt_images = await _generate_images_best_effort(_build_prompt_image_prompt(message_text))
            if generate_answer_image and mode != "image":
                answer_images = await _generate_images_best_effort(
                    _build_answer_image_prompt(message_text, instant)
                )
            add_message("user", message_text, session_id=session_id)
            add_message("assistant", instant, session_id=session_id)
            payload = _payload(instant, prompt_images=prompt_images, answer_images=answer_images)
            if request.stream:
                async def generate_instant():
                    yield _sse_event(
                        _final_payload(
                            instant,
                            prompt_images=prompt_images,
                            answer_images=answer_images,
                        )
                    )

                return StreamingResponse(generate_instant(), media_type="text/event-stream")
            return payload

        force_search = mode == "search"
        enhanced_message = message_text
        answer_sources: List[dict] = []
        if mode not in {"documents", "image"}:
            enhanced_message, answer_sources = await _maybe_enhance_temporal_message_with_sources(
                message_text,
                force_search=force_search,
            )

        public_messages = _build_ai_messages(
            history,
            enhanced_message,
            mode,
            instruction_message=message_text,
        )
        provider, model = _resolve_provider_and_model(mode, request.provider, request.model)
        response_max_tokens = _response_max_tokens(message_text, mode)
        _log_chat_request(mode, provider, model, message_text)

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

                prompt_image_task = _start_prompt_image_task(generate_prompt_image, message_text)

                async def generate_provider_stream():
                    full_response = ""
                    try:
                        async for chunk in stream_response(
                            provider_key,
                            request.model or "",
                            public_messages,
                            max_tokens=response_max_tokens,
                        ):
                            full_response += chunk
                            yield _sse_event({"type": "delta", "content": chunk})
                        full_response = full_response.strip()
                        if not full_response:
                            raise RuntimeError("Provider returned an empty response")
                        full_response = await _cross_check_answer_if_needed(
                            message_text,
                            enhanced_message,
                            full_response,
                            provider=None,
                            model=request.model,
                            max_tokens=response_max_tokens,
                            compatible_provider=provider_key,
                        )
                        full_response, rescued_sources = await _rescue_stale_compatible_provider_answer_bundle(
                            history,
                            message_text,
                            full_response,
                            mode,
                            response_max_tokens,
                        )
                        final_sources = rescued_sources or answer_sources
                        prompt_images = await _await_image_task(prompt_image_task)
                        answer_images = []
                        if generate_answer_image:
                            answer_images = await _generate_images_best_effort(
                                _build_answer_image_prompt(message_text, full_response)
                            )
                        _log_chat_response(mode, provider_key, request.model, full_response)
                        yield _sse_event(
                            _final_payload(
                                full_response,
                                prompt_images=prompt_images,
                                answer_images=answer_images,
                                sources=final_sources,
                            )
                        )
                    except Exception as exc:
                        yield _sse_event(_final_payload(fallback_message, interrupted=True))

                return StreamingResponse(generate_provider_stream(), media_type="text/event-stream")

            if not request.model:
                return _payload(SETUP_RETRY_MESSAGE)

            prompt_image_task = _start_prompt_image_task(generate_prompt_image, message_text)

            try:
                answer = await generate_response(
                    provider_key,
                    request.model,
                    public_messages,
                    max_tokens=response_max_tokens,
                )
                text = (answer.get("response", "") if isinstance(answer, dict) else str(answer)).strip()
                text = await _cross_check_answer_if_needed(
                    message_text,
                    enhanced_message,
                    text,
                    provider=None,
                    model=request.model,
                    max_tokens=response_max_tokens,
                    compatible_provider=provider_key,
                )
                text, rescued_sources = await _rescue_stale_compatible_provider_answer_bundle(
                    history,
                    message_text,
                    text,
                    mode,
                    response_max_tokens,
                )
                final_sources = rescued_sources or answer_sources
                prompt_images = await _await_image_task(prompt_image_task)
                answer_images = []
                if text and generate_answer_image:
                    answer_images = await _generate_images_best_effort(
                        _build_answer_image_prompt(message_text, text)
                    )
                if text:
                    _log_chat_response(mode, provider_key, request.model, text)
                return _payload(
                    text or fallback_message,
                    prompt_images=prompt_images,
                    answer_images=answer_images,
                    sources=final_sources,
                )
            except Exception as exc:
                logger.warning("Compatible provider public chat failed provider=%s model=%s error=%s", provider_key, request.model, exc)
                answer, final_sources = await _best_effort_answer_bundle(
                    history,
                    message_text,
                    mode,
                    None,
                    None,
                    force_search=force_search,
                )
                prompt_images = await _await_image_task(prompt_image_task)
                answer_images = []
                if answer and generate_answer_image and answer != FALLBACK_MESSAGE:
                    answer_images = await _generate_images_best_effort(
                        _build_answer_image_prompt(message_text, answer)
                    )
                return _payload(
                    answer,
                    prompt_images=prompt_images,
                    answer_images=answer_images,
                    sources=final_sources,
                )

        if mode == "documents":
            payload = response_envelope("Please log in to use document mode.")
            payload["type"] = "final"
            if request.stream:
                async def generate_login_required():
                    yield _sse_event(payload)

                return StreamingResponse(generate_login_required(), media_type="text/event-stream")
            return response_envelope("Please log in to use document mode.")

        if mode not in {"documents", "image"}:
            prompt_image_task = _start_prompt_image_task(generate_prompt_image, message_text)
            add_message("user", message_text, session_id=session_id)
            answer, answer_sources = await _best_effort_answer_bundle(
                history,
                message_text,
                mode,
                provider,
                model,
                force_search=force_search,
            )
            prompt_images = await _await_image_task(prompt_image_task)
            answer_images = []
            if answer and generate_answer_image and answer != FALLBACK_MESSAGE:
                answer_images = await _generate_images_best_effort(
                    _build_answer_image_prompt(message_text, answer)
                )
            add_message("assistant", answer, session_id=session_id)
            _log_chat_response(mode, provider, model, answer)
            payload = _payload(
                answer,
                prompt_images=prompt_images,
                answer_images=answer_images,
                sources=answer_sources,
            )
            if request.stream:
                async def generate_fast():
                    yield _sse_event(
                        _final_payload(
                            answer,
                            prompt_images=prompt_images,
                            answer_images=answer_images,
                            sources=answer_sources,
                        )
                    )

                return StreamingResponse(generate_fast(), media_type="text/event-stream")
            return payload

        response_max_tokens = _response_max_tokens(message_text, mode)
        ai_messages = _build_ai_messages([], message_text, mode)

        if request.stream:
            async def generate_public():
                try:
                    if mode == "image":
                        yield _sse_event({"type": "delta", "content": "Generating image..."})
                        images = await _generate_images_for_prompt(message_text)
                        yield _sse_event(_final_payload("Here are your images.", images=images))
                        return

                    full_response = ""
                    async for chunk in ai_service.chat_stream(
                        ai_messages,
                        provider=provider,
                        model=model,
                        max_tokens=response_max_tokens,
                        use_case=infer_use_case(mode, message_text),
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
            images = await _generate_images_for_prompt(message_text)
            return _payload("Here are your images.", images=images)

        try:
            response_text = await _collect_ai_response(
                ai_messages,
                provider,
                model,
                max_tokens=response_max_tokens,
                use_case=infer_use_case(mode, message_text),
            )
            _log_chat_response(mode, provider, model, response_text)
            return _payload(response_text)
        except Exception as exc:
            logger.warning("Public structured chat completion failed: %s", exc)
            return _payload(fallback_message)

    document = None
    if mode == "documents":
        resolved_document_id = _resolve_document_id(request.document_id)
        if resolved_document_id is None:
            payload = _payload("Please upload a document first.")
            if request.stream:
                async def generate_missing_doc():
                    yield _sse_event(_final_payload("Please upload a document first."))

                return StreamingResponse(generate_missing_doc(), media_type="text/event-stream")
            return payload

        document = db.query(Document).filter(
            Document.id == resolved_document_id,
            Document.user_id == current_user.id,
        ).first()

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        if not document.is_processed:
            raise HTTPException(status_code=400, detail="Document is still being processed")

    conversation = _get_or_create_conversation(
        db,
        current_user,
        request.conversation_id,
        message_text,
    )
    user_message = _append_message(
        db,
        conversation,
        "user",
        message_text,
        meta=_merge_message_meta(
            _image_preferences(generate_prompt_image, generate_answer_image),
            images=[uploaded_image_preview] if uploaded_image_preview else None,
            attachment_kind="image" if has_uploaded_image else None,
            image_origin="upload" if has_uploaded_image else None,
            document_id=document.id if document else None,
            document_name=document.filename if document else None,
        ),
    )
    conversation = _save_conversation(db, conversation)
    prompt_image_task = _start_prompt_image_task(generate_prompt_image and mode != "image", message_text)

    if has_uploaded_image and mode != "image":
        answer = await ai_service.analyze_image(
            message_text or "Describe this image clearly.",
            image_bytes,
            mime_type=request.image_mime_type or "image/png",
            provider=request.provider,
            model=request.model,
            max_tokens=_response_max_tokens(message_text, mode),
        )
        _append_message(
            db,
            conversation,
            "assistant",
            answer,
            meta=_merge_message_meta({"mode": mode}),
        )
        conversation = await _save_conversation_with_summary(
            db,
            conversation,
            refresh_summary=True,
        )
        _log_chat_response(mode, request.provider, request.model, answer)
        payload = _payload(answer, conversation)
        if request.stream:
            async def generate_auth_image_analysis():
                yield _sse_event({"type": "delta", "content": "Analyzing image..."})
                yield _sse_event(_final_payload(answer, conversation))

            return StreamingResponse(generate_auth_image_analysis(), media_type="text/event-stream")
        return payload

    instant = instant_reply(message_text)
    if instant:
        prompt_images = await _await_image_task(prompt_image_task)
        answer_images = []
        if generate_answer_image and mode != "image":
            answer_images = await _generate_images_best_effort(
                _build_answer_image_prompt(message_text, instant)
            )
        _apply_images_to_message(
            user_message,
            images=prompt_images,
            generate_prompt_image=generate_prompt_image,
            generate_answer_image=generate_answer_image,
        )
        _append_message(
            db,
            conversation,
            "assistant",
            instant,
            meta=_merge_message_meta(
                {"mode": mode},
                images=answer_images,
                image_origin="answer" if answer_images else None,
            ),
        )
        conversation = await _save_conversation_with_summary(
            db,
            conversation,
            refresh_summary=True,
        )
        _log_chat_response(mode, request.provider, request.model, instant)
        payload = _payload(
            instant,
            conversation,
            prompt_images=prompt_images,
            answer_images=answer_images,
        )
        if request.stream:
            async def generate_instant_auth():
                yield _sse_event(
                    _final_payload(
                        instant,
                        conversation,
                        prompt_images=prompt_images,
                        answer_images=answer_images,
                    )
                )

            return StreamingResponse(generate_instant_auth(), media_type="text/event-stream")
        return payload

    provider, model = _resolve_provider_and_model(mode, request.provider, request.model)
    force_search = mode == "search"
    response_max_tokens = _response_max_tokens(message_text, mode)
    _log_chat_request(mode, provider, model, message_text, conversation.id)

    if provider_key in PROVIDERS and mode not in {"documents", "image"}:
        history = _conversation_history(db, conversation, drop_last=(mode not in {"documents", "image"}))
        enhanced_message = message_text
        answer_sources: List[dict] = []
        if mode not in {"documents", "image"}:
            enhanced_message, answer_sources = await _maybe_enhance_temporal_message_with_sources(
                message_text,
                force_search=force_search,
            )
        provider_messages = _build_ai_messages(
            history,
            enhanced_message,
            mode,
            instruction_message=message_text,
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
                    async for chunk in stream_response(
                        provider_key,
                        request.model or "",
                        provider_messages,
                        max_tokens=response_max_tokens,
                    ):
                        full_response += chunk
                        yield _sse_event({"type": "delta", "content": chunk})

                    full_response = full_response.strip()
                    if not full_response:
                        raise RuntimeError("Provider returned an empty response")
                    full_response = await _cross_check_answer_if_needed(
                        message_text,
                        enhanced_message,
                        full_response,
                        provider=None,
                        model=request.model,
                        max_tokens=response_max_tokens,
                        compatible_provider=provider_key,
                    )
                    full_response, rescued_sources = await _rescue_stale_compatible_provider_answer_bundle(
                        history,
                        message_text,
                        full_response,
                        mode,
                        response_max_tokens,
                    )
                    final_sources = rescued_sources or answer_sources
                    prompt_images = await _await_image_task(prompt_image_task)
                    answer_images = []
                    if generate_answer_image:
                        answer_images = await _generate_images_best_effort(
                            _build_answer_image_prompt(message_text, full_response)
                        )
                    _apply_images_to_message(
                        user_message,
                        images=prompt_images,
                        generate_prompt_image=generate_prompt_image,
                        generate_answer_image=generate_answer_image,
                    )
                    _append_message(
                        db,
                        conversation,
                        "assistant",
                        full_response,
                        meta=_merge_message_meta(
                            {"mode": mode},
                            images=answer_images,
                            image_origin="answer" if answer_images else None,
                            sources=final_sources,
                        ),
                    )
                    saved_conversation = await _save_conversation_with_summary(
                        db,
                        conversation,
                        refresh_summary=True,
                    )
                    _log_chat_response(mode, provider_key, request.model, full_response)
                    yield _sse_event(
                        _final_payload(
                            full_response,
                            saved_conversation,
                            prompt_images=prompt_images,
                            answer_images=answer_images,
                            sources=final_sources,
                        )
                    )
                except Exception as exc:
                    yield _sse_event(_final_payload(fallback_message, conversation, interrupted=True))

            return StreamingResponse(generate_provider_stream_auth(), media_type="text/event-stream")

        if not request.model:
            return _payload(SETUP_RETRY_MESSAGE, conversation)

        try:
            answer = await generate_response(
                provider_key,
                request.model,
                provider_messages,
                max_tokens=response_max_tokens,
            )
            text = (answer.get("response", "") if isinstance(answer, dict) else str(answer)).strip()
            text = await _cross_check_answer_if_needed(
                message_text,
                enhanced_message,
                text,
                provider=None,
                model=request.model,
                max_tokens=response_max_tokens,
                compatible_provider=provider_key,
            )
            text, rescued_sources = await _rescue_stale_compatible_provider_answer_bundle(
                history,
                message_text,
                text,
                mode,
                response_max_tokens,
            )
            final_sources = rescued_sources or answer_sources
        except Exception as exc:
            logger.warning("Compatible provider chat failed provider=%s model=%s error=%s", provider_key, request.model, exc)
            text, final_sources = await _best_effort_answer_bundle(
                history,
                message_text,
                mode,
                None,
                None,
                force_search=force_search,
            )

        prompt_images = await _await_image_task(prompt_image_task)
        answer_images = []
        if text and generate_answer_image and text != FALLBACK_MESSAGE:
            answer_images = await _generate_images_best_effort(
                _build_answer_image_prompt(message_text, text)
            )
        _apply_images_to_message(
            user_message,
            images=prompt_images,
            generate_prompt_image=generate_prompt_image,
            generate_answer_image=generate_answer_image,
        )
        _append_message(
            db,
            conversation,
            "assistant",
            text or fallback_message,
            meta=_merge_message_meta(
                {"mode": mode},
                images=answer_images,
                image_origin="answer" if answer_images else None,
                sources=final_sources,
            ),
        )
        conversation = await _save_conversation_with_summary(
            db,
            conversation,
            refresh_summary=True,
        )
        if text:
            _log_chat_response(mode, provider_key, request.model, text)
        return _payload(
            text or fallback_message,
            conversation,
            prompt_images=prompt_images,
            answer_images=answer_images,
            sources=final_sources,
        )

    if mode not in {"documents", "image"}:
        history = _conversation_history(db, conversation, drop_last=True)
        answer, answer_sources = await _best_effort_answer_bundle(
            history,
            message_text,
            mode,
            provider,
            model,
            force_search=force_search,
        )

        prompt_images = await _await_image_task(prompt_image_task)
        answer_images = []
        if answer and generate_answer_image and answer != FALLBACK_MESSAGE:
            answer_images = await _generate_images_best_effort(
                _build_answer_image_prompt(message_text, answer)
            )
        _apply_images_to_message(
            user_message,
            images=prompt_images,
            generate_prompt_image=generate_prompt_image,
            generate_answer_image=generate_answer_image,
        )
        _append_message(
            db,
            conversation,
            "assistant",
            answer,
            meta=_merge_message_meta(
                {"mode": mode},
                images=answer_images,
                image_origin="answer" if answer_images else None,
                sources=answer_sources,
            ),
        )
        conversation = await _save_conversation_with_summary(
            db,
            conversation,
            refresh_summary=True,
        )
        _log_chat_response(mode, provider, model, answer)
        payload = _payload(
            answer,
            conversation,
            prompt_images=prompt_images,
            answer_images=answer_images,
            sources=answer_sources,
        )

        if request.stream:
            async def generate_fast_auth():
                yield _sse_event(
                    _final_payload(
                        answer,
                        conversation,
                        prompt_images=prompt_images,
                        answer_images=answer_images,
                        sources=answer_sources,
                    )
                )

            return StreamingResponse(generate_fast_auth(), media_type="text/event-stream")
        return payload

    history = _conversation_history(db, conversation)
    doc_context = None
    if mode == "documents":
        await vector_service.ensure_document(document.text_content or "", document.id)
        doc_context = await _resolve_document_context(message_text, document)

    response_max_tokens = _response_max_tokens(message_text, mode, doc_context)
    ai_messages = build_messages(history, mode)
    if doc_context:
        ai_messages.insert(1, {"role": "system", "content": f"Document context:\n{doc_context}"})

    if request.stream:
        async def generate():
            try:
                if mode == "image":
                    yield _sse_event({"type": "delta", "content": "Generating image..."})
                    images = await _generate_images_for_prompt(message_text)
                    _append_message(
                        db,
                        conversation,
                        "assistant",
                        "Here are your images.",
                        meta={"mode": mode, "images": images},
                    )
                    saved_conversation = await _save_conversation_with_summary(
                        db,
                        conversation,
                        refresh_summary=True,
                    )
                    _log_chat_response(mode, provider, model, "Here are your images.")
                    yield _sse_event(_final_payload("Here are your images.", saved_conversation, images=images))
                    return

                if mode == "documents":
                    full_response, answer_sources = await _best_effort_answer_bundle(
                        history,
                        message_text,
                        mode,
                        provider,
                        model,
                        doc_context=doc_context,
                        max_tokens=response_max_tokens,
                    )
                    prompt_images = await _await_image_task(prompt_image_task)
                    answer_images = []
                    if generate_answer_image and full_response != FALLBACK_MESSAGE:
                        answer_images = await _generate_images_best_effort(
                            _build_answer_image_prompt(message_text, full_response)
                        )
                    _apply_images_to_message(
                        user_message,
                        images=prompt_images,
                        generate_prompt_image=generate_prompt_image,
                        generate_answer_image=generate_answer_image,
                        document_id=document.id if document else None,
                        document_name=document.filename if document else None,
                    )
                    _append_message(
                        db,
                        conversation,
                        "assistant",
                        full_response,
                        meta=_merge_message_meta(
                            {"mode": mode},
                            images=answer_images,
                            image_origin="answer" if answer_images else None,
                            document_id=document.id if document else None,
                            document_name=document.filename if document else None,
                            sources=answer_sources,
                        ),
                    )
                    saved_conversation = await _save_conversation_with_summary(
                        db,
                        conversation,
                        refresh_summary=True,
                    )
                    _log_chat_response(mode, provider, model, full_response)
                    yield _sse_event(
                        _final_payload(
                            full_response,
                            saved_conversation,
                            prompt_images=prompt_images,
                            answer_images=answer_images,
                            sources=answer_sources,
                        )
                    )
                    return

                full_response = ""
                async for chunk in ai_service.chat_stream(
                    ai_messages,
                    provider=provider,
                    model=model,
                    max_tokens=response_max_tokens,
                    use_case=infer_use_case(mode, message_text),
                ):
                    full_response += chunk
                    yield _sse_event({"type": "delta", "content": chunk})

                full_response = full_response.strip()
                if not full_response:
                    raise RuntimeError("AI provider returned an empty response")
                prompt_images = await _await_image_task(prompt_image_task)
                answer_images = []
                if generate_answer_image and mode != "image":
                    answer_images = await _generate_images_best_effort(
                        _build_answer_image_prompt(message_text, full_response)
                    )
                _apply_images_to_message(
                    user_message,
                    images=prompt_images,
                    generate_prompt_image=generate_prompt_image,
                    generate_answer_image=generate_answer_image,
                    document_id=document.id if document else None,
                    document_name=document.filename if document else None,
                )
                _append_message(
                    db,
                    conversation,
                    "assistant",
                    full_response,
                    meta=_merge_message_meta(
                        {"mode": mode},
                        images=answer_images,
                        image_origin="answer" if answer_images else None,
                        document_id=document.id if document else None,
                        document_name=document.filename if document else None,
                    ),
                )
                saved_conversation = await _save_conversation_with_summary(
                    db,
                    conversation,
                    refresh_summary=True,
                )
                _log_chat_response(mode, provider, model, full_response)
                yield _sse_event(
                    _final_payload(
                        full_response,
                        saved_conversation,
                        prompt_images=prompt_images,
                        answer_images=answer_images,
                    )
                )
            except Exception as exc:
                yield _sse_event(_final_payload(fallback_message, conversation, interrupted=True))

        return StreamingResponse(generate(), media_type="text/event-stream")

    if mode == "image":
        images = await _generate_images_for_prompt(message_text)
        _append_message(
            db,
            conversation,
            "assistant",
            "Here are your images.",
            meta={"mode": mode, "images": images},
        )
        conversation = await _save_conversation_with_summary(
            db,
            conversation,
            refresh_summary=True,
        )
        _log_chat_response(mode, provider, model, "Here are your images.")
        return _payload("Here are your images.", conversation, images=images)

    answer_sources: List[dict] = []
    if mode == "documents":
        response_text, answer_sources = await _best_effort_answer_bundle(
            history,
            message_text,
            mode,
            provider,
            model,
            doc_context=doc_context,
            max_tokens=response_max_tokens,
        )
    else:
        response_text = await _best_effort_answer(
            history,
            message_text,
            mode,
            provider,
            model,
            doc_context=doc_context,
            max_tokens=response_max_tokens,
        )

    prompt_images = await _await_image_task(prompt_image_task)
    answer_images = []
    if response_text and generate_answer_image and mode != "image" and response_text != FALLBACK_MESSAGE:
        answer_images = await _generate_images_best_effort(
            _build_answer_image_prompt(message_text, response_text)
        )
    _apply_images_to_message(
        user_message,
        images=prompt_images,
        generate_prompt_image=generate_prompt_image,
        generate_answer_image=generate_answer_image,
        document_id=document.id if document else None,
        document_name=document.filename if document else None,
    )
    _append_message(
        db,
        conversation,
        "assistant",
        response_text,
        meta=_merge_message_meta(
            {"mode": mode},
            images=answer_images,
            image_origin="answer" if answer_images else None,
            document_id=document.id if document else None,
            document_name=document.filename if document else None,
            sources=answer_sources,
        ),
    )
    conversation = await _save_conversation_with_summary(
        db,
        conversation,
        refresh_summary=True,
    )
    _log_chat_response(mode, provider, model, response_text)
    return _payload(
        response_text,
        conversation,
        prompt_images=prompt_images,
        answer_images=answer_images,
        sources=answer_sources,
    )


@router.post("/regenerate")
async def regenerate(
    http_request: Request,
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

    last_user_message = user_messages[-1]
    last_assistant_message = next(
        (message for message in reversed(message_records) if message.role == "assistant"),
        None,
    )
    last_user_message_content = _normalize_user_message(last_user_message.content or "")
    mode = _resolve_effective_mode(request.mode, last_user_message_content)
    if not last_user_message_content:
        raise HTTPException(status_code=400, detail="Last user message is empty")
    last_user_message_meta = getattr(last_user_message, "meta", None)
    last_assistant_meta = getattr(last_assistant_message, "meta", None) if last_assistant_message else None
    previous_answer = _normalize_regenerate_answer(
        request.previous_answer or (last_assistant_message.content if last_assistant_message else "")
    )
    regenerate_instruction = _build_regenerate_instruction(previous_answer)
    generate_answer_image = _resolve_answer_image_request(
        request.generate_answer_image,
        last_user_message_meta,
        last_user_message_content,
    ) and mode != "image"

    await enforce_chat_rate_limit(http_request, current_user)
    image_generation_cost = _chat_image_generation_cost(
        mode,
        generate_answer_image=generate_answer_image,
    )
    if image_generation_cost:
        await enforce_image_rate_limit(
            http_request,
            current_user,
            cost=image_generation_cost,
        )

    if message_records and message_records[-1].role == "assistant":
        db.delete(message_records[-1])
        conversation = _save_conversation(db, conversation)

    instant = instant_reply(last_user_message_content)
    if instant:
        prompt_images = _message_images(last_user_message)
        answer_images = []
        if generate_answer_image and mode != "image":
            answer_images = await _generate_images_best_effort(
                _build_answer_image_prompt(last_user_message_content, instant)
            )
        _append_message(
            db,
            conversation,
            "assistant",
            instant,
            meta=_merge_message_meta(
                {"mode": mode},
                images=answer_images,
                image_origin="answer" if answer_images else None,
            ),
        )
        conversation = await _save_conversation_with_summary(
            db,
            conversation,
            refresh_summary=True,
        )
        _log_chat_response(mode, request.provider, request.model, instant)
        payload = _payload(
            instant,
            conversation,
            prompt_images=prompt_images,
            answer_images=answer_images,
        )
        if request.stream:
            async def generate_instant():
                yield _sse_event(
                    _final_payload(
                        instant,
                        conversation,
                        prompt_images=prompt_images,
                        answer_images=answer_images,
                    )
                )

            return StreamingResponse(generate_instant(), media_type="text/event-stream")
        return payload

    provider, model = _resolve_provider_and_model(mode, request.provider, request.model)
    force_search = mode == "search"
    response_max_tokens = _response_max_tokens(last_user_message_content, mode)
    _log_chat_request(mode, provider, model, last_user_message_content, conversation.id)

    if provider_key in PROVIDERS and mode not in {"documents", "image"}:
        history = _conversation_history(db, conversation, drop_last=(mode not in {"documents", "image"}))
        enhanced_message = last_user_message_content
        answer_sources: List[dict] = []
        if mode not in {"documents", "image"}:
            enhanced_message, answer_sources = await _maybe_enhance_temporal_message_with_sources(
                last_user_message_content,
                force_search=force_search,
            )
        provider_messages = _build_ai_messages(
            history,
            enhanced_message,
            mode,
            extra_instruction=regenerate_instruction,
            instruction_message=last_user_message_content,
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
                    async for chunk in stream_response(
                        provider_key,
                        request.model or "",
                        provider_messages,
                        max_tokens=response_max_tokens,
                    ):
                        full_response += chunk
                        yield _sse_event({"type": "delta", "content": chunk})

                    full_response = full_response.strip()
                    if not full_response:
                        raise RuntimeError("Provider returned an empty response")
                    full_response = await _cross_check_answer_if_needed(
                        last_user_message_content,
                        enhanced_message,
                        full_response,
                        provider=None,
                        model=request.model,
                        max_tokens=response_max_tokens,
                        compatible_provider=provider_key,
                    )
                    full_response, rescued_sources = await _rescue_stale_compatible_provider_answer_bundle(
                        history,
                        last_user_message_content,
                        full_response,
                        mode,
                        response_max_tokens,
                        extra_instruction=regenerate_instruction,
                    )
                    final_sources = rescued_sources or answer_sources
                    prompt_images = _message_images(last_user_message)
                    answer_images = []
                    if generate_answer_image:
                        answer_images = await _generate_images_best_effort(
                            _build_answer_image_prompt(last_user_message_content, full_response)
                        )
                    _append_message(
                        db,
                        conversation,
                        "assistant",
                        full_response,
                        meta=_merge_message_meta(
                            {"mode": mode},
                            images=answer_images,
                            image_origin="answer" if answer_images else None,
                            sources=final_sources,
                        ),
                    )
                    saved_conversation = await _save_conversation_with_summary(
                        db,
                        conversation,
                        refresh_summary=True,
                    )
                    _log_chat_response(mode, provider_key, request.model, full_response)
                    yield _sse_event(
                        _final_payload(
                            full_response,
                            saved_conversation,
                            prompt_images=prompt_images,
                            answer_images=answer_images,
                            sources=final_sources,
                        )
                    )
                except Exception as exc:
                    yield _sse_event(_final_payload(fallback_message, conversation, interrupted=True))

            return StreamingResponse(generate_provider_stream(), media_type="text/event-stream")

        if not request.model:
            return _payload(SETUP_RETRY_MESSAGE, conversation)

        try:
            answer = await generate_response(
                provider_key,
                request.model,
                provider_messages,
                max_tokens=response_max_tokens,
            )
            text = (answer.get("response", "") if isinstance(answer, dict) else str(answer)).strip()
            text = await _cross_check_answer_if_needed(
                last_user_message_content,
                enhanced_message,
                text,
                provider=None,
                model=request.model,
                max_tokens=response_max_tokens,
                compatible_provider=provider_key,
            )
            text, rescued_sources = await _rescue_stale_compatible_provider_answer_bundle(
                history,
                last_user_message_content,
                text,
                mode,
                response_max_tokens,
                extra_instruction=regenerate_instruction,
            )
            final_sources = rescued_sources or answer_sources
        except Exception as exc:
            logger.warning(
                "Compatible provider regenerate failed provider=%s model=%s error=%s",
                provider_key,
                request.model,
                exc,
            )
            text, final_sources = await _best_effort_answer_bundle(
                history,
                last_user_message_content,
                mode,
                None,
                None,
                extra_instruction=regenerate_instruction,
                force_search=force_search,
            )
        text = _resolve_regenerated_text(text, previous_answer)

        prompt_images = _message_images(last_user_message)
        answer_images = []
        if text and generate_answer_image and text != FALLBACK_MESSAGE:
            answer_images = await _generate_images_best_effort(
                _build_answer_image_prompt(last_user_message_content, text)
            )
        _append_message(
            db,
            conversation,
            "assistant",
            text or fallback_message,
            meta=_merge_message_meta(
                {"mode": mode},
                images=answer_images,
                image_origin="answer" if answer_images else None,
                sources=final_sources,
            ),
        )
        conversation = await _save_conversation_with_summary(
            db,
            conversation,
            refresh_summary=True,
        )
        if text:
            _log_chat_response(mode, provider_key, request.model, text)
        return _payload(
            text or fallback_message,
            conversation,
            prompt_images=prompt_images,
            answer_images=answer_images,
            sources=final_sources,
        )

    if mode not in {"documents", "image"}:
        history = _conversation_history(db, conversation, drop_last=True)
        answer, answer_sources = await _best_effort_answer_bundle(
            history,
            last_user_message_content,
            mode,
            provider,
            model,
            extra_instruction=regenerate_instruction,
            force_search=force_search,
        )
        answer = _resolve_regenerated_text(answer, previous_answer)

        prompt_images = _message_images(last_user_message)
        answer_images = []
        if answer and generate_answer_image and answer != FALLBACK_MESSAGE:
            answer_images = await _generate_images_best_effort(
                _build_answer_image_prompt(last_user_message_content, answer)
            )
        _append_message(
            db,
            conversation,
            "assistant",
            answer,
            meta=_merge_message_meta(
                {"mode": mode},
                images=answer_images,
                image_origin="answer" if answer_images else None,
                sources=answer_sources,
            ),
        )
        conversation = await _save_conversation_with_summary(
            db,
            conversation,
            refresh_summary=True,
        )
        _log_chat_response(mode, provider, model, answer)
        payload = _payload(
            answer,
            conversation,
            prompt_images=prompt_images,
            answer_images=answer_images,
            sources=answer_sources,
        )

        if request.stream:
            async def generate_fast():
                yield _sse_event(
                    _final_payload(
                        answer,
                        conversation,
                        prompt_images=prompt_images,
                        answer_images=answer_images,
                        sources=answer_sources,
                    )
                )

            return StreamingResponse(generate_fast(), media_type="text/event-stream")
        return payload

    history = _conversation_history(db, conversation)
    doc_context = None
    document = None
    if mode == "documents":
        resolved_document_id = _resolve_document_id(
            request.document_id,
            last_user_message_meta,
            last_assistant_meta,
        )
        if resolved_document_id is None:
            payload = _payload("Please upload a document first.", conversation)
            if request.stream:
                async def generate_missing_doc():
                    yield _sse_event(_final_payload("Please upload a document first.", conversation))

                return StreamingResponse(generate_missing_doc(), media_type="text/event-stream")
            return payload

        document = db.query(Document).filter(
            Document.id == resolved_document_id,
            Document.user_id == current_user.id,
        ).first()

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        if not document.is_processed:
            raise HTTPException(status_code=400, detail="Document is still being processed")

        await vector_service.ensure_document(document.text_content or "", document.id)
        doc_context = await _resolve_document_context(last_user_message_content, document)

    response_max_tokens = _response_max_tokens(last_user_message_content, mode, doc_context)
    ai_messages = build_messages(history, mode)
    ai_messages.insert(1, {"role": "system", "content": regenerate_instruction})
    if doc_context:
        ai_messages.insert(2, {"role": "system", "content": f"Document context:\n{doc_context}"})

    if request.stream:
        async def generate():
            try:
                if mode == "image":
                    yield _sse_event({"type": "delta", "content": "Generating image..."})
                    images = await _generate_images_for_prompt(last_user_message_content)
                    _append_message(
                        db,
                        conversation,
                        "assistant",
                        "Here are your images.",
                        meta={"mode": mode, "images": images},
                    )
                    saved_conversation = await _save_conversation_with_summary(
                        db,
                        conversation,
                        refresh_summary=True,
                    )
                    _log_chat_response(mode, provider, model, "Here are your images.")
                    yield _sse_event(_final_payload("Here are your images.", saved_conversation, images=images))
                    return

                if mode == "documents":
                    full_response, answer_sources = await _best_effort_answer_bundle(
                        history,
                        last_user_message_content,
                        mode,
                        provider,
                        model,
                        doc_context=doc_context,
                        extra_instruction=regenerate_instruction,
                        max_tokens=response_max_tokens,
                    )
                    full_response = _resolve_regenerated_text(full_response, previous_answer)
                    prompt_images = _message_images(last_user_message)
                    answer_images = []
                    if generate_answer_image and full_response != FALLBACK_MESSAGE:
                        answer_images = await _generate_images_best_effort(
                            _build_answer_image_prompt(last_user_message_content, full_response)
                        )
                    _append_message(
                        db,
                        conversation,
                        "assistant",
                        full_response,
                        meta=_merge_message_meta(
                            {"mode": mode},
                            images=answer_images,
                            image_origin="answer" if answer_images else None,
                            document_id=document.id if document else None,
                            document_name=document.filename if document else None,
                            sources=answer_sources,
                        ),
                    )
                    saved_conversation = await _save_conversation_with_summary(
                        db,
                        conversation,
                        refresh_summary=True,
                    )
                    _log_chat_response(mode, provider, model, full_response)
                    yield _sse_event(
                        _final_payload(
                            full_response,
                            saved_conversation,
                            prompt_images=prompt_images,
                            answer_images=answer_images,
                            sources=answer_sources,
                        )
                    )
                    return

                full_response = ""
                async for chunk in ai_service.chat_stream(
                    ai_messages,
                    provider=provider,
                    model=model,
                    max_tokens=response_max_tokens,
                    use_case=infer_use_case(mode, last_user_message_content),
                ):
                    full_response += chunk
                    yield _sse_event({"type": "delta", "content": chunk})

                full_response = full_response.strip()
                if not full_response:
                    raise RuntimeError("AI provider returned an empty response")
                prompt_images = _message_images(last_user_message)
                answer_images = []
                if generate_answer_image and mode != "image":
                    answer_images = await _generate_images_best_effort(
                        _build_answer_image_prompt(last_user_message_content, full_response)
                    )
                    _append_message(
                        db,
                        conversation,
                        "assistant",
                        full_response,
                        meta=_merge_message_meta(
                            {"mode": mode},
                            images=answer_images,
                            image_origin="answer" if answer_images else None,
                            document_id=document.id if document else None,
                            document_name=document.filename if document else None,
                        ),
                    )
                saved_conversation = await _save_conversation_with_summary(
                    db,
                    conversation,
                    refresh_summary=True,
                )
                _log_chat_response(mode, provider, model, full_response)
                yield _sse_event(
                    _final_payload(
                        full_response,
                        saved_conversation,
                        prompt_images=prompt_images,
                        answer_images=answer_images,
                    )
                )
            except Exception as exc:
                yield _sse_event(_final_payload(fallback_message, conversation, interrupted=True))

        return StreamingResponse(generate(), media_type="text/event-stream")

    if mode == "image":
        images = await _generate_images_for_prompt(last_user_message_content)
        _append_message(
            db,
            conversation,
            "assistant",
            "Here are your images.",
            meta={"mode": mode, "images": images},
        )
        conversation = await _save_conversation_with_summary(
            db,
            conversation,
            refresh_summary=True,
        )
        _log_chat_response(mode, provider, model, "Here are your images.")
        return _payload("Here are your images.", conversation, images=images)

    answer_sources: List[dict] = []
    if mode == "documents":
        response_text, answer_sources = await _best_effort_answer_bundle(
            history,
            last_user_message_content,
            mode,
            provider,
            model,
            doc_context=doc_context,
            extra_instruction=regenerate_instruction,
            max_tokens=response_max_tokens,
        )
    else:
        response_text = await _best_effort_answer(
            history,
            last_user_message_content,
            mode,
            provider,
            model,
            doc_context=doc_context,
            extra_instruction=regenerate_instruction,
            max_tokens=response_max_tokens,
        )
    response_text = _resolve_regenerated_text(response_text, previous_answer)
    prompt_images = _message_images(last_user_message)
    answer_images = []
    if response_text and generate_answer_image and mode != "image" and response_text != FALLBACK_MESSAGE:
        answer_images = await _generate_images_best_effort(
            _build_answer_image_prompt(last_user_message_content, response_text)
        )
    _append_message(
        db,
        conversation,
        "assistant",
        response_text,
        meta=_merge_message_meta(
            {"mode": mode},
            images=answer_images,
            image_origin="answer" if answer_images else None,
            document_id=document.id if document else None,
            document_name=document.filename if document else None,
            sources=answer_sources,
        ),
    )
    conversation = await _save_conversation_with_summary(
        db,
        conversation,
        refresh_summary=True,
    )
    _log_chat_response(mode, provider, model, response_text)
    return _payload(
        response_text,
        conversation,
        prompt_images=prompt_images,
        answer_images=answer_images,
        sources=answer_sources,
    )


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
            "model": conv.model,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else (conv.created_at.isoformat() if conv.created_at else None),
            "preview": _conversation_preview_text(db, conv),
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
        "preview": _conversation_preview_text(db, conversation),
        "messages": serialized_messages,
    }


@router.put("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    request: ConversationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a conversation title."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    next_title = " ".join(str(request.title or "").split()).strip()
    if not next_title:
        raise HTTPException(status_code=400, detail="Conversation title cannot be empty")

    if len(next_title) > 120:
        raise HTTPException(status_code=400, detail="Conversation title must be 120 characters or fewer")

    conversation.title = next_title
    conversation = _save_conversation(db, conversation)

    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
        "preview": _conversation_preview_text(db, conversation),
        "message": "Conversation updated successfully",
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
