from typing import List, Dict, Tuple
from config.settings import settings
from prompts import get_mode_prompt


def select_model(mode: str) -> str:
    """Select model based on mode."""
    key = (mode or "chat").lower()
    if key == "code":
        return settings.OPENAI_CODE_MODEL
    if key in {"deep", "safe", "knowledge", "learning", "documents"}:
        return settings.OPENAI_EXPLAIN_MODEL
    return settings.OPENAI_CHAT_MODEL


def build_messages(history: List[Dict[str, str]], mode: str) -> List[Dict[str, str]]:
    """Inject system prompt for the selected mode."""
    system_prompt = get_mode_prompt(mode)
    return [{"role": "system", "content": system_prompt}, *history]


def response_envelope(
    message: str,
    images: List[str] = None,
    code_blocks: List[str] = None,
    audio: str = None,
    references: List[str] = None
) -> Dict:
    return {
        "message": message,
        "images": images or [],
        "code_blocks": code_blocks or [],
        "audio": audio,
        "references": references or []
    }
