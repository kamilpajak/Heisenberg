"""Rate limiting functionality for Heisenberg backend."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from heisenberg.backend.logging import get_logger

logger = get_logger(__name__)


class SlidingWindowRateLimiter:
    """Sliding window rate limiter for API requests.

    Thread-safe implementation using asyncio locks per key.

    Note:
        This implementation uses in-memory storage and is suitable for
        single-instance deployments only. It does not support horizontal
        scaling across multiple server instances.

        For distributed/multi-instance deployments, consider using a
        Redis-based rate limiter that provides shared state across instances.

        To prevent memory leaks from abandoned keys, call cleanup_stale_entries()
        periodically (e.g., via a background task or scheduled job).
    """

    def __init__(self, requests_per_minute: int = 60):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute.
        """
        self.rpm = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def is_allowed(self, key: str) -> tuple[bool, dict[str, str]]:
        """
        Check if a request is allowed for the given key.

        Thread-safe implementation using per-key locks to prevent race conditions.

        Args:
            key: Unique identifier for rate limiting (e.g., API key, IP).

        Returns:
            Tuple of (allowed, rate_limit_headers).
        """
        async with self._locks[key]:
            now = time.time()
            window_start = now - 60  # 1-minute sliding window

            # Clean old requests outside the window
            self.requests[key] = [t for t in self.requests[key] if t > window_start]

            current_count = len(self.requests[key])
            allowed = current_count < self.rpm

            if allowed:
                self.requests[key].append(now)
                remaining = self.rpm - current_count - 1
            else:
                remaining = 0

        headers = {
            "X-RateLimit-Limit": str(self.rpm),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(int(window_start + 60)),
        }

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                key=key,
                limit=self.rpm,
                current_count=current_count,
            )

        return allowed, headers

    def cleanup_stale_entries(self) -> int:
        """
        Remove stale request entries and their associated locks.

        This method should be called periodically to prevent memory leaks
        from keys that are no longer making requests.

        Returns:
            Number of entries cleaned up.
        """
        now = time.time()
        window_start = now - 60  # 1-minute sliding window

        stale_keys: list[str] = []

        for key, timestamps in self.requests.items():
            # Filter out old timestamps
            fresh = [t for t in timestamps if t > window_start]
            if fresh:
                self.requests[key] = fresh
            else:
                stale_keys.append(key)

        # Remove stale entries
        for key in stale_keys:
            del self.requests[key]
            if key in self._locks:
                del self._locks[key]

        if stale_keys:
            logger.debug(
                "rate_limiter_cleanup",
                cleaned_count=len(stale_keys),
            )

        return len(stale_keys)
