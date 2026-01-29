"""FastAPI application for Heisenberg backend."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request

from heisenberg.backend.health import check_database_health
from heisenberg.backend.logging import configure_logging, get_logger
from heisenberg.backend.middleware import RateLimitMiddleware, RequestIDMiddleware
from heisenberg.backend.routers import analyze, feedback, tasks, usage
from heisenberg.backend.schemas import (
    DatabaseHealthStatus,
    DetailedHealthResponse,
    HealthResponse,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Application version
__version__ = "1.8.2"

# API prefix
API_PREFIX = "/api/v1"

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    from heisenberg.backend.config import get_settings
    from heisenberg.backend.database import init_db

    settings = get_settings()

    # Configure logging
    configure_logging(
        log_level=settings.log_level,
        json_format=settings.log_json_format,
    )

    # Initialize database if DATABASE_URL is set
    if os.environ.get("DATABASE_URL"):
        engine, session_maker = init_db(settings)
        app.state.engine = engine
        app.state.session_maker = session_maker
        logger.info("database_initialized", database_url=settings.database_url[:20] + "...")

    logger.info("app_started", version=__version__)

    yield

    # Shutdown
    if hasattr(app.state, "engine"):
        await app.state.engine.dispose()
    logger.info("app_shutdown")


app = FastAPI(
    title="Heisenberg API",
    description="AI Root Cause Analysis for Flaky Tests",
    version=__version__,
    lifespan=lifespan,
)

# Add middleware (order matters - first added is outermost)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)  # type: ignore[arg-type]
app.add_middleware(RequestIDMiddleware)  # type: ignore[arg-type]

# Include routers
app.include_router(analyze.router, prefix=API_PREFIX)
app.include_router(feedback.router, prefix=API_PREFIX)
app.include_router(usage.router, prefix=API_PREFIX)
app.include_router(tasks.router, prefix=API_PREFIX)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        Health status of the API.
    """
    return HealthResponse(status="healthy", version=__version__)


@app.get("/health/detailed", response_model=DetailedHealthResponse, tags=["Health"])
async def detailed_health_check(request: Request) -> DetailedHealthResponse:
    """
    Detailed health check endpoint with component status.

    Returns:
        Detailed health status including database connectivity.
    """
    # Get session_maker from app.state
    session_maker = getattr(request.app.state, "session_maker", None)

    # Check database health
    if session_maker is not None:
        db_connected, db_latency = await check_database_health(session_maker)
    else:
        db_connected, db_latency = False, 0.0

    # Determine overall status
    if not db_connected:
        status = "unhealthy"
    elif db_latency > 1000:  # More than 1 second is degraded
        status = "degraded"
    else:
        status = "healthy"

    return DetailedHealthResponse(
        status=status,
        version=__version__,
        database=DatabaseHealthStatus(
            connected=db_connected,
            latency_ms=db_latency,
        ),
    )
