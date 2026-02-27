"""Text-to-Speech routes — generates audio from text using Edge TTS"""

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from config import get_settings
import io
import logging

router = APIRouter(prefix="/api/tts", tags=["tts"])
settings = get_settings()
logger = logging.getLogger("kairo.tts")


@router.get("/speak")
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
