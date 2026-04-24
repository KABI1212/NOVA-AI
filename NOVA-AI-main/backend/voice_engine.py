from typing import Optional


async def speech_to_text(_: bytes) -> str:
    """Placeholder for Whisper/ASR integration."""
    raise NotImplementedError("Speech-to-text is handled on the client for now.")


async def text_to_speech(_: str) -> Optional[str]:
    """Placeholder for TTS integration. Return an audio URL/base64 string if implemented."""
    return None
