"""Tests for backend enhanced health check - TDD for Phase 5."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


class TestHealthModule:
    """Test suite for health check module."""

    def test_health_module_exists(self):
        """Health module should be importable."""
        from heisenberg.backend.health import check_database_health

        assert check_database_health is not None

    @pytest.mark.asyncio
    async def test_check_database_health_returns_tuple(self):
        """check_database_health should return (is_healthy, latency_ms)."""
        from heisenberg.backend.health import check_database_health

        # Given
        mock_session_maker = MagicMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        # When
        is_healthy, latency_ms = await check_database_health(mock_session_maker)

        # Then
        assert isinstance(is_healthy, bool)
        assert isinstance(latency_ms, float)

    @pytest.mark.asyncio
    async def test_check_database_health_returns_true_when_ok(self):
        """check_database_health should return True when DB is healthy."""
        from heisenberg.backend.health import check_database_health

        # Given
        mock_session_maker = MagicMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        # When
        is_healthy, latency_ms = await check_database_health(mock_session_maker)

        # Then
        assert is_healthy
        assert latency_ms >= 0

    @pytest.mark.asyncio
    async def test_check_database_health_returns_false_on_error(self):
        """check_database_health should return False when DB fails."""
        from heisenberg.backend.health import check_database_health

        # Given
        mock_session_maker = MagicMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("Connection refused"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_session

        # When
        is_healthy, latency_ms = await check_database_health(mock_session_maker)

        # Then
        assert not is_healthy
        assert latency_ms == pytest.approx(0.0)


class TestDetailedHealthResponse:
    """Test suite for detailed health response schema."""

    def test_detailed_health_response_exists(self):
        """DetailedHealthResponse schema should be importable."""
        from heisenberg.backend.schemas import DetailedHealthResponse

        assert DetailedHealthResponse is not None

    def test_detailed_health_response_has_status(self):
        """DetailedHealthResponse should have status field."""
        from heisenberg.backend.schemas import (
            DatabaseHealthStatus,
            DetailedHealthResponse,
        )

        response = DetailedHealthResponse(
            status="healthy",
            version="0.1.0",
            database=DatabaseHealthStatus(connected=True, latency_ms=5.0),
        )
        assert response.status == "healthy"

    def test_detailed_health_response_has_database(self):
        """DetailedHealthResponse should have database status."""
        from heisenberg.backend.schemas import (
            DatabaseHealthStatus,
            DetailedHealthResponse,
        )

        response = DetailedHealthResponse(
            status="healthy",
            version="0.1.0",
            database=DatabaseHealthStatus(connected=True, latency_ms=5.0),
        )
        assert response.database.connected
        assert response.database.latency_ms == pytest.approx(5.0)

    def test_detailed_health_response_has_timestamp(self):
        """DetailedHealthResponse should have timestamp."""
        from datetime import datetime

        from heisenberg.backend.schemas import (
            DatabaseHealthStatus,
            DetailedHealthResponse,
        )

        response = DetailedHealthResponse(
            status="healthy",
            version="0.1.0",
            database=DatabaseHealthStatus(connected=True, latency_ms=5.0),
        )
        assert hasattr(response, "timestamp")
        assert isinstance(response.timestamp, datetime)


class TestHealthEndpoint:
    """Test suite for /health endpoint."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        from heisenberg.backend.app import app

        return AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        )

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_200(self, test_client: AsyncClient):
        """Health endpoint should return 200."""
        async with test_client as client:
            response = await client.get("/health")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_includes_version(self, test_client: AsyncClient):
        """Health response should include version."""
        from heisenberg import __version__

        async with test_client as client:
            response = await client.get("/health")
            data = response.json()
            assert "version" in data
            assert data["version"] == __version__

    @pytest.mark.asyncio
    async def test_health_includes_status(self, test_client: AsyncClient):
        """Health response should include status."""
        async with test_client as client:
            response = await client.get("/health")
            data = response.json()
            assert "status" in data
            assert data["status"] in ["healthy", "degraded", "unhealthy"]


class TestDetailedHealthEndpoint:
    """Test suite for /health/detailed endpoint."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        from heisenberg.backend.app import app

        return AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        )

    @pytest.mark.asyncio
    async def test_detailed_health_endpoint_exists(self, test_client: AsyncClient):
        """Detailed health endpoint should exist at /health/detailed."""
        async with test_client as client:
            response = await client.get("/health/detailed")
            # Should not be 404
            assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_detailed_health_includes_database_status(self, test_client: AsyncClient):
        """Detailed health should include database status."""
        from heisenberg.backend.app import app

        # Set up mock session_maker in app.state
        app.state.session_maker = MagicMock()

        async with test_client as client:
            with patch("heisenberg.backend.app.check_database_health") as mock_check:
                mock_check.return_value = (True, 5.5)
                response = await client.get("/health/detailed")
                data = response.json()

                assert "database" in data
                assert "connected" in data["database"]
                assert "latency_ms" in data["database"]

        # Cleanup
        if hasattr(app.state, "session_maker"):
            del app.state.session_maker

    @pytest.mark.asyncio
    async def test_detailed_health_returns_degraded_when_db_slow(self, test_client: AsyncClient):
        """Detailed health should return 'degraded' when DB is slow."""
        from heisenberg.backend.app import app

        # Set up mock session_maker in app.state
        app.state.session_maker = MagicMock()

        async with test_client as client:
            with patch("heisenberg.backend.app.check_database_health") as mock_check:
                # Simulate slow database (> 1000ms)
                mock_check.return_value = (True, 1500.0)
                response = await client.get("/health/detailed")
                data = response.json()

                assert data["status"] == "degraded"

        # Cleanup
        if hasattr(app.state, "session_maker"):
            del app.state.session_maker

    @pytest.mark.asyncio
    async def test_detailed_health_returns_unhealthy_when_db_down(self, test_client: AsyncClient):
        """Detailed health should return 'unhealthy' when DB is down."""
        from heisenberg.backend.app import app

        # Set up mock session_maker in app.state
        app.state.session_maker = MagicMock()

        async with test_client as client:
            with patch("heisenberg.backend.app.check_database_health") as mock_check:
                mock_check.return_value = (False, 0.0)
                response = await client.get("/health/detailed")
                data = response.json()

                assert data["status"] == "unhealthy"
                assert not data["database"]["connected"]

        # Cleanup
        if hasattr(app.state, "session_maker"):
            del app.state.session_maker


class TestAppLifespan:
    """Test suite for app lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_initializes_logging(self):
        """Lifespan should configure logging on startup."""
        from fastapi import FastAPI

        from heisenberg.backend.app import lifespan

        test_app = FastAPI(lifespan=lifespan)

        with (
            patch("heisenberg.backend.app.configure_logging") as mock_logging,
            patch.dict("os.environ", {"DATABASE_URL": ""}, clear=False),
        ):
            # Mock get_settings to avoid validation errors
            mock_settings = MagicMock()
            mock_settings.log_level = "INFO"
            mock_settings.log_json_format = True
            mock_settings.database_url = "postgresql://test"
            with patch("heisenberg.backend.config.get_settings", return_value=mock_settings):
                async with lifespan(test_app):
                    pass

            mock_logging.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_initializes_db_when_url_set(self):
        """Lifespan should init DB when DATABASE_URL is set."""
        from fastapi import FastAPI

        from heisenberg.backend.app import lifespan

        test_app = FastAPI(lifespan=lifespan)

        mock_settings = MagicMock()
        mock_settings.log_level = "INFO"
        mock_settings.log_json_format = True
        mock_settings.database_url = "postgresql://test:test@localhost/test"

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        mock_session_maker = MagicMock()

        with (
            patch("heisenberg.backend.app.configure_logging"),
            patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}, clear=False),
            patch("heisenberg.backend.config.get_settings", return_value=mock_settings),
            patch(
                "heisenberg.backend.database.init_db",
                return_value=(mock_engine, mock_session_maker),
            ) as mock_init_db,
        ):
            async with lifespan(test_app):
                pass

            mock_init_db.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_skips_db_when_no_url(self):
        """Lifespan should skip DB init when no DATABASE_URL."""
        import os

        from fastapi import FastAPI

        from heisenberg.backend.app import lifespan

        test_app = FastAPI(lifespan=lifespan)

        mock_settings = MagicMock()
        mock_settings.log_level = "INFO"
        mock_settings.log_json_format = True
        mock_settings.database_url = ""

        # Ensure DATABASE_URL is not set
        env_backup = os.environ.get("DATABASE_URL")
        if "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]

        try:
            with (
                patch("heisenberg.backend.app.configure_logging"),
                patch("heisenberg.backend.config.get_settings", return_value=mock_settings),
                patch("heisenberg.backend.database.init_db") as mock_init_db,
            ):
                async with lifespan(test_app):
                    pass

                mock_init_db.assert_not_called()
        finally:
            if env_backup:
                os.environ["DATABASE_URL"] = env_backup

    @pytest.mark.asyncio
    async def test_lifespan_disposes_engine_on_shutdown(self):
        """Lifespan should dispose engine on shutdown."""
        from fastapi import FastAPI

        from heisenberg.backend.app import lifespan

        test_app = FastAPI(lifespan=lifespan)

        mock_settings = MagicMock()
        mock_settings.log_level = "INFO"
        mock_settings.log_json_format = True
        mock_settings.database_url = "postgresql://test:test@localhost/test"

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        mock_session_maker = MagicMock()

        with (
            patch("heisenberg.backend.app.configure_logging"),
            patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}, clear=False),
            patch("heisenberg.backend.config.get_settings", return_value=mock_settings),
            patch(
                "heisenberg.backend.database.init_db",
                return_value=(mock_engine, mock_session_maker),
            ),
        ):
            async with lifespan(test_app):
                pass

            # Engine should have been disposed on shutdown
            mock_engine.dispose.assert_called_once()
