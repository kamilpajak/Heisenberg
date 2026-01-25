"""Tests for backend database configuration - TDD for Phase 4."""

from unittest.mock import AsyncMock, MagicMock

import pytest


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
        assert not settings.debug


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


class TestCreateAsyncEngine:
    """Test suite for create_async_engine function."""

    def test_converts_postgresql_to_asyncpg(self):
        """Should convert postgresql:// to postgresql+asyncpg://."""
        from heisenberg.backend.database import create_async_engine

        engine = create_async_engine("postgresql://user:pass@localhost/db")
        assert "asyncpg" in str(engine.url)

    def test_preserves_asyncpg_url(self):
        """Should preserve already asyncpg URLs."""
        from heisenberg.backend.database import create_async_engine

        engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
        assert "asyncpg" in str(engine.url)

    def test_engine_has_pool_pre_ping(self):
        """Engine should have pool_pre_ping enabled."""
        from heisenberg.backend.database import create_async_engine

        engine = create_async_engine("postgresql://user:pass@localhost/db")
        assert engine.pool._pre_ping is True


class TestGetSessionMaker:
    """Test suite for get_session_maker function."""

    def test_returns_async_session_maker(self):
        """Should return an async_sessionmaker."""
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from heisenberg.backend.database import create_async_engine, get_session_maker

        engine = create_async_engine("postgresql://user:pass@localhost/db")
        session_maker = get_session_maker(engine)
        assert isinstance(session_maker, async_sessionmaker)

    def test_session_maker_config(self):
        """Session maker should have correct configuration."""
        from heisenberg.backend.database import create_async_engine, get_session_maker

        engine = create_async_engine("postgresql://user:pass@localhost/db")
        session_maker = get_session_maker(engine)
        # Check expire_on_commit is False
        assert session_maker.kw.get("expire_on_commit") is False


class TestInitDb:
    """Test suite for init_db function."""

    def test_init_db_returns_engine_and_session_maker(self):
        """init_db should return (engine, session_maker) tuple."""
        from heisenberg.backend.config import Settings
        from heisenberg.backend.database import init_db

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret",
        )
        engine, session_maker = init_db(settings)

        assert engine is not None
        assert session_maker is not None


class TestGetDb:
    """Test suite for get_db dependency."""

    @pytest.mark.asyncio
    async def test_get_db_raises_when_not_initialized(self):
        """get_db should raise RuntimeError when session_maker not in app.state."""
        from heisenberg.backend.database import get_db

        # Mock request without session_maker in app.state
        mock_request = MagicMock()
        mock_request.app.state = MagicMock(spec=[])  # No session_maker attribute

        with pytest.raises(RuntimeError, match="Database not initialized"):
            async for _ in get_db(mock_request):
                pass

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        """get_db should yield a session from request.app.state."""
        from heisenberg.backend.database import get_db

        # Mock session
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        # Mock session maker context manager
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        # Mock request with session_maker in app.state
        mock_request = MagicMock()
        mock_request.app.state.session_maker = mock_session_maker

        async for session in get_db(mock_request):
            assert session == mock_session

        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_db_rollback_on_exception(self):
        """get_db should rollback on exception."""
        from heisenberg.backend.database import get_db

        # Mock session that raises on commit
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock(side_effect=Exception("DB error"))
        mock_session.rollback = AsyncMock()

        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_request = MagicMock()
        mock_request.app.state.session_maker = mock_session_maker

        with pytest.raises(Exception, match="DB error"):
            async for _ in get_db(mock_request):
                pass

        mock_session.rollback.assert_called_once()
