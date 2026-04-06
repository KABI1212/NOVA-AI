from __future__ import annotations

import base64
import io

from fastapi import HTTPException
from openai import AsyncOpenAI

from config.settings import settings


_DEFAULT_TRANSCRIPTION_FILENAME = "recording.webm"
_DEFAULT_TRANSCRIPTION_LANGUAGE = "en"
_DEFAULT_TTS_MODEL = "tts-1"
_DEFAULT_TTS_VOICE = "nova"
_MAX_AUDIO_BYTES = 25 * 1024 * 1024
_MAX_TTS_CHARS = 4096


def _openai_client() -> AsyncOpenAI:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing OPENAI_API_KEY")
    return AsyncOpenAI(api_key=api_key)


def _normalize_tts_text(text: str, *, limit: int = _MAX_TTS_CHARS) -> str:
    normalized = " ".join(str(text or "").split()).strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="No text provided.")
    return normalized[:limit]


def _normalize_tts_speed(speed: float | None) -> float:
    if speed is None:
        return 1.0

    try:
        numeric_speed = float(speed)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid speech speed.") from exc

    return max(0.25, min(4.0, numeric_speed))


async def speech_to_text(
    audio_bytes: bytes,
    filename: str | None = None,
    *,
    language: str = _DEFAULT_TRANSCRIPTION_LANGUAGE,
) -> str:
    """Transcribe uploaded audio bytes with OpenAI audio transcription."""
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file.")
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="Audio too large. Max 25MB.")

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename or _DEFAULT_TRANSCRIPTION_FILENAME

    transcript = await _openai_client().audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="text",
        language=language,
    )
    if isinstance(transcript, str):
        return transcript.strip()
    return getattr(transcript, "text", "").strip()


async def text_to_speech_audio(
    text: str,
    *,
    voice: str = _DEFAULT_TTS_VOICE,
    speed: float | None = 1.0,
    model: str = _DEFAULT_TTS_MODEL,
) -> bytes:
    """Convert text to raw MP3 bytes using OpenAI TTS."""
    normalized_text = _normalize_tts_text(text)
    normalized_speed = _normalize_tts_speed(speed)

    response = await _openai_client().audio.speech.create(
        model=model or _DEFAULT_TTS_MODEL,
        voice=voice or _DEFAULT_TTS_VOICE,
        input=normalized_text,
        speed=normalized_speed,
        response_format="mp3",
    )
    audio_data = getattr(response, "content", None)

    if isinstance(audio_data, (bytes, bytearray)):
        return bytes(audio_data)
    if isinstance(response, (bytes, bytearray)):
        return bytes(response)
    if hasattr(response, "read"):
        streamed_audio = response.read()
        if isinstance(streamed_audio, (bytes, bytearray)):
            return bytes(streamed_audio)

    raise RuntimeError("OpenAI TTS did not return audio bytes.")


async def text_to_speech(
    text: str,
    *,
    voice: str = _DEFAULT_TTS_VOICE,
    speed: float | None = 1.0,
    model: str = _DEFAULT_TTS_MODEL,
) -> str:
    """Convert text to base64-encoded MP3 audio."""
    audio_data = await text_to_speech_audio(
        text,
        voice=voice,
        speed=speed,
        model=model,
    )
    return base64.b64encode(audio_data).decode("utf-8")
