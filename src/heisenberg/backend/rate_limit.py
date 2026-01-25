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
