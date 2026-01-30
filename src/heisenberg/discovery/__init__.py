"""Discover GitHub projects suitable for Heisenberg testing.

This package searches GitHub for repositories that:
1. Use Playwright for E2E testing
2. Upload test artifacts to GitHub Actions
3. Have recent failed workflow runs
"""

from .analysis import (
    analyze_source,
    analyze_source_with_status,
    determine_status,
    download_and_check_failures,
    extract_failure_count_from_dir,
    filter_expired_artifacts,
    find_valid_artifacts,
    is_playwright_artifact,
    select_best_artifact,
    sort_sources,
    verify_has_failures,
    verify_has_failures_cached,
)
from .cache import QuarantineCache, RunCache, get_default_cache_path, get_default_quarantine_path
from .cli import create_argument_parser, main
from .client import (
    download_artifact_to_dir,
    fetch_stars_batch,
    get_failed_jobs,
    get_failed_runs,
    get_repo_stars,
    get_run_artifacts,
    gh_api,
    search_repos,
)
from .display import DiscoveryDisplay
from .events import (
    AnalysisCompleted,
    AnalysisProgress,
    AnalysisStarted,
    DiscoveryCompleted,
    DiscoveryEvent,
    EventHandler,
    QueryCompleted,
    SearchCompleted,
    SearchStarted,
)
from .models import (
    CACHE_SCHEMA_VERSION,
    CACHE_TTL_DAYS,
    DEFAULT_QUERIES,
    GH_MAX_CONCURRENT,
    GH_MAX_RETRIES,
    GH_RETRY_BASE_DELAY,
    MAX_RUNS_TO_CHECK,
    PLAYWRIGHT_PATTERNS,
    QUARANTINE_SCHEMA_VERSION,
    QUARANTINE_TTL_HOURS,
    TIMEOUT_API,
    TIMEOUT_DOWNLOAD,
    ProgressInfo,
    ProjectSource,
    SourceStatus,
)
from .service import discover_sources
from .ui import (
    COL_REPO,
    COL_STATUS,
    COL_TRAIL,
    STATUS_COLORS,
    STATUS_ICONS,
    STATUS_LABELS,
    create_progress_display,
    format_progress_line,
    format_size,
    format_stars,
    format_status_color,
    format_status_icon,
    format_status_label,
    print_source_line,
    print_summary,
    save_results,
)

__all__ = [
    # models
    "DEFAULT_QUERIES",
    "PLAYWRIGHT_PATTERNS",
    "MAX_RUNS_TO_CHECK",
    "CACHE_TTL_DAYS",
    "CACHE_SCHEMA_VERSION",
    "TIMEOUT_API",
    "TIMEOUT_DOWNLOAD",
    "GH_MAX_CONCURRENT",
    "GH_MAX_RETRIES",
    "GH_RETRY_BASE_DELAY",
    "SourceStatus",
    "ProgressInfo",
    "ProjectSource",
    "QUARANTINE_TTL_HOURS",
    "QUARANTINE_SCHEMA_VERSION",
    # cache
    "get_default_cache_path",
    "get_default_quarantine_path",
    "RunCache",
    "QuarantineCache",
    # client
    "gh_api",
    "search_repos",
    "get_repo_stars",
    "fetch_stars_batch",
    "get_failed_jobs",
    "get_failed_runs",
    "get_run_artifacts",
    "download_artifact_to_dir",
    # analysis
    "is_playwright_artifact",
    "select_best_artifact",
    "download_and_check_failures",
    "verify_has_failures",
    "verify_has_failures_cached",
    "extract_failure_count_from_dir",
    "filter_expired_artifacts",
    "find_valid_artifacts",
    "determine_status",
    "analyze_source_with_status",
    "analyze_source",
    "sort_sources",
    # ui
    "COL_REPO",
    "COL_STATUS",
    "COL_TRAIL",
    "STATUS_ICONS",
    "STATUS_COLORS",
    "STATUS_LABELS",
    "format_status_label",
    "format_size",
    "format_stars",
    "create_progress_display",
    "format_progress_line",
    "format_status_icon",
    "format_status_color",
    "print_source_line",
    "print_summary",
    "save_results",
    # service
    "discover_sources",
    # cli
    "create_argument_parser",
    "main",
    # events
    "DiscoveryEvent",
    "EventHandler",
    "SearchStarted",
    "QueryCompleted",
    "SearchCompleted",
    "AnalysisStarted",
    "AnalysisProgress",
    "AnalysisCompleted",
    "DiscoveryCompleted",
    # display
    "DiscoveryDisplay",
]
