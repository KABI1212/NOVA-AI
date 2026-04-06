import io

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models.user import User
from utils.dependencies import get_current_user
from voice_engine import (
    speech_to_text as transcribe_audio_bytes,
    text_to_speech as synthesize_audio_base64,
    text_to_speech_audio,
)

router = APIRouter(tags=["Voice"])


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
        text = await transcribe_audio_bytes(audio_bytes, file.filename or "recording.webm")
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
        audio_data = await text_to_speech_audio(
            payload.text,
            voice=payload.voice,
            speed=payload.speed,
            model=payload.model,
        )
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
        text = await transcribe_audio_bytes(content, audio.filename or "recording.webm")
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
    try:
        audio_b64 = await synthesize_audio_base64(request.text)
        return {"audio": audio_b64}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(exc)}")
