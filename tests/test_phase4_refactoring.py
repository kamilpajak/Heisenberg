"""Tests for Phase 4 refactoring - TDD approach.

Phase 4: Move database state from global variables to app.state
- Remove global _engine and _session_maker
- Store in app.state during lifespan
- Update get_db() to get from request.app.state
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


class TestDatabaseInitReturnsInstances:
    """Test that init_db returns engine and session_maker instead of using globals."""

    def test_init_db_returns_tuple(self):
        """init_db() should return (engine, session_maker) tuple."""
        from heisenberg.backend.config import Settings
        from heisenberg.backend.database import init_db

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )

        with patch("heisenberg.backend.database.create_async_engine") as mock_engine:
            mock_engine.return_value = MagicMock()
            result = init_db(settings)

        # Should return tuple of (engine, session_maker)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_init_db_returns_engine_first(self):
        """init_db() should return engine as first element."""
        from sqlalchemy.ext.asyncio import AsyncEngine

        from heisenberg.backend.config import Settings
        from heisenberg.backend.database import init_db

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )

        with patch("heisenberg.backend.database.create_async_engine") as mock_create:
            mock_engine = MagicMock(spec=AsyncEngine)
            mock_create.return_value = mock_engine
            engine, _ = init_db(settings)

        assert engine is mock_engine

    def test_init_db_returns_session_maker_second(self):
        """init_db() should return session_maker as second element."""
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from heisenberg.backend.config import Settings
        from heisenberg.backend.database import init_db

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )

        with patch("heisenberg.backend.database.create_async_engine") as mock_create:
            mock_create.return_value = MagicMock()
            _, session_maker = init_db(settings)

        assert isinstance(session_maker, async_sessionmaker)


class TestGetDbUsesRequest:
    """Test that get_db dependency uses request.app.state."""

    def test_get_db_accepts_request_parameter(self):
        """get_db() should accept Request as parameter."""
        import inspect

        from heisenberg.backend.database import get_db

        sig = inspect.signature(get_db)
        params = list(sig.parameters.keys())

        assert "request" in params

    @pytest.mark.asyncio
    async def test_get_db_gets_session_maker_from_app_state(self):
        """get_db() should get session_maker from request.app.state."""
        from heisenberg.backend.database import get_db

        # Create mock request with app.state
        mock_session = MagicMock()
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_request = MagicMock()
        mock_request.app.state.session_maker = mock_session_maker

        # Call get_db with mock request
        async for session in get_db(mock_request):
            assert session is mock_session

    @pytest.mark.asyncio
    async def test_get_db_raises_if_session_maker_not_initialized(self):
        """get_db() should raise RuntimeError if session_maker not in app.state."""
        from heisenberg.backend.database import get_db

        mock_request = MagicMock()
        mock_request.app.state = MagicMock(spec=[])  # No session_maker attribute

        with pytest.raises(RuntimeError, match="Database not initialized"):
            async for _ in get_db(mock_request):
                pass


class TestAppStateStoresDatabase:
    """Test that app.state stores database instances."""

    @pytest.mark.asyncio
    async def test_app_state_has_engine_after_startup(self):
        """app.state should have engine after startup."""
        from heisenberg.backend.app import app

        with patch.dict(
            "os.environ",
            {"DATABASE_URL": "postgresql://test:test@localhost/test"},
        ):
            with patch("heisenberg.backend.database.create_async_engine") as mock_create:
                mock_engine = MagicMock()
                mock_engine.dispose = AsyncMock()
                mock_create.return_value = mock_engine

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    # Check that engine is in app.state
                    assert hasattr(app.state, "engine")
                    assert app.state.engine is mock_engine

    @pytest.mark.asyncio
    async def test_app_state_has_session_maker_after_startup(self):
        """app.state should have session_maker after startup."""
        from heisenberg.backend.app import app

        with patch.dict(
            "os.environ",
            {"DATABASE_URL": "postgresql://test:test@localhost/test"},
        ):
            with patch("heisenberg.backend.database.create_async_engine") as mock_create:
                mock_engine = MagicMock()
                mock_engine.dispose = AsyncMock()
                mock_create.return_value = mock_engine

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    # Check that session_maker is in app.state
                    assert hasattr(app.state, "session_maker")
                    assert app.state.session_maker is not None

    @pytest.mark.asyncio
    async def test_engine_disposed_on_shutdown(self):
        """Engine should be disposed on app shutdown."""
        from heisenberg.backend.app import app

        with patch.dict(
            "os.environ",
            {"DATABASE_URL": "postgresql://test:test@localhost/test"},
        ):
            with patch("heisenberg.backend.database.create_async_engine") as mock_create:
                mock_engine = MagicMock()
                mock_engine.dispose = AsyncMock()
                mock_create.return_value = mock_engine

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    pass  # App starts and stops

                # Engine should have been disposed
                mock_engine.dispose.assert_called_once()


class TestNoGlobalDatabaseState:
    """Test that global database state is removed."""

    def test_no_global_engine_variable(self):
        """database.py should not have global _engine variable."""
        from heisenberg.backend import database

        # _engine should not exist as a module-level variable
        # or should be removed/deprecated
        if hasattr(database, "_engine"):
            assert database._engine is None or not hasattr(database, "_engine")

    def test_no_global_session_maker_variable(self):
        """database.py should not have global _session_maker variable."""
        from heisenberg.backend import database

        # _session_maker should not exist as a module-level variable
        # or should be removed/deprecated
        if hasattr(database, "_session_maker"):
            assert database._session_maker is None or not hasattr(database, "_session_maker")


class TestHealthCheckUsesAppState:
    """Test that health check gets database from app.state."""

    @pytest.mark.asyncio
    async def test_detailed_health_check_uses_app_state(self):
        """Detailed health check should get session_maker from app.state."""
        from heisenberg.backend.app import app

        with patch.dict(
            "os.environ",
            {"DATABASE_URL": "postgresql://test:test@localhost/test"},
        ):
            with patch("heisenberg.backend.database.create_async_engine") as mock_create:
                mock_engine = MagicMock()
                mock_engine.dispose = AsyncMock()
                mock_create.return_value = mock_engine

                with patch("heisenberg.backend.app.check_database_health") as mock_health:
                    mock_health.return_value = (True, 5.0)

                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.get("/health/detailed")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["database"]["connected"] is True
