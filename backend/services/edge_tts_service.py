"""Edge TTS adapter — free Microsoft neural voices for Kairo

Implements the LiveKit TTS interface so it can be used with AgentSession.
"""

import edge_tts
import io
import asyncio
import logging
from config import get_settings

logger = logging.getLogger("kairo.tts")

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


try:
    from livekit.agents import tts as lk_tts
    import numpy as np

    class EdgeTTSService(lk_tts.TTS):
        """Edge TTS as a LiveKit TTS plugin."""

        def __init__(self, language: str = "en", gender: str = "female"):
            super().__init__(
                capabilities=lk_tts.TTSCapabilities(streaming=False),
                sample_rate=24000,
                num_channels=1,
            )
            self.current_language = language
            self.current_gender = gender

        @property
        def voice(self) -> str:
            lang_voices = VOICES.get(self.current_language, VOICES["en"])
            return lang_voices.get(self.current_gender, lang_voices["female"])

        def switch_language(self, language: str):
            if language in VOICES:
                self.current_language = language

        def synthesize(self, text: str, *, conn_options=None) -> "lk_tts.ChunkedStream":
            return EdgeTTSChunkedStream(self, text, conn_options=conn_options)

    class EdgeTTSChunkedStream(lk_tts.ChunkedStream):
        """Non-streaming chunked synthesis using Edge TTS."""

        def __init__(self, tts_service: EdgeTTSService, text: str, *, conn_options=None):
            super().__init__(tts=tts_service, input_text=text, conn_options=conn_options or lk_tts.APIConnectOptions())
            self._tts_service = tts_service
            self._text = text

        async def _run(self, output):
            """Generate audio frames from Edge TTS. `output` is an AudioEmitter."""
            from livekit import rtc
            import uuid

            try:
                communicate = edge_tts.Communicate(self._text, self._tts_service.voice)
                audio_buffer = io.BytesIO()

                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_buffer.write(chunk["data"])

                audio_data = audio_buffer.getvalue()
                if not audio_data:
                    return

                # Edge TTS returns MP3 — decode to raw PCM via ffmpeg
                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-i", "pipe:0",
                    "-f", "s16le", "-ar", "24000", "-ac", "1",
                    "pipe:1",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                pcm_data, stderr = await proc.communicate(audio_data)
                if proc.returncode != 0:
                    logger.warning(f"ffmpeg error: {stderr.decode()[:200]}")
                    return

                if len(pcm_data) == 0:
                    return

                # Initialize emitter with raw PCM format
                request_id = str(uuid.uuid4())
                output.initialize(
                    request_id=request_id,
                    sample_rate=24000,
                    num_channels=1,
                    mime_type="audio/pcm",
                    stream=False,
                )

                # Push raw PCM bytes directly (emitter handles framing for non-stream)
                output.push(pcm_data)

            except FileNotFoundError:
                logger.error("ffmpeg not found — required for Edge TTS audio decoding")
            except Exception as e:
                logger.error(f"Edge TTS synthesis error: {e}")

except ImportError:
    # Fallback if livekit.agents not installed
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
