"""Kairo configuration — loads from .env"""

from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Look for .env in backend/ first, then project root
_BACKEND_DIR = Path(__file__).resolve().parent
_ENV_FILE = _BACKEND_DIR / ".env"
if not _ENV_FILE.exists():
    _ENV_FILE = _BACKEND_DIR.parent / ".env"


class Settings(BaseSettings):
    # App
    app_name: str = "Kairo"
    app_env: str = "development"
    secret_key: str = "change-me"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 72
    cors_origins: str = "http://localhost:3000"

    # Database
    database_url: str = "sqlite:///./kairo.db"

    # LLM
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6-20250220"

    # Composio
    composio_api_key: str = ""

    # Snowflake
    snowflake_account: str = ""
    snowflake_user: str = ""
    snowflake_password: str = ""
    snowflake_database: str = "kairo"
    snowflake_schema: str = "public"
    snowflake_warehouse: str = "compute_wh"

    # Skyfire
    skyfire_api_key: str = ""  # backward compat alias for buyer key
    skyfire_wallet_id: str = ""
    skyfire_buyer_api_key: str = ""
    skyfire_seller_api_key: str = ""
    skyfire_seller_service_id: str = ""

    # LiveKit
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_url: str = ""

    # Deepgram (used for STT in voice agent)
    deepgram_api_key: str = ""

    # OpenAI (used for TTS in voice agent)
    openai_api_key: str = ""

    # Edge TTS
    edge_tts_voice_en: str = "en-US-AriaNeural"
    edge_tts_voice_hi: str = "hi-IN-SwaraNeural"

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
