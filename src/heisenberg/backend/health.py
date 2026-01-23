"""Health check functionality for Heisenberg backend."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from sqlalchemy import text

from heisenberg.backend.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = get_logger(__name__)


async def check_database_health(
    session_maker: async_sessionmaker[AsyncSession],
) -> tuple[bool, float]:
    """
    Check database connectivity and measure latency.

    Args:
        session_maker: SQLAlchemy async session maker.

    Returns:
        Tuple of (is_healthy, latency_ms).
    """
    start = time.perf_counter()

    try:
        async with session_maker() as session:
            await session.execute(text("SELECT 1"))
        latency_ms = (time.perf_counter() - start) * 1000

        logger.debug(
            "database_health_check",
            connected=True,
            latency_ms=round(latency_ms, 2),
        )

        return True, latency_ms

    except Exception as e:
        logger.warning(
            "database_health_check_failed",
            connected=False,
            error=str(e),
        )
        return False, 0.0
