from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    groq_transcription_model: Optional[str] = None
    groq_llm_model: Optional[str] = None
    stockfish_path: Optional[str] = None
    frontend_origin: Optional[str] = None
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
