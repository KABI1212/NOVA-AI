from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import AsyncOpenAI
from models.user import User
from config.settings import settings
from utils.dependencies import get_current_user
import base64
import io

router = APIRouter(tags=["Voice"])


def _openai_client() -> AsyncOpenAI:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing OPENAI_API_KEY")
    return AsyncOpenAI(api_key=api_key)


async def _transcribe_bytes(audio_bytes: bytes, filename: str) -> str:
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file.")
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Audio too large. Max 25MB.")

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename or "recording.webm"

    client = _openai_client()
    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="text",
        language="en",
    )
    if isinstance(transcript, str):
        return transcript.strip()
    return getattr(transcript, "text", "").strip()


async def _tts_bytes(text: str, voice: str, speed: float, model: str) -> bytes:
    client = _openai_client()
    response = await client.audio.speech.create(
        model=model,
        voice=voice,
        input=text,
        speed=speed,
        response_format="mp3",
    )
    audio_data = getattr(response, "content", None)
    return audio_data if audio_data is not None else response


class VoiceOutputRequest(BaseModel):
    text: str


class VoiceSpeakRequest(BaseModel):
    text: str
    voice: str = "nova"
    speed: float = 1.0
    model: str = "tts-1"


@router.post("/api/voice/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        audio_bytes = await file.read()
        text = await _transcribe_bytes(audio_bytes, file.filename or "recording.webm")
        return {"transcript": text}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(exc)}")


@router.post("/api/voice/speak")
async def text_to_speech(
    payload: VoiceSpeakRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        text = (payload.text or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="No text provided.")
        if len(text) > 4096:
            text = text[:4096]

        voice = payload.voice or "nova"
        speed = payload.speed if payload.speed else 1.0
        speed = max(0.25, min(4.0, speed))
        model = payload.model or "tts-1"

        audio_data = await _tts_bytes(text, voice, speed, model)
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(exc)}")


# Backward compatible endpoints
@router.post("/voice-input")
async def voice_input(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        content = await audio.read()
        text = await _transcribe_bytes(content, audio.filename or "recording.webm")
        return {"text": text}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(exc)}")


@router.post("/voice-output")
async def voice_output(
    request: VoiceOutputRequest,
    current_user: User = Depends(get_current_user)
):
    if not request.text:
        raise HTTPException(status_code=400, detail="No text provided.")
    audio_data = await _tts_bytes(request.text, "nova", 1.0, "tts-1")
    audio_b64 = base64.b64encode(audio_data).decode("utf-8")
    return {"audio": audio_b64}
