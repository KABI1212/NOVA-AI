from __future__ import annotations

import asyncio
import base64

import pytest
from fastapi import HTTPException

import voice_engine


def test_openai_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(voice_engine.settings, "OPENAI_API_KEY", "")

    with pytest.raises(HTTPException) as exc_info:
        voice_engine._openai_client()

    assert exc_info.value.status_code == 400
    assert "OPENAI_API_KEY" in str(exc_info.value.detail)


def test_normalize_tts_text_rejects_empty_input() -> None:
    with pytest.raises(HTTPException) as exc_info:
        voice_engine._normalize_tts_text("   ")

    assert exc_info.value.status_code == 400
    assert "No text provided" in str(exc_info.value.detail)


def test_normalize_tts_speed_clamps_to_supported_range() -> None:
    assert voice_engine._normalize_tts_speed(None) == 1.0
    assert voice_engine._normalize_tts_speed(0.1) == 0.25
    assert voice_engine._normalize_tts_speed(9.0) == 4.0


def test_normalize_tts_speed_rejects_invalid_values() -> None:
    with pytest.raises(HTTPException) as exc_info:
        voice_engine._normalize_tts_speed("fast")

    assert exc_info.value.status_code == 400
    assert "Invalid speech speed" in str(exc_info.value.detail)


def test_speech_to_text_rejects_empty_audio() -> None:
    async def scenario() -> None:
        with pytest.raises(HTTPException) as exc_info:
            await voice_engine.speech_to_text(b"")

        assert exc_info.value.status_code == 400
        assert "Empty audio file" in str(exc_info.value.detail)

    asyncio.run(scenario())


def test_text_to_speech_returns_base64_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_text_to_speech_audio(
        text: str,
        *,
        voice: str = "nova",
        speed: float | None = 1.0,
        model: str = "tts-1",
    ) -> bytes:
        assert text == "Read this aloud"
        assert voice == "nova"
        assert speed == 1.0
        assert model == "tts-1"
        return b"mp3-bytes"

    monkeypatch.setattr(voice_engine, "text_to_speech_audio", fake_text_to_speech_audio)

    async def scenario() -> None:
        encoded_audio = await voice_engine.text_to_speech("Read this aloud")
        assert encoded_audio == base64.b64encode(b"mp3-bytes").decode("utf-8")

    asyncio.run(scenario())
