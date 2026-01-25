"""Middleware components for Heisenberg backend."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from heisenberg.backend.logging import request_id_ctx
from heisenberg.backend.rate_limit import SlidingWindowRateLimiter

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add and propagate request ID."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request and add request ID.

        Args:
            request: Incoming request.
            call_next: Next middleware/endpoint handler.

        Returns:
            Response with X-Request-ID header.
        """
        # Get request ID from header or generate new one
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Set context variable for logging
        token = request_id_ctx.set(request_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx.reset(token)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for API rate limiting."""

    def __init__(self, app, requests_per_minute: int = 60):
        """
        Initialize rate limit middleware.

        Args:
            app: ASGI application.
            requests_per_minute: Maximum requests per minute per key.
        """
        super().__init__(app)
        self.limiter = SlidingWindowRateLimiter(requests_per_minute=requests_per_minute)

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request with rate limiting.

        Args:
            request: Incoming request.
            call_next: Next middleware/endpoint handler.

        Returns:
            Response or 429 Too Many Requests.
        """
        # Use API key for tracking, fallback to client IP
        key = (
            request.headers.get("X-API-Key") or request.client.host if request.client else "unknown"
        )

        allowed, headers = await self.limiter.is_allowed(key)

        if not allowed:
            # Calculate retry-after (seconds until window resets)
            retry_after = 60  # Conservative: wait full minute
            headers["Retry-After"] = str(retry_after)

            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please retry later."},
            )
            for header_name, header_value in headers.items():
                response.headers[header_name] = header_value
            return response

        response = await call_next(request)

        # Add rate limit headers to successful responses
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value

        return response
