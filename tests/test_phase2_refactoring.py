"""Tests for Phase 2 refactoring - TDD approach.

Phase 2: Rate limiter scalability and thread-safety
- Make is_allowed() async
- Add asyncio.Lock per key to prevent race conditions
- Update middleware to await is_allowed()
"""

from __future__ import annotations

import asyncio
import inspect

import pytest
from httpx import ASGITransport, AsyncClient


class TestAsyncRateLimiter:
    """Test suite for async rate limiter."""

    def test_is_allowed_is_coroutine(self):
        """is_allowed() should be a coroutine function."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(requests_per_minute=10)

        # is_allowed should be an async method
        assert inspect.iscoroutinefunction(limiter.is_allowed)

    @pytest.mark.asyncio
    async def test_is_allowed_can_be_awaited(self):
        """is_allowed() should be awaitable and return correct tuple."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(requests_per_minute=10)

        # Should be awaitable
        result = await limiter.is_allowed("test-key")

        # Should return tuple (allowed, headers)
        assert isinstance(result, tuple)
        assert len(result) == 2
        allowed, headers = result
        assert isinstance(allowed, bool)
        assert isinstance(headers, dict)

    @pytest.mark.asyncio
    async def test_async_allows_under_limit(self):
        """Async rate limiter should allow requests under the limit."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(requests_per_minute=10)

        allowed, headers = await limiter.is_allowed("test-key")

        assert allowed
        assert headers["X-RateLimit-Remaining"] == "9"

    @pytest.mark.asyncio
    async def test_async_blocks_over_limit(self):
        """Async rate limiter should block requests over the limit."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(requests_per_minute=3)

        # Make 3 allowed requests
        for _ in range(3):
            allowed, _ = await limiter.is_allowed("test-key")
            assert allowed

        # 4th request should be blocked
        allowed, _ = await limiter.is_allowed("test-key")
        assert not allowed


class TestRateLimiterConcurrency:
    """Test suite for rate limiter concurrency safety."""

    def test_rate_limiter_has_locks(self):
        """Rate limiter should have internal locks dictionary."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(requests_per_minute=10)

        # Should have _locks attribute
        assert hasattr(limiter, "_locks")

    @pytest.mark.asyncio
    async def test_concurrent_requests_respect_limit(self):
        """Concurrent requests should not exceed rate limit due to race conditions."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        # Given a limiter with low limit
        limiter = SlidingWindowRateLimiter(requests_per_minute=5)

        # When making many concurrent requests
        async def make_request():
            allowed, _ = await limiter.is_allowed("concurrent-key")
            return allowed

        # Launch 20 concurrent requests
        tasks = [make_request() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # Then exactly 5 should be allowed (the limit)
        allowed_count = sum(1 for r in results if r)
        assert allowed_count == 5, f"Expected 5 allowed, got {allowed_count}"

    @pytest.mark.asyncio
    async def test_concurrent_requests_different_keys_independent(self):
        """Concurrent requests with different keys should be independent."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(requests_per_minute=3)

        async def make_requests_for_key(key: str, count: int) -> list[bool]:
            results = []
            for _ in range(count):
                allowed, _ = await limiter.is_allowed(key)
                results.append(allowed)
            return results

        # Launch concurrent requests for different keys
        tasks = [
            make_requests_for_key("key-a", 5),
            make_requests_for_key("key-b", 5),
            make_requests_for_key("key-c", 5),
        ]
        results = await asyncio.gather(*tasks)

        # Each key should have exactly 3 allowed (the limit)
        for key_results in results:
            allowed_count = sum(1 for r in key_results if r)
            assert allowed_count == 3

    @pytest.mark.asyncio
    async def test_lock_is_per_key(self):
        """Each key should have its own lock (not blocking other keys)."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(requests_per_minute=100)

        # Make requests for different keys
        await limiter.is_allowed("key-1")
        await limiter.is_allowed("key-2")
        await limiter.is_allowed("key-3")

        # Each key should have its own lock
        assert "key-1" in limiter._locks
        assert "key-2" in limiter._locks
        assert "key-3" in limiter._locks

    @pytest.mark.asyncio
    async def test_lock_type_is_asyncio_lock(self):
        """Locks should be asyncio.Lock instances."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(requests_per_minute=10)

        await limiter.is_allowed("test-key")

        # Lock should be asyncio.Lock
        assert isinstance(limiter._locks["test-key"], asyncio.Lock)


class TestMiddlewareWithAsyncRateLimiter:
    """Test suite for middleware with async rate limiter."""

    @pytest.mark.asyncio
    async def test_middleware_works_with_async_limiter(self):
        """Middleware should work correctly with async rate limiter."""
        from fastapi import FastAPI

        from heisenberg.backend.middleware import RateLimitMiddleware

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test")

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_429_with_async_limiter(self):
        """Middleware should return 429 when async rate limit exceeded."""
        from fastapi import FastAPI

        from heisenberg.backend.middleware import RateLimitMiddleware

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=2)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/test")
            await client.get("/test")
            response = await client.get("/test")

        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_middleware_concurrent_requests(self):
        """Middleware should handle concurrent requests correctly."""
        from fastapi import FastAPI

        from heisenberg.backend.middleware import RateLimitMiddleware

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=5)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Make 10 concurrent requests
            tasks = [client.get("/test") for _ in range(10)]
            responses = await asyncio.gather(*tasks)

        # Exactly 5 should succeed (200), rest should be 429
        success_count = sum(1 for r in responses if r.status_code == 200)
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)

        assert success_count == 5, f"Expected 5 successes, got {success_count}"
        assert rate_limited_count == 5, f"Expected 5 rate-limited, got {rate_limited_count}"
