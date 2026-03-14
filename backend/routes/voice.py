from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from models.user import User
from utils.dependencies import get_current_user
from voice_engine import speech_to_text, text_to_speech

router = APIRouter(tags=["Voice"])


class VoiceOutputRequest(BaseModel):
    text: str


@router.post("/voice-input")
async def voice_input(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        content = await audio.read()
        text = await speech_to_text(content)
        return {"text": text}
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))


@router.post("/voice-output")
async def voice_output(
    request: VoiceOutputRequest,
    current_user: User = Depends(get_current_user)
):
    audio = await text_to_speech(request.text)
    return {"audio": audio}
