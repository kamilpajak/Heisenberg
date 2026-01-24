"""Tests for backend rate limiting - TDD for Phase 5."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


class TestSlidingWindowRateLimiter:
    """Test suite for sliding window rate limiter."""

    def test_rate_limiter_exists(self):
        """SlidingWindowRateLimiter should be importable."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        assert SlidingWindowRateLimiter is not None

    def test_rate_limiter_allows_under_limit(self):
        """Rate limiter should allow requests under the limit."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        # Given
        limiter = SlidingWindowRateLimiter(requests_per_minute=10)

        # When
        allowed, headers = limiter.is_allowed("test-key")

        # Then
        assert allowed

    def test_rate_limiter_blocks_over_limit(self):
        """Rate limiter should block requests over the limit."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        # Given
        limiter = SlidingWindowRateLimiter(requests_per_minute=3)

        # When - make 3 allowed requests
        for _ in range(3):
            allowed, _ = limiter.is_allowed("test-key")
            assert allowed

        # 4th request should be blocked
        allowed, headers = limiter.is_allowed("test-key")

        # Then
        assert not allowed

    def test_rate_limiter_tracks_by_key(self):
        """Rate limiter should track requests by key."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        # Given
        limiter = SlidingWindowRateLimiter(requests_per_minute=2)

        # When - exhaust limit for key1
        limiter.is_allowed("key1")
        limiter.is_allowed("key1")
        allowed_key1, _ = limiter.is_allowed("key1")

        # key2 should still have quota
        allowed_key2, _ = limiter.is_allowed("key2")

        # Then
        assert not allowed_key1
        assert allowed_key2

    def test_rate_limiter_returns_headers(self):
        """Rate limiter should return rate limit headers."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        # Given
        limiter = SlidingWindowRateLimiter(requests_per_minute=10)

        # When
        allowed, headers = limiter.is_allowed("test-key")

        # Then
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
        assert headers["X-RateLimit-Limit"] == "10"
        assert headers["X-RateLimit-Remaining"] == "9"

    def test_rate_limiter_resets_after_window(self):
        """Rate limiter should reset after time window passes."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        # Given
        limiter = SlidingWindowRateLimiter(requests_per_minute=2)

        # Exhaust limit
        limiter.is_allowed("key")
        limiter.is_allowed("key")
        allowed, _ = limiter.is_allowed("key")
        assert not allowed

        # When - simulate time passing (clear old requests)
        with patch("heisenberg.backend.rate_limit.time.time") as mock_time:
            # Set time to 61 seconds in the future
            mock_time.return_value = 9999999999.0
            allowed, _ = limiter.is_allowed("key")

        # Then
        assert allowed


class TestRateLimitMiddleware:
    """Test suite for rate limit middleware."""

    def test_middleware_exists(self):
        """RateLimitMiddleware should be importable."""
        from heisenberg.backend.middleware import RateLimitMiddleware

        assert RateLimitMiddleware is not None

    @pytest.mark.asyncio
    async def test_middleware_adds_rate_limit_headers(self):
        """Middleware should add rate limit headers to response."""
        from fastapi import FastAPI

        from heisenberg.backend.middleware import RateLimitMiddleware

        # Given
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        # When
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test")

        # Then
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_returns_429_when_exceeded(self):
        """Middleware should return 429 when rate limit exceeded."""
        from fastapi import FastAPI

        from heisenberg.backend.middleware import RateLimitMiddleware

        # Given
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=2)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        # When
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Make 2 allowed requests
            await client.get("/test")
            await client.get("/test")

            # 3rd request should be rate limited
            response = await client.get("/test")

        # Then
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_middleware_includes_retry_after_header(self):
        """Middleware should include Retry-After header on 429."""
        from fastapi import FastAPI

        from heisenberg.backend.middleware import RateLimitMiddleware

        # Given
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=1)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        # When
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/test")  # First request
            response = await client.get("/test")  # Rate limited

        # Then
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_uses_api_key_for_tracking(self):
        """Middleware should use API key for rate limit tracking."""
        from fastapi import FastAPI

        from heisenberg.backend.middleware import RateLimitMiddleware

        # Given
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=2)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        # When - exhaust limit for key1
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/test", headers={"X-API-Key": "key1"})
            await client.get("/test", headers={"X-API-Key": "key1"})
            response_key1 = await client.get("/test", headers={"X-API-Key": "key1"})

            # key2 should still be allowed
            response_key2 = await client.get("/test", headers={"X-API-Key": "key2"})

        # Then
        assert response_key1.status_code == 429
        assert response_key2.status_code == 200


class TestRateLimitConfig:
    """Test suite for rate limit configuration."""

    def test_settings_has_rate_limit_per_minute(self):
        """Settings should have rate_limit_per_minute field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "rate_limit_per_minute")
        assert settings.rate_limit_per_minute == 60  # default

    def test_settings_allows_custom_rate_limit(self):
        """Settings should allow custom rate limit."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
            rate_limit_per_minute=100,
        )
        assert settings.rate_limit_per_minute == 100
