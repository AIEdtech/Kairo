"""Text-to-Speech routes — generates audio from text using Edge TTS + LiveKit voice token"""

from fastapi import APIRouter, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from config import get_settings
from services.auth import get_current_user_id
import io
import json
import time
import logging

router = APIRouter(prefix="/api", tags=["tts"])
settings = get_settings()
logger = logging.getLogger("kairo.tts")


# ── LiveKit Voice Token ──

class VoiceTokenRequest(BaseModel):
    mode: str = "BRIEFING"
    language: str = "Auto"


@router.post("/voice/token")
async def get_voice_token(
    body: VoiceTokenRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Generate a LiveKit access token for the voice interface."""
    if not settings.livekit_api_key or not settings.livekit_api_secret or not settings.livekit_url:
        return {"error": "LiveKit not configured. Set LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and LIVEKIT_URL in .env"}

    from livekit.api import AccessToken, VideoGrants

    # Generate an internal JWT for the voice agent to call backend APIs as this user
    from services.auth import create_access_token
    internal_token = create_access_token(user_id, email="")

    room_name = f"kairo-voice-{user_id}-{int(time.time())}"

    token = (
        AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(f"user-{user_id}")
        .with_name("Kairo User")
        .with_grants(VideoGrants(
            room_join=True,
            room=room_name,
        ))
        .with_metadata(json.dumps({"user_id": user_id, "mode": body.mode, "language": body.language, "api_token": internal_token}))
    )

    return {
        "token": token.to_jwt(),
        "url": settings.livekit_url,
        "room_name": room_name,
    }


# ── Edge TTS ──


@router.get("/tts/speak")
async def speak(
    text: str = Query(..., description="Text to convert to speech"),
    lang: str = Query("en", description="Language code: en or hi"),
):
    """Generate speech audio from text using Edge TTS."""
    voice = settings.edge_tts_voice_hi if lang == "hi" else settings.edge_tts_voice_en

    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        audio_buffer = io.BytesIO()

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        audio_buffer.seek(0)
        return StreamingResponse(
            audio_buffer,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=kairo_speech.mp3"},
        )
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return {"error": str(e), "fallback": "Use browser speech synthesis"}
