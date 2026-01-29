"""Discover GitHub projects suitable for Heisenberg testing.

This package searches GitHub for repositories that:
1. Use Playwright for E2E testing
2. Upload test artifacts to GitHub Actions
3. Have recent failed workflow runs
"""

from .analysis import (
    _artifact_sizes,  # noqa: F401
    _extract_failure_count,  # noqa: F401
    analyze_source,
    analyze_source_with_status,
    determine_status,
    download_and_check_failures,
    extract_failure_count_from_dir,
    filter_by_min_stars,
    filter_expired_artifacts,
    find_valid_artifacts,
    is_playwright_artifact,
    sort_sources,
    verify_has_failures,
    verify_has_failures_cached,
)
from .cache import QuarantineCache, RunCache, get_default_cache_path, get_default_quarantine_path
from .cli import create_argument_parser, main
from .client import (
    _gh_semaphore,  # noqa: F401
    _gh_subprocess,  # noqa: F401
    _is_rate_limit_error,  # noqa: F401
    download_artifact_to_dir,
    get_failed_runs,
    get_repo_stars,
    get_run_artifacts,
    gh_api,
    gh_artifact_download,
    search_repos,
)
from .models import (
    _PLAYWRIGHT_REGEX,  # noqa: F401
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
from .service import _USE_DEFAULT_CACHE, _USE_DEFAULT_QUARANTINE, discover_sources  # noqa: F401
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
    "get_failed_runs",
    "get_run_artifacts",
    "download_artifact_to_dir",
    "gh_artifact_download",
    # analysis
    "is_playwright_artifact",
    "download_and_check_failures",
    "verify_has_failures",
    "verify_has_failures_cached",
    "extract_failure_count_from_dir",
    "filter_expired_artifacts",
    "find_valid_artifacts",
    "determine_status",
    "analyze_source_with_status",
    "analyze_source",
    "filter_by_min_stars",
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
]
