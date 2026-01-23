"""Tests for backend database configuration - TDD for Phase 4."""



class TestDatabaseConfig:
    """Test suite for database configuration."""

    def test_settings_class_exists(self):
        """Settings class should be importable."""
        from heisenberg.backend.config import Settings

        assert Settings is not None

    def test_settings_has_database_url(self):
        """Settings should have database_url field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert settings.database_url == "postgresql://test:test@localhost/test"

    def test_settings_has_secret_key(self):
        """Settings should have secret_key for API key hashing."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="my-secret-key",
        )
        assert settings.secret_key == "my-secret-key"

    def test_settings_has_anthropic_api_key(self):
        """Settings should optionally have anthropic_api_key."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
            anthropic_api_key="sk-ant-test",
        )
        assert settings.anthropic_api_key == "sk-ant-test"

    def test_settings_has_defaults(self):
        """Settings should have sensible defaults."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert settings.api_v1_prefix == "/api/v1"
        assert settings.debug is False


class TestDatabaseSession:
    """Test suite for database session management."""

    def test_get_db_function_exists(self):
        """get_db dependency should be importable."""
        from heisenberg.backend.database import get_db

        assert get_db is not None

    def test_engine_creator_exists(self):
        """create_engine function should be importable."""
        from heisenberg.backend.database import create_async_engine

        assert create_async_engine is not None

    def test_session_maker_exists(self):
        """AsyncSessionLocal should be available."""
        from heisenberg.backend.database import get_session_maker

        assert get_session_maker is not None
