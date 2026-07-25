from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and the root .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    web_origin: str = "http://localhost:3000"
    database_url: str = (
        "postgresql+psycopg://living_rag:change-me-before-production@postgres:5432/living_rag"
    )

    embedding_provider: str = "mock"
    ollama_base_url: str = "http://host.docker.internal:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_timeout_seconds: float = 30.0
    embedding_api_base_url: str = ""
    embedding_api_key: str = ""

@lru_cache
def get_settings() -> Settings:
    return Settings()