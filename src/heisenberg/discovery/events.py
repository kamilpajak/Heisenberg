"""Typed events for discovery process.

Event-based architecture decouples business logic from display concerns.
Services emit events, display components handle rendering.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import ProjectSource, SourceStatus

# =============================================================================
# SEARCH PHASE EVENTS
# =============================================================================


@dataclass
class SearchStarted:
    """Emitted when search phase begins."""

    total_queries: int


@dataclass
class QueryCompleted:
    """Emitted after each search query completes."""

    query_index: int  # 0-based
    query_preview: str  # First ~30 chars of query
    repos_found: int  # Repos found by this query
    new_repos: int  # Repos not seen in previous queries


@dataclass
class SearchCompleted:
    """Emitted when search phase ends, before analysis begins."""

    total_candidates: int  # Total unique repos found
    quarantine_skipped: int  # Skipped due to quarantine cache
    stars_filtered: int  # Skipped due to min_stars filter
    to_analyze: int  # Repos that will be analyzed


# =============================================================================
# ANALYSIS PHASE EVENTS
# =============================================================================


@dataclass
class AnalysisStarted:
    """Emitted when analysis of a repo begins."""

    repo: str
    stars: int
    index: int  # 0-based position in analysis queue
    total: int  # Total repos to analyze


@dataclass
class AnalysisProgress:
    """Emitted during analysis to report current stage."""

    repo: str
    stage: str  # "fetching runs", "downloading...", "checking cache", etc.


@dataclass
class AnalysisCompleted:
    """Emitted when analysis of a repo completes."""

    repo: str
    stars: int
    status: SourceStatus
    artifact_name: str | None  # Name of checked artifact (if any)
    failure_count: int | None  # Number of failures (if verified)
    cache_hit: bool  # Whether result came from cache
    elapsed_ms: int  # Time taken for analysis
    index: int  # 0-based position
    total: int  # Total repos being analyzed


# =============================================================================
# FINAL EVENT
# =============================================================================


@dataclass
class DiscoveryCompleted:
    """Emitted when entire discovery process completes."""

    results: list[ProjectSource]  # All analyzed sources
    stats: dict[SourceStatus, int]  # Count by status


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================

DiscoveryEvent = (
    SearchStarted
    | QueryCompleted
    | SearchCompleted
    | AnalysisStarted
    | AnalysisProgress
    | AnalysisCompleted
    | DiscoveryCompleted
)

EventHandler = Callable[[DiscoveryEvent], None]
