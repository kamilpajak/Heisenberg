"""Pydantic schemas for Heisenberg API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
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


# ============================================================================
# Feedback Schemas
# ============================================================================


class FeedbackCreate(BaseModel):
    """Request to create feedback on an analysis."""

    is_helpful: bool = Field(..., description="Whether the analysis was helpful")
    comment: str | None = Field(None, description="Optional comment about the analysis")


class FeedbackResponse(BaseModel):
    """Response for feedback."""

    id: UUID
    analysis_id: UUID
    is_helpful: bool
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackStats(BaseModel):
    """Aggregated feedback statistics."""

    total_feedback: int = Field(..., description="Total number of feedback entries")
    helpful_count: int = Field(..., description="Number of helpful ratings")
    not_helpful_count: int = Field(..., description="Number of not helpful ratings")
    helpful_percentage: float = Field(..., description="Percentage of helpful ratings")


# ============================================================================
# Usage Tracking Schemas
# ============================================================================


class UsageCreate(BaseModel):
    """Request to create a usage record."""

    model_name: str = Field(..., description="Name of the LLM model used")
    input_tokens: int = Field(..., ge=0, description="Number of input tokens")
    output_tokens: int = Field(..., ge=0, description="Number of output tokens")
    analysis_id: UUID | None = Field(None, description="Optional linked analysis ID")


class UsageSummary(BaseModel):
    """Aggregated usage statistics for an organization."""

    organization_id: UUID
    period_start: datetime
    period_end: datetime
    total_requests: int = Field(..., description="Total number of API requests")
    total_input_tokens: int = Field(..., description="Total input tokens used")
    total_output_tokens: int = Field(..., description="Total output tokens used")
    total_cost_usd: Decimal = Field(..., description="Total cost in USD")
    by_model: dict[str, Any] = Field(
        default_factory=dict,
        description="Usage breakdown by model",
    )


# ============================================================================
# Task Queue Schemas
# ============================================================================


class TaskCreate(BaseModel):
    """Request to create an async task."""

    organization_id: UUID = Field(..., description="Organization ID")
    task_type: str = Field(..., description="Type of task (e.g., 'analyze')")
    payload: dict[str, Any] = Field(default_factory=dict, description="Task payload")


class TaskResponse(BaseModel):
    """Response for an async task."""

    id: UUID
    task_type: str
    status: str
    payload: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
