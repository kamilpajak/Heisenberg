"""Configuration settings for Heisenberg backend."""

from __future__ import annotations

from functools import lru_cache

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

    # Logging
    log_level: str = "INFO"
    log_json_format: bool = True

    # Retry
    retry_max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0

    # Rate Limiting
    rate_limit_per_minute: int = 60

    # Budget Alerts
    budget_alert_threshold_usd: float | None = None

    # Webhook
    webhook_url: str | None = None

    # LLM Configuration
    llm_primary_provider: str = "google"
    llm_fallback_provider: str | None = None

    # External Services
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None

    # Server
    host: str = "0.0.0.0"  # noqa: S104 - intentional for Docker
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    # pydantic-settings loads required fields from env vars at runtime
    return Settings()  # type: ignore[call-arg]
