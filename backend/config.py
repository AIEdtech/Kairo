"""Kairo configuration — loads from .env"""

from pydantic_settings import BaseSettings
from functools import lru_cache


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

    # Skyfire
    skyfire_api_key: str = ""
    skyfire_wallet_id: str = ""

    # LiveKit
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_url: str = ""

    # Edge TTS
    edge_tts_voice_en: str = "en-US-AriaNeural"
    edge_tts_voice_hi: str = "hi-IN-SwaraNeural"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
