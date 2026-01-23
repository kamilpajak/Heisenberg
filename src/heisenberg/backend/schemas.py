"""Pydantic schemas for Heisenberg API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ============================================================================
# Request Schemas
# ============================================================================


class ContainerLog(BaseModel):
    """Container log entry."""

    container_name: str
    entries: list[LogEntry] = Field(default_factory=list)


class LogEntry(BaseModel):
    """Single log entry."""

    timestamp: datetime
    message: str
    stream: str = "stdout"


class TestError(BaseModel):
    """Test error information."""

    message: str
    stack: str | None = None


class FailedTest(BaseModel):
    """Failed test information from Playwright report."""

    title: str
    file: str | None = None
    suite: str | None = None
    project: str | None = None
    duration_ms: int = 0
    errors: list[TestError] = Field(default_factory=list)
    start_time: datetime | None = None


class AnalyzeRequest(BaseModel):
    """Request body for /api/v1/analyze endpoint."""

    repository: str = Field(..., description="Repository name (owner/repo)")
    commit_sha: str | None = Field(None, description="Git commit SHA")
    branch: str | None = Field(None, description="Git branch name")
    pull_request_number: int | None = Field(None, description="PR number if applicable")

    # Test results
    total_tests: int = Field(0, description="Total number of tests")
    passed_tests: int = Field(0, description="Number of passed tests")
    failed_tests: list[FailedTest] = Field(..., description="List of failed tests")
    skipped_tests: int = Field(0, description="Number of skipped tests")

    # Optional context
    container_logs: list[ContainerLog] | None = Field(
        None,
        description="Backend container logs",
    )


# ============================================================================
# Response Schemas
# ============================================================================


class DiagnosisResponse(BaseModel):
    """AI diagnosis for a single failed test."""

    test_name: str
    root_cause: str
    evidence: list[str]
    suggested_fix: str
    confidence: str
    confidence_explanation: str | None = None


class AnalyzeResponse(BaseModel):
    """Response from /api/v1/analyze endpoint."""

    test_run_id: UUID
    repository: str
    diagnoses: list[DiagnosisResponse]
    total_input_tokens: int
    total_output_tokens: int
    created_at: datetime


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str | None = None


class DatabaseHealthStatus(BaseModel):
    """Database health status details."""

    connected: bool
    latency_ms: float
    error: str | None = None


class DetailedHealthResponse(BaseModel):
    """Detailed health check response with component status."""

    status: str = Field(
        ...,
        description="Overall health status: healthy, degraded, or unhealthy",
    )
    version: str
    database: DatabaseHealthStatus
    timestamp: datetime = Field(default_factory=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc))


# ============================================================================
# Organization/API Key Schemas
# ============================================================================


class OrganizationCreate(BaseModel):
    """Request to create a new organization."""

    name: str = Field(..., min_length=1, max_length=255)


class OrganizationResponse(BaseModel):
    """Organization response."""

    id: UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreate(BaseModel):
    """Request to create a new API key."""

    name: str | None = Field(None, max_length=255, description="Optional name for the key")


class APIKeyResponse(BaseModel):
    """API key response (without the actual key)."""

    id: UUID
    name: str | None
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class APIKeyCreatedResponse(BaseModel):
    """Response when creating a new API key (includes the actual key)."""

    id: UUID
    name: str | None
    api_key: str = Field(..., description="The API key - save this, it won't be shown again!")
    created_at: datetime
