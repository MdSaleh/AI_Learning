"""Application settings — loaded from environment variables or .env file."""
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── App ──────────────────────────────────────────────────────────────────
    app_name: str = "AI Chat API"
    environment: str = Field(default="development", alias="ENV")
    debug: bool = False
    port: int = 8000
    api_key: Optional[str] = None  # Optional auth

    # ─── LLM ──────────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "llama3.1:8b"
    default_temperature: float = 0.7
    default_max_tokens: int = 2048
    llm_timeout_seconds: int = 120

    # ─── Redis ────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"
    conversation_ttl_seconds: int = 3600  # 1 hour
    max_history_messages: int = 20

    # ─── Observability ────────────────────────────────────────────────────────
    otlp_endpoint: Optional[str] = None
    log_level: str = "INFO"

    # ─── Testing ──────────────────────────────────────────────────────────────
    mock_llm: bool = Field(default=False, alias="MOCK_LLM")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
