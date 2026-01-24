"""Tests for backend structured logging - TDD for Phase 5."""

import json
from io import StringIO

import pytest


class TestLoggingConfig:
    """Test suite for logging configuration."""

    def test_logging_module_exists(self):
        """Logging module should be importable."""
        from heisenberg.backend.logging import configure_logging

        assert configure_logging is not None

    def test_get_logger_returns_logger(self):
        """get_logger should return a configured logger."""
        from heisenberg.backend.logging import get_logger

        logger = get_logger("test")
        assert logger is not None

    def test_logger_outputs_json_format(self):
        """Logger should output JSON format by default."""
        from heisenberg.backend.logging import configure_logging, get_logger

        # Given
        output = StringIO()
        configure_logging(log_level="INFO", json_format=True, stream=output)
        logger = get_logger("test")

        # When
        logger.info("test message", key="value")

        # Then
        output.seek(0)
        log_line = output.getvalue().strip()
        parsed = json.loads(log_line)
        assert "event" in parsed
        assert parsed["event"] == "test message"
        assert parsed["key"] == "value"

    def test_log_includes_timestamp(self):
        """Log entries should include timestamp."""
        from heisenberg.backend.logging import configure_logging, get_logger

        # Given
        output = StringIO()
        configure_logging(log_level="INFO", json_format=True, stream=output)
        logger = get_logger("test")

        # When
        logger.info("test message")

        # Then
        output.seek(0)
        parsed = json.loads(output.getvalue().strip())
        assert "timestamp" in parsed

    def test_log_includes_level(self):
        """Log entries should include log level."""
        from heisenberg.backend.logging import configure_logging, get_logger

        # Given
        output = StringIO()
        configure_logging(log_level="INFO", json_format=True, stream=output)
        logger = get_logger("test")

        # When
        logger.warning("warning message")

        # Then
        output.seek(0)
        parsed = json.loads(output.getvalue().strip())
        assert "level" in parsed
        assert parsed["level"] == "warning"

    def test_log_includes_logger_name(self):
        """Log entries should include logger name."""
        from heisenberg.backend.logging import configure_logging, get_logger

        # Given
        output = StringIO()
        configure_logging(log_level="INFO", json_format=True, stream=output)
        logger = get_logger("heisenberg.backend")

        # When
        logger.info("test message")

        # Then
        output.seek(0)
        parsed = json.loads(output.getvalue().strip())
        assert "logger" in parsed
        assert parsed["logger"] == "heisenberg.backend"


class TestRequestContext:
    """Test suite for request context management."""

    def test_request_id_context_exists(self):
        """Request ID context variable should exist."""
        from heisenberg.backend.logging import request_id_ctx

        assert request_id_ctx is not None

    def test_request_id_default_is_empty(self):
        """Request ID should default to empty string."""
        from heisenberg.backend.logging import request_id_ctx

        assert request_id_ctx.get() == ""

    def test_request_id_can_be_set(self):
        """Request ID should be settable."""
        from heisenberg.backend.logging import request_id_ctx

        # Given
        token = request_id_ctx.set("test-request-123")

        try:
            # Then
            assert request_id_ctx.get() == "test-request-123"
        finally:
            # Cleanup
            request_id_ctx.reset(token)

    def test_log_includes_request_id_when_set(self):
        """Log entries should include request_id when set."""
        from heisenberg.backend.logging import (
            configure_logging,
            get_logger,
            request_id_ctx,
        )

        # Given
        output = StringIO()
        configure_logging(log_level="INFO", json_format=True, stream=output)
        logger = get_logger("test")
        token = request_id_ctx.set("req-abc-123")

        try:
            # When
            logger.info("test message")

            # Then
            output.seek(0)
            parsed = json.loads(output.getvalue().strip())
            assert "request_id" in parsed
            assert parsed["request_id"] == "req-abc-123"
        finally:
            request_id_ctx.reset(token)


class TestRequestIDMiddleware:
    """Test suite for request ID middleware."""

    def test_middleware_exists(self):
        """RequestIDMiddleware should be importable."""
        from heisenberg.backend.middleware import RequestIDMiddleware

        assert RequestIDMiddleware is not None

    @pytest.mark.asyncio
    async def test_middleware_generates_request_id(self):
        """Middleware should generate unique request ID for each request."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from heisenberg.backend.middleware import RequestIDMiddleware

        # Given
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        # When
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test")

        # Then
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0

    @pytest.mark.asyncio
    async def test_middleware_uses_provided_request_id(self):
        """Middleware should use X-Request-ID from incoming request if provided."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from heisenberg.backend.middleware import RequestIDMiddleware

        # Given
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        # When
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test", headers={"X-Request-ID": "custom-id-456"})

        # Then
        assert response.headers["X-Request-ID"] == "custom-id-456"

    @pytest.mark.asyncio
    async def test_middleware_sets_context_var(self):
        """Middleware should set request_id in context var."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from heisenberg.backend.logging import request_id_ctx
        from heisenberg.backend.middleware import RequestIDMiddleware

        # Given
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)
        captured_request_id = None

        @app.get("/test")
        async def test_endpoint():
            nonlocal captured_request_id
            captured_request_id = request_id_ctx.get()
            return {"status": "ok"}

        # When
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/test", headers={"X-Request-ID": "context-test-789"})

        # Then
        assert captured_request_id == "context-test-789"


class TestLoggingSettings:
    """Test suite for logging settings in config."""

    def test_settings_has_log_level(self):
        """Settings should have log_level field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "log_level")
        assert settings.log_level == "INFO"  # default

    def test_settings_has_log_json_format(self):
        """Settings should have log_json_format field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "log_json_format")
        assert settings.log_json_format is True  # default
