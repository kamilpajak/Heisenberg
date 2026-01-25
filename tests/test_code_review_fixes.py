"""Tests for code review fixes - TDD approach.

Fixes:
1. Memory leak in rate limiter - cleanup inactive locks
2. Immutable PRICING dict - use MappingProxyType
"""

from __future__ import annotations

import asyncio
from types import MappingProxyType
from unittest.mock import patch

import pytest


class TestRateLimiterLockCleanup:
    """Test that rate limiter cleans up unused locks to prevent memory leak."""

    def test_rate_limiter_has_cleanup_method(self):
        """Rate limiter should have a cleanup_stale_entries method."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter()
        assert hasattr(limiter, "cleanup_stale_entries")
        assert callable(limiter.cleanup_stale_entries)

    @pytest.mark.asyncio
    async def test_cleanup_removes_stale_requests(self):
        """Cleanup should remove requests older than the window."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(requests_per_minute=10)

        # Make some requests
        await limiter.is_allowed("key1")
        await limiter.is_allowed("key2")

        assert len(limiter.requests) == 2

        # Simulate time passing beyond the window
        with patch("heisenberg.backend.rate_limit.time.time") as mock_time:
            mock_time.return_value = 9999999999.0
            limiter.cleanup_stale_entries()

        # Stale entries should be cleaned
        assert len(limiter.requests) == 0

    @pytest.mark.asyncio
    async def test_cleanup_removes_stale_locks(self):
        """Cleanup should remove locks for keys with no requests."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(requests_per_minute=10)

        # Make requests to create locks
        await limiter.is_allowed("key1")
        await limiter.is_allowed("key2")

        assert "key1" in limiter._locks
        assert "key2" in limiter._locks

        # Simulate time passing beyond the window
        with patch("heisenberg.backend.rate_limit.time.time") as mock_time:
            mock_time.return_value = 9999999999.0
            limiter.cleanup_stale_entries()

        # Locks for stale keys should be removed
        assert "key1" not in limiter._locks
        assert "key2" not in limiter._locks

    @pytest.mark.asyncio
    async def test_cleanup_preserves_active_entries(self):
        """Cleanup should preserve entries still within the window."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(requests_per_minute=10)

        # Make requests
        await limiter.is_allowed("active_key")
        await limiter.is_allowed("stale_key")

        # Make stale_key old but keep active_key fresh
        import time

        current_time = time.time()
        limiter.requests["stale_key"] = [current_time - 120]  # 2 minutes old
        limiter.requests["active_key"] = [current_time - 30]  # 30 seconds old

        limiter.cleanup_stale_entries()

        # Active entry should be preserved
        assert "active_key" in limiter.requests
        assert "active_key" in limiter._locks
        # Stale entry should be removed
        assert "stale_key" not in limiter.requests
        assert "stale_key" not in limiter._locks

    def test_cleanup_stats_returns_count(self):
        """Cleanup should return the number of cleaned entries."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(requests_per_minute=10)

        # Manually add stale entries
        import time

        old_time = time.time() - 120  # 2 minutes old
        limiter.requests["stale1"] = [old_time]
        limiter.requests["stale2"] = [old_time]
        limiter._locks["stale1"] = asyncio.Lock()
        limiter._locks["stale2"] = asyncio.Lock()

        cleaned_count = limiter.cleanup_stale_entries()

        assert cleaned_count == 2


class TestImmutablePricing:
    """Test that PRICING dict is immutable."""

    def test_pricing_is_mapping_proxy(self):
        """PRICING should be a MappingProxyType (immutable)."""
        from heisenberg.llm.models import PRICING

        assert isinstance(PRICING, MappingProxyType)

    def test_pricing_cannot_be_modified(self):
        """PRICING should not allow item assignment."""
        from heisenberg.llm.models import PRICING

        with pytest.raises(TypeError):
            PRICING["new_model"] = {"input": 1.0, "output": 2.0}

    def test_pricing_nested_dicts_are_immutable(self):
        """Nested pricing dicts should also be immutable."""
        from heisenberg.llm.models import PRICING

        # Get any existing model pricing
        model_pricing = PRICING.get("claude-sonnet-4-20250514")
        assert model_pricing is not None
        assert isinstance(model_pricing, MappingProxyType)

    def test_pricing_nested_cannot_be_modified(self):
        """Nested pricing dicts should not allow modification."""
        from heisenberg.llm.models import PRICING

        model_pricing = PRICING.get("claude-sonnet-4-20250514")
        with pytest.raises(TypeError):
            model_pricing["input"] = 999.0

    def test_estimated_cost_still_works(self):
        """LLMAnalysis.estimated_cost should still work with immutable PRICING."""
        from heisenberg.llm.models import LLMAnalysis

        analysis = LLMAnalysis(
            content="test",
            input_tokens=1000,
            output_tokens=500,
            model="claude-sonnet-4-20250514",
            provider="claude",
        )

        # Should calculate cost without errors
        cost = analysis.estimated_cost
        assert cost > 0


class TestRateLimiterDocumentation:
    """Test that rate limiter has scalability documentation."""

    def test_rate_limiter_has_scalability_note(self):
        """Rate limiter docstring should mention single-instance limitation."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        docstring = SlidingWindowRateLimiter.__doc__
        assert docstring is not None
        # Check for scalability warning
        assert "single" in docstring.lower() or "horizontal" in docstring.lower()

    def test_rate_limiter_suggests_redis_alternative(self):
        """Rate limiter docstring should mention Redis for multi-instance."""
        from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

        docstring = SlidingWindowRateLimiter.__doc__
        assert docstring is not None
        assert "redis" in docstring.lower() or "distributed" in docstring.lower()
