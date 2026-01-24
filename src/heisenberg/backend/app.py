"""FastAPI application for Heisenberg backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from heisenberg.backend.health import check_database_health
from heisenberg.backend.routers import analyze, feedback, tasks, usage
from heisenberg.backend.schemas import (
    DatabaseHealthStatus,
    DetailedHealthResponse,
    HealthResponse,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Application version
__version__ = "0.1.0"

# API prefix
API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    # Database initialization would happen here in production
    yield
    # Shutdown
    # Database cleanup would happen here


app = FastAPI(
    title="Heisenberg API",
    description="AI Root Cause Analysis for Flaky Tests",
    version=__version__,
    lifespan=lifespan,
)

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
async def detailed_health_check() -> DetailedHealthResponse:
    """
    Detailed health check endpoint with component status.

    Returns:
        Detailed health status including database connectivity.
    """
    from heisenberg.backend.database import _session_maker

    # Check database health
    if _session_maker is not None:
        db_connected, db_latency = await check_database_health(_session_maker)
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
