"""Edge TTS adapter — free Microsoft neural voices for Kairo"""

import edge_tts
import io
import asyncio
from config import get_settings

settings = get_settings()

VOICES = {
    "en": {
        "female": "en-US-AriaNeural",
        "male": "en-US-GuyNeural",
    },
    "hi": {
        "female": "hi-IN-SwaraNeural",
        "male": "hi-IN-MadhurNeural",
    },
    "en-IN": {
        "female": "en-IN-NeerjaNeural",
        "male": "en-IN-PrabhatNeural",
    },
}


class EdgeTTSService:
    def __init__(self, language: str = "en", gender: str = "female"):
        self.current_language = language
        self.current_gender = gender

    @property
    def voice(self) -> str:
        lang_voices = VOICES.get(self.current_language, VOICES["en"])
        return lang_voices.get(self.current_gender, lang_voices["female"])

    def switch_language(self, language: str):
        if language in VOICES:
            self.current_language = language

    async def synthesize(self, text: str) -> bytes:
        communicate = edge_tts.Communicate(text, self.voice)
        audio = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.write(chunk["data"])
        return audio.getvalue()

    async def synthesize_to_file(self, text: str, filepath: str):
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(filepath)

    async def stream_audio(self, text: str):
        communicate = edge_tts.Communicate(text, self.voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]


# Singleton
_tts_service = None

def get_tts_service(language: str = "en", gender: str = "female") -> EdgeTTSService:
    global _tts_service
    if _tts_service is None:
        _tts_service = EdgeTTSService(language, gender)
    return _tts_service
