"""Tests for backend LLM settings and configuration.

Provider tests moved to: test_llm_providers.py
Router tests moved to: test_llm_router.py
"""

import pytest


class TestLLMSettings:
    """Test suite for LLM configuration settings."""

    def test_settings_has_primary_provider(self):
        """Settings should have llm_primary_provider field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "llm_primary_provider")
        assert settings.llm_primary_provider == "anthropic"  # default

    def test_settings_has_fallback_provider(self):
        """Settings should have llm_fallback_provider field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "llm_fallback_provider")
        assert settings.llm_fallback_provider is None  # default

    def test_settings_has_openai_api_key(self):
        """Settings should have openai_api_key field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "openai_api_key")
        assert settings.openai_api_key is None  # default

    def test_settings_allows_custom_primary_provider(self):
        """Settings should allow custom primary provider."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
            llm_primary_provider="openai",
        )
        assert settings.llm_primary_provider == "openai"

    def test_settings_allows_custom_fallback_provider(self):
        """Settings should allow custom fallback provider."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
            llm_fallback_provider="openai",
        )
        assert settings.llm_fallback_provider == "openai"


class TestSettingsCaching:
    """Test suite for settings caching with @lru_cache."""

    @pytest.fixture
    def settings_env(self, monkeypatch):
        """Set required environment variables for Settings."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-testing")
        yield
        from heisenberg.backend.config import get_settings

        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()

    def test_get_settings_returns_same_instance(self, settings_env):
        """get_settings() should return the same cached instance."""
        from heisenberg.backend.config import get_settings

        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_get_settings_has_cache_clear(self):
        """get_settings() should have cache_clear method from lru_cache."""
        from heisenberg.backend.config import get_settings

        assert hasattr(get_settings, "cache_clear")
        assert callable(get_settings.cache_clear)

    def test_get_settings_has_cache_info(self):
        """get_settings() should have cache_info method from lru_cache."""
        from heisenberg.backend.config import get_settings

        assert hasattr(get_settings, "cache_info")
        assert callable(get_settings.cache_info)

    def test_cache_clear_creates_new_instance(self, settings_env):
        """cache_clear() should allow creating a new Settings instance."""
        from heisenberg.backend.config import get_settings

        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()

        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()

        assert settings1 is not settings2
