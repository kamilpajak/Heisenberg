"""Domain models and configuration constants for project discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_QUERIES = [
    'playwright "upload-artifact" path:.github/workflows extension:yml',
    '"blob-report" "upload-artifact" path:.github/workflows',
    '"playwright-report" "actions/upload-artifact" path:.github/workflows',
    '"blob-report" path:.github extension:yml',  # Repos with custom upload actions
]

PLAYWRIGHT_PATTERNS = [
    r"^playwright[-_]?report",  # playwright-report, playwright_report
    r"^blob[-_]?report",  # blob-report (Playwright sharding)
    r"^playwright[-_]?traces?",  # playwright-trace, playwright-traces
    r"^trace\.zip$",  # trace.zip
    r"playwright.*report",  # any-playwright-report
    r"playwright.*traces?",  # middleware-starter-playwright-traces
]

_PLAYWRIGHT_REGEX = re.compile("|".join(PLAYWRIGHT_PATTERNS), re.IGNORECASE)

MAX_RUNS_TO_CHECK = 5
CACHE_TTL_DAYS = 90
CACHE_SCHEMA_VERSION = 1
QUARANTINE_TTL_HOURS = 24
QUARANTINE_SCHEMA_VERSION = 1
TIMEOUT_API = 30  # seconds — for gh API calls
TIMEOUT_DOWNLOAD = 120  # seconds — for artifact downloads
GH_MAX_CONCURRENT = 4  # max concurrent gh CLI processes
GH_MAX_RETRIES = 3  # retries on secondary rate limit
GH_RETRY_BASE_DELAY = 2  # seconds — exponential backoff base

# =============================================================================
# DOMAIN MODELS
# =============================================================================


class SourceStatus(Enum):
    """Status of a source project."""

    COMPATIBLE = "compatible"  # Has valid Playwright artifacts WITH failures
    NO_FAILURES = "no_failures"  # Has Playwright artifacts but 0 test failures
    HAS_ARTIFACTS = "has_artifacts"  # Has artifacts but not Playwright
    NO_ARTIFACTS = "no_artifacts"  # Run exists but no artifacts
    NO_FAILED_RUNS = "no_failed_runs"  # No failed workflow runs


@dataclass
class ProgressInfo:
    """Progress information for a single repo analysis."""

    completed: int  # Sequential completion number (1, 2, 3...)
    total: int  # Total repos to analyze
    repo: str  # Repository name
    status: str  # SourceStatus value
    elapsed_ms: int  # Time taken in milliseconds
    message: str | None = None  # Optional extra message


@dataclass
class ProjectSource:
    """A source project for testing."""

    repo: str
    stars: int
    status: SourceStatus
    artifact_names: list[str] = field(default_factory=list)
    playwright_artifacts: list[str] = field(default_factory=list)
    run_id: str | None = None
    run_url: str | None = None

    @property
    def compatible(self) -> bool:
        """Whether this source has valid Playwright artifacts."""
        return self.status == SourceStatus.COMPATIBLE

    @property
    def has_artifacts(self) -> bool:
        """Whether this source has any artifacts."""
        return len(self.artifact_names) > 0
