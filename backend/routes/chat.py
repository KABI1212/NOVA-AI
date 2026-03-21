import asyncio
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
from config.database import get_db, get_db_optional
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
from services.search_service import fetch_page_content, format_results_for_ai, is_temporal_query, search_web, search_web_images
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
    generate_prompt_image: Optional[bool] = None
    generate_answer_image: Optional[bool] = None
    stream: bool = True

    model_config = ConfigDict(extra="ignore")


class RegenerateRequest(BaseModel):
    conversation_id: str
    mode: str = "chat"
    provider: Optional[str] = None
    model: Optional[str] = None
    document_id: Optional[int] = None
    generate_answer_image: Optional[bool] = None
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
    prompt_images: Optional[List[str]] = None,
    answer_images: Optional[List[str]] = None,
) -> dict:
    resolved_answer_images = answer_images if answer_images is not None else images
    payload = {
        "message": message,
        "answer": message,
        "images": resolved_answer_images or [],
        "answer_images": resolved_answer_images or [],
        "prompt_images": prompt_images or [],
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
    interrupted: bool = False,
) -> dict:
    payload = _payload(
        message,
        conversation,
        images,
        prompt_images=prompt_images,
        answer_images=answer_images,
    ) | {"type": "final"}
    if interrupted:
        payload["error"] = "retry"
    return payload


def _normalize_image_prompt_text(text: str, limit: int = 2600) -> str:
    return " ".join((text or "").split())[:limit]


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


def _message_images(message) -> List[str]:
    meta = getattr(message, "meta", None)
    if not isinstance(meta, dict):
        return []
    images = meta.get("images")
    if not isinstance(images, list):
        return []
    return [str(image) for image in images if image]


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


def _build_answer_image_prompt(user_message: str, answer: str) -> str:
    cleaned_user = _normalize_image_prompt_text(user_message, 900)
    cleaned_answer = _normalize_image_prompt_text(answer, 2400)
    if not cleaned_answer:
        return ""
    diagram_type, layout_note, accuracy_note = _answer_visual_strategy(cleaned_user, cleaned_answer)
    topic = _diagram_topic_text(cleaned_user, cleaned_answer)
    specific_requirements = _specific_diagram_requirements(cleaned_user, cleaned_answer, diagram_type)
    return (
        f'Create a clean, minimal, textbook-style {diagram_type} explaining "{topic}".\n\n'
        "Diagram rules:\n"
        f"- Selected type: {diagram_type}\n"
        "- Use real components and real protocols only when they genuinely apply to the topic\n"
        "- Use proper data flow with arrows\n"
        "- Use logical sequence from left to right or top to bottom\n\n"
        "Style requirements:\n"
        "- White background\n"
        "- Flat 2D vector design (no 3D, no gradients, no shadows)\n"
        "- Use simple geometric shapes, thin lines, and sharp edges\n"
        "- Use a limited color palette (black, blue, grey)\n"
        "- Clearly labeled components with readable sans-serif font\n"
        "- Balanced spacing and alignment\n"
        "- Arrows to show flow or relationships\n"
        "- No decorative elements, no icons, no stock images, no UI cards\n"
        "- Professional academic look (like engineering or CS textbooks)\n\n"
        "Specific content requirements:\n"
        f"- {layout_note}\n"
        f"- {accuracy_note}\n"
        + "".join(f"- {line}\n" for line in specific_requirements)
        + "\nAccuracy requirements:\n"
        "- Base the structure, labels, and relationships on the assistant answer below.\n"
        "- If web grounding is provided, use it only to verify or refine the factual structure.\n"
        "- Do not invent unsupported components, steps, or relationships.\n\n"
        "Output:\n"
        "- High resolution\n"
        "- Centered layout\n"
        "- Diagram only, no extra text outside the diagram\n\n"
        f"User prompt: {cleaned_user}\n"
        f"Assistant answer: {cleaned_answer}"
    )[:3800]


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


async def _generate_images_best_effort(prompt: str) -> List[str]:
    cleaned_prompt = (prompt or "").strip()
    if not cleaned_prompt:
        return []
    grounded_prompt = cleaned_prompt
    if "Assistant answer:" in cleaned_prompt:
        grounded_prompt, web_images = await _ground_answer_image_prompt(cleaned_prompt)
        if web_images:
            return web_images
        return []
    try:
        return await ai_service.generate_image(grounded_prompt)
    except Exception as exc:
        logger.warning(
            "Image generation failed prompt=%s error=%s",
            _preview_text(grounded_prompt),
            exc,
        )
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


def _resolve_answer_image_request(requested: Optional[bool], meta: Optional[dict]) -> bool:
    if requested is not None:
        return bool(requested)
    if isinstance(meta, dict):
        return bool(meta.get("generate_answer_image"))
    return False


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
    return append_conversation_message(db, conversation, role, content, meta)


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
    db: Optional[Session] = Depends(get_db_optional),
):
    """Send a chat message and get AI response."""
    mode = (request.mode or "chat").lower()
    provider_key = (request.provider or "").strip().lower()
    fallback_message = FALLBACK_MESSAGE
    generate_prompt_image = bool(request.generate_prompt_image)
    generate_answer_image = bool(request.generate_answer_image)

    if not request.message or not request.message.strip():
        payload = response_envelope("Please enter a message.")
        payload["type"] = "final"
        if request.stream:
            async def generate_empty():
                yield _sse_event(payload)

            return StreamingResponse(generate_empty(), media_type="text/event-stream")
        return payload

    if current_user is None or db is None:
        history = get_history(limit=20)
        instant = instant_reply(request.message)
        if instant:
            prompt_images = []
            answer_images = []
            if generate_prompt_image and mode != "image":
                prompt_images = await _generate_images_best_effort(_build_prompt_image_prompt(request.message))
            if generate_answer_image and mode != "image":
                answer_images = await _generate_images_best_effort(
                    _build_answer_image_prompt(request.message, instant)
                )
            add_message("user", request.message)
            add_message("assistant", instant)
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

                prompt_image_task = _start_prompt_image_task(generate_prompt_image, request.message)

                async def generate_provider_stream():
                    full_response = ""
                    try:
                        async for chunk in stream_response(provider_key, request.model or "", public_messages):
                            full_response += chunk
                            yield _sse_event({"type": "delta", "content": chunk})
                        full_response = full_response.strip()
                        if not full_response:
                            raise RuntimeError("Provider returned an empty response")
                        prompt_images = await _await_image_task(prompt_image_task)
                        answer_images = []
                        if generate_answer_image:
                            answer_images = await _generate_images_best_effort(
                                _build_answer_image_prompt(request.message, full_response)
                            )
                        _log_chat_response(mode, provider_key, request.model, full_response)
                        yield _sse_event(
                            _final_payload(
                                full_response,
                                prompt_images=prompt_images,
                                answer_images=answer_images,
                            )
                        )
                    except Exception as exc:
                        yield _sse_event(_final_payload(fallback_message, interrupted=True))

                return StreamingResponse(generate_provider_stream(), media_type="text/event-stream")

            if not request.model:
                return _payload(SETUP_RETRY_MESSAGE)

            prompt_image_task = _start_prompt_image_task(generate_prompt_image, request.message)

            try:
                answer = await generate_response(provider_key, request.model, public_messages)
                text = (answer.get("response", "") if isinstance(answer, dict) else str(answer)).strip()
                prompt_images = await _await_image_task(prompt_image_task)
                answer_images = []
                if text and generate_answer_image:
                    answer_images = await _generate_images_best_effort(
                        _build_answer_image_prompt(request.message, text)
                    )
                if text:
                    _log_chat_response(mode, provider_key, request.model, text)
                return _payload(
                    text or fallback_message,
                    prompt_images=prompt_images,
                    answer_images=answer_images,
                )
            except Exception as exc:
                logger.warning("Compatible provider public chat failed provider=%s model=%s error=%s", provider_key, request.model, exc)
                answer = await _best_effort_answer(history, request.message, mode, None, None, force_search=force_search)
                prompt_images = await _await_image_task(prompt_image_task)
                answer_images = []
                if answer and generate_answer_image and answer != FALLBACK_MESSAGE:
                    answer_images = await _generate_images_best_effort(
                        _build_answer_image_prompt(request.message, answer)
                    )
                return _payload(
                    answer,
                    prompt_images=prompt_images,
                    answer_images=answer_images,
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
            prompt_image_task = _start_prompt_image_task(generate_prompt_image, request.message)
            add_message("user", request.message)
            answer = await _best_effort_answer(
                history,
                request.message,
                mode,
                provider,
                model,
                force_search=force_search,
            )
            prompt_images = await _await_image_task(prompt_image_task)
            answer_images = []
            if answer and generate_answer_image and answer != FALLBACK_MESSAGE:
                answer_images = await _generate_images_best_effort(
                    _build_answer_image_prompt(request.message, answer)
                )
            add_message("assistant", answer)
            _log_chat_response(mode, provider, model, answer)
            payload = _payload(
                answer,
                prompt_images=prompt_images,
                answer_images=answer_images,
            )
            if request.stream:
                async def generate_fast():
                    yield _sse_event(
                        _final_payload(
                            answer,
                            prompt_images=prompt_images,
                            answer_images=answer_images,
                        )
                    )

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
    user_message = _append_message(
        db,
        conversation,
        "user",
        request.message,
        meta=_image_preferences(generate_prompt_image, generate_answer_image),
    )
    conversation = _save_conversation(db, conversation)
    prompt_image_task = _start_prompt_image_task(generate_prompt_image and mode != "image", request.message)

    instant = instant_reply(request.message)
    if instant:
        prompt_images = await _await_image_task(prompt_image_task)
        answer_images = []
        if generate_answer_image and mode != "image":
            answer_images = await _generate_images_best_effort(
                _build_answer_image_prompt(request.message, instant)
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
        conversation = _save_conversation(db, conversation)
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
                    prompt_images = await _await_image_task(prompt_image_task)
                    answer_images = []
                    if generate_answer_image:
                        answer_images = await _generate_images_best_effort(
                            _build_answer_image_prompt(request.message, full_response)
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
                        ),
                    )
                    saved_conversation = _save_conversation(db, conversation)
                    _log_chat_response(mode, provider_key, request.model, full_response)
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

        prompt_images = await _await_image_task(prompt_image_task)
        answer_images = []
        if text and generate_answer_image and text != FALLBACK_MESSAGE:
            answer_images = await _generate_images_best_effort(
                _build_answer_image_prompt(request.message, text)
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
            ),
        )
        conversation = _save_conversation(db, conversation)
        if text:
            _log_chat_response(mode, provider_key, request.model, text)
        return _payload(
            text or fallback_message,
            conversation,
            prompt_images=prompt_images,
            answer_images=answer_images,
        )

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

        prompt_images = await _await_image_task(prompt_image_task)
        answer_images = []
        if answer and generate_answer_image and answer != FALLBACK_MESSAGE:
            answer_images = await _generate_images_best_effort(
                _build_answer_image_prompt(request.message, answer)
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
            ),
        )
        conversation = _save_conversation(db, conversation)
        _log_chat_response(mode, provider, model, answer)
        payload = _payload(
            answer,
            conversation,
            prompt_images=prompt_images,
            answer_images=answer_images,
        )

        if request.stream:
            async def generate_fast_auth():
                yield _sse_event(
                    _final_payload(
                        answer,
                        conversation,
                        prompt_images=prompt_images,
                        answer_images=answer_images,
                    )
                )

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
                prompt_images = await _await_image_task(prompt_image_task)
                answer_images = []
                if generate_answer_image and mode != "image":
                    answer_images = await _generate_images_best_effort(
                        _build_answer_image_prompt(request.message, full_response)
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
                    ),
                )
                saved_conversation = _save_conversation(db, conversation)
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

    prompt_images = await _await_image_task(prompt_image_task)
    answer_images = []
    if response_text and generate_answer_image and mode != "image" and response_text != FALLBACK_MESSAGE:
        answer_images = await _generate_images_best_effort(
            _build_answer_image_prompt(request.message, response_text)
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
        response_text,
        meta=_merge_message_meta(
            {"mode": mode},
            images=answer_images,
            image_origin="answer" if answer_images else None,
        ),
    )
    conversation = _save_conversation(db, conversation)
    _log_chat_response(mode, provider, model, response_text)
    return _payload(
        response_text,
        conversation,
        prompt_images=prompt_images,
        answer_images=answer_images,
    )


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

    last_user_message = user_messages[-1]
    last_user_message_content = (last_user_message.content or "").strip()
    if not last_user_message_content:
        raise HTTPException(status_code=400, detail="Last user message is empty")
    generate_answer_image = _resolve_answer_image_request(
        request.generate_answer_image,
        getattr(last_user_message, "meta", None),
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
        conversation = _save_conversation(db, conversation)
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
                        ),
                    )
                    saved_conversation = _save_conversation(db, conversation)
                    _log_chat_response(mode, provider_key, request.model, full_response)
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
            ),
        )
        conversation = _save_conversation(db, conversation)
        if text:
            _log_chat_response(mode, provider_key, request.model, text)
        return _payload(
            text or fallback_message,
            conversation,
            prompt_images=prompt_images,
            answer_images=answer_images,
        )

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
            ),
        )
        conversation = _save_conversation(db, conversation)
        _log_chat_response(mode, provider, model, answer)
        payload = _payload(
            answer,
            conversation,
            prompt_images=prompt_images,
            answer_images=answer_images,
        )

        if request.stream:
            async def generate_fast():
                yield _sse_event(
                    _final_payload(
                        answer,
                        conversation,
                        prompt_images=prompt_images,
                        answer_images=answer_images,
                    )
                )

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
                    ),
                )
                saved_conversation = _save_conversation(db, conversation)
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
        ),
    )
    conversation = _save_conversation(db, conversation)
    _log_chat_response(mode, provider, model, response_text)
    return _payload(
        response_text,
        conversation,
        prompt_images=prompt_images,
        answer_images=answer_images,
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
