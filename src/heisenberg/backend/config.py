"""Configuration settings for Heisenberg backend."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str

    # Security
    secret_key: str
    api_key_algorithm: str = "HS256"

    # API
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # External Services
    anthropic_api_key: str | None = None

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
