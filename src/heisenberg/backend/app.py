"""FastAPI application for Heisenberg backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from heisenberg.backend.routers import analyze
from heisenberg.backend.schemas import HealthResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Application version
__version__ = "0.1.0"


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
app.include_router(analyze.router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        Health status of the API.
    """
    return HealthResponse(status="healthy", version=__version__)
