#!/usr/bin/env python3
"""Discover GitHub projects suitable for Heisenberg testing.

This script searches GitHub for repositories that:
1. Use Playwright for E2E testing
2. Upload test artifacts to GitHub Actions
3. Have recent failed workflow runs

Architecture follows Single Responsibility Principle:
- GitHubClient: API communication
- Domain: ProjectSource, SourceStatus, validation logic
- Presenter: CLI output formatting
- Config: DEFAULT_QUERIES, PLAYWRIGHT_PATTERNS
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import TextIO

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_QUERIES = [
    'playwright "upload-artifact" path:.github/workflows extension:yml',
    '"blob-report" "upload-artifact" path:.github/workflows',
    '"playwright-report" "actions/upload-artifact" path:.github/workflows',
    '"blob-report" path:.github extension:yml',  # Repos with custom upload actions
]

# Curated list of repos known to have Playwright tests with frequent failures
KNOWN_GOOD_REPOS = [
    "microsoft/playwright",  # The Playwright project itself - always has test failures
]

PLAYWRIGHT_PATTERNS = [
    r"^playwright[-_]?report",  # playwright-report, playwright_report
    r"^blob[-_]?report",  # blob-report (Playwright sharding)
    r"^playwright[-_]?traces?",  # playwright-trace, playwright-traces
    r"^trace\.zip$",  # trace.zip
    r"playwright.*report",  # any-playwright-report
]

_PLAYWRIGHT_REGEX = re.compile("|".join(PLAYWRIGHT_PATTERNS), re.IGNORECASE)

MAX_RUNS_TO_CHECK = 5
CACHE_TTL_DAYS = 90
CACHE_SCHEMA_VERSION = 1


def get_default_cache_path():
    """Get the default cache path (XDG-compliant).

    Returns:
        Path to ~/.cache/heisenberg/verified_runs.json
    """
    from pathlib import Path

    cache_dir = Path.home() / ".cache" / "heisenberg"
    return cache_dir / "verified_runs.json"


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


# =============================================================================
# VERIFICATION CACHE
# =============================================================================


class RunCache:
    """Cache for verified run results with TTL.

    Stores run_id -> failure_count mappings to avoid re-downloading
    large artifacts on subsequent runs. Entries expire after 90 days
    to ensure users can still view runs on GitHub.

    Thread-safe: uses a lock for concurrent access and auto-saves on write.
    """

    def __init__(self, cache_path: str | None = None):
        """Initialize cache.

        Args:
            cache_path: Path to cache JSON file. If None, uses in-memory only.
        """
        import threading
        from pathlib import Path

        self._path = Path(cache_path) if cache_path else None
        self._data: dict = {"schema_version": CACHE_SCHEMA_VERSION, "runs": {}}
        # Use RLock (reentrant) because set() calls save() while holding lock
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        """Load cache from disk if it exists, then prune expired entries."""
        if not self._path or not self._path.exists():
            return

        try:
            data = json.loads(self._path.read_text())
            # Ignore old schema versions
            if data.get("schema_version") != CACHE_SCHEMA_VERSION:
                return
            self._data = data
            # Prune expired/corrupt entries
            self._prune()
        except (json.JSONDecodeError, OSError):
            # Corrupt or unreadable file - start fresh
            pass

    def _prune(self) -> None:
        """Remove expired and corrupt entries from cache.

        Called during load to prevent unbounded cache growth.
        Saves to disk if any entries were pruned.
        """
        from datetime import datetime, timedelta

        now = datetime.now()
        cutoff = timedelta(days=CACHE_TTL_DAYS)
        expired_ids = []

        for run_id, entry in self._data["runs"].items():
            try:
                created_at = datetime.fromisoformat(entry["run_created_at"])
                if now - created_at > cutoff:
                    expired_ids.append(run_id)
            except (KeyError, ValueError):
                # Missing or invalid date - prune corrupt entry
                expired_ids.append(run_id)

        for run_id in expired_ids:
            del self._data["runs"][run_id]

        # Save if we pruned anything
        if expired_ids:
            self.save()

    def save(self) -> None:
        """Save cache to disk (thread-safe)."""
        if not self._path:
            return

        with self._lock:
            # Create parent directory if needed
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2))

    def get(self, run_id: str) -> int | None:
        """Get cached failure count for a run (thread-safe).

        Returns None if not in cache or if run is older than 90 days
        (GitHub artifacts would have expired).
        """
        from datetime import datetime, timedelta

        with self._lock:
            entry = self._data["runs"].get(run_id)
            if not entry:
                return None

            # Check TTL based on when the RUN was created (not when we cached it)
            # This ensures artifacts are still available on GitHub for demo users
            try:
                run_created_at = datetime.fromisoformat(entry["run_created_at"])
                run_age = datetime.now() - run_created_at
                if run_age > timedelta(days=CACHE_TTL_DAYS):
                    return None  # Expired - GitHub artifacts gone
                return entry["failure_count"]
            except (KeyError, ValueError):
                return None

    def set(self, run_id: str, failure_count: int, run_created_at: str) -> None:
        """Store failure count for a run and auto-save to disk.

        Thread-safe: uses lock for concurrent access.

        Args:
            run_id: GitHub workflow run ID
            failure_count: Number of test failures
            run_created_at: ISO timestamp of when the run was created on GitHub
        """
        with self._lock:
            self._data["runs"][run_id] = {
                "failure_count": failure_count,
                "run_created_at": run_created_at,
            }
            self.save()  # Auto-save to prevent data loss on crash


def verify_has_failures_cached(
    repo: str,
    run_id: str,
    artifact_name: str,
    cache: RunCache,
    run_created_at: str,
) -> bool:
    """Verify that an artifact contains actual test failures, using cache.

    Args:
        repo: Repository in owner/repo format
        run_id: Workflow run ID
        artifact_name: Name of the artifact to check
        cache: RunCache instance for caching results
        run_created_at: ISO timestamp of when the run was created on GitHub

    Returns:
        True if artifact has non-zero failure count.
    """
    # Check cache first
    cached_count = cache.get(run_id)
    if cached_count is not None:
        return cached_count > 0

    # Cache miss - download and verify
    failure_count = download_and_check_failures(repo, run_id, artifact_name)

    # Store result in cache (even if None or 0)
    if failure_count is not None:
        cache.set(run_id, failure_count, run_created_at)

    return failure_count is not None and failure_count > 0


# =============================================================================
# GITHUB CLIENT (API Communication)
# =============================================================================


def gh_api(endpoint: str, params: dict | None = None) -> dict | list | None:
    """Call GitHub API via gh CLI."""
    cmd = ["gh", "api", endpoint]
    if params:
        for k, v in params.items():
            cmd.extend(["-f", f"{k}={v}"])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout) if result.stdout.strip() else None
    except subprocess.CalledProcessError as e:
        if e.stderr and "rate limit" in e.stderr.lower():
            print(f"⚠️  Rate limit hit: {endpoint}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        return None


def search_repos(query: str, limit: int = 30) -> list[str]:
    """Search GitHub for repositories matching query.

    Returns list of unique repo names.
    """
    import urllib.parse

    encoded_query = urllib.parse.quote(query)
    endpoint = f"/search/code?q={encoded_query}&per_page={min(limit, 100)}"

    cmd = ["gh", "api", "-X", "GET", endpoint]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return []

    if not data or "items" not in data:
        return []

    seen: set[str] = set()
    for item in data["items"][:limit]:
        repo_data = item.get("repository", {})
        repo_name = repo_data.get("full_name", "")
        if repo_name:
            seen.add(repo_name)

    return list(seen)


def get_repo_stars(repo: str) -> int:
    """Get star count for a repository."""
    data = gh_api(f"/repos/{repo}")
    return data.get("stargazers_count", 0) if data else 0


def get_failed_runs(repo: str, limit: int = MAX_RUNS_TO_CHECK) -> list[dict]:
    """Get recent failed workflow runs for a repository."""
    cmd = ["gh", "api", "-X", "GET", f"/repos/{repo}/actions/runs?status=failure&per_page={limit}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return []

    return data.get("workflow_runs", []) if data else []


def get_run_artifacts(repo: str, run_id: str) -> list[dict]:
    """Get artifacts for a specific workflow run."""
    data = gh_api(f"/repos/{repo}/actions/runs/{run_id}/artifacts")
    if not data or not data.get("artifacts"):
        return []
    return data["artifacts"]


def download_artifact_to_dir(repo: str, artifact_name: str, target_dir: str) -> bool:
    """Download and extract artifact directly to target directory.

    Args:
        repo: Repository in owner/repo format
        artifact_name: Name of the artifact to download
        target_dir: Directory to extract artifact contents to

    Returns:
        True if download succeeded, False otherwise.
    """
    cmd = ["gh", "run", "download", "-R", repo, "-n", artifact_name, "-D", target_dir]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def extract_failure_count_from_dir(dir_path) -> int | None:
    """Extract failure count from files in an extracted artifact directory.

    Handles both direct JSON files and nested ZIP files (blob reports).

    Args:
        dir_path: Path to the extracted artifact directory

    Returns:
        Number of failures found, or None if no stats found.
    """
    import zipfile
    from pathlib import Path

    dir_path = Path(dir_path)

    # First, check nested ZIP files (blob reports)
    for zip_file in dir_path.glob("*.zip"):
        try:
            with zipfile.ZipFile(zip_file) as zf:
                for name in zf.namelist():
                    if name.endswith(".json"):
                        content = zf.read(name)
                        data = json.loads(content)
                        failures = _extract_failure_count(data)
                        if failures is not None:
                            return failures
        except (zipfile.BadZipFile, json.JSONDecodeError):
            continue

    # Then check direct JSON files
    for json_file in dir_path.rglob("*.json"):
        try:
            data = json.loads(json_file.read_text())
            failures = _extract_failure_count(data)
            if failures is not None:
                return failures
        except (json.JSONDecodeError, OSError):
            continue

    return None


def gh_artifact_download(repo: str, artifact_name: str) -> bytes | None:
    """Download artifact content via gh CLI.

    DEPRECATED: Use download_artifact_to_dir instead for better performance.

    Returns raw bytes of the artifact ZIP, or None on failure.
    """
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = ["gh", "run", "download", "-R", repo, "-n", artifact_name, "-D", tmpdir]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            # gh extracts the zip, so we need to re-zip the contents
            import io
            import zipfile

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for file_path in Path(tmpdir).rglob("*"):
                    if file_path.is_file():
                        arcname = str(file_path.relative_to(tmpdir))
                        zf.write(file_path, arcname)
            return zip_buffer.getvalue()
        except subprocess.CalledProcessError:
            return None


# =============================================================================
# DOMAIN LOGIC (Validation & Analysis)
# =============================================================================


def is_playwright_artifact(name: str) -> bool:
    """Check if artifact name suggests Playwright report."""
    return bool(_PLAYWRIGHT_REGEX.search(name))


def download_and_check_failures(repo: str, run_id: str, artifact_name: str) -> int | None:
    """Download artifact and extract failure count.

    Uses optimized direct file reading instead of re-zipping.

    Returns:
        Number of failures found, or None if download/parsing failed.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        if not download_artifact_to_dir(repo, artifact_name, tmpdir):
            return None

        return extract_failure_count_from_dir(tmpdir)


def _extract_failure_count(data: dict) -> int | None:
    """Extract failure count from Playwright report data."""
    if not isinstance(data, dict):
        return None

    stats = data.get("stats", {})
    if not stats:
        return None

    # Playwright JSON reporter format: unexpected, flaky
    if "unexpected" in stats:
        return stats.get("unexpected", 0) + stats.get("flaky", 0)

    # Playwright blob/JSONL format: failed
    if "failed" in stats:
        return stats.get("failed", 0)

    return None


def verify_has_failures(repo: str, run_id: str, artifact_name: str) -> bool:
    """Verify that an artifact contains actual test failures.

    Downloads the artifact and checks if it has non-zero failure count.
    """
    failure_count = download_and_check_failures(repo, run_id, artifact_name)
    return failure_count is not None and failure_count > 0


def filter_expired_artifacts(artifacts: list[dict]) -> list[str]:
    """Filter out expired artifacts, return names of valid ones."""
    return [a["name"] for a in artifacts if not a.get("expired", False)]


def find_valid_artifacts(repo: str) -> tuple[str | None, str | None, list[str], str | None]:
    """Find valid (non-expired) Playwright artifacts from recent failed runs.

    Prioritizes runs with Playwright artifacts over runs with other artifacts.

    Returns:
        Tuple of (run_id, run_url, artifact_names, run_created_at) for first run
        with Playwright artifacts, or first run with any artifacts,
        or (first_run_id, first_run_url, [], run_created_at) if none.
    """
    runs = get_failed_runs(repo)
    if not runs:
        return None, None, [], None

    # First pass: look for runs with Playwright artifacts
    for run in runs:
        run_id = str(run["id"])
        run_url = run.get("html_url", "")
        run_created_at = run.get("created_at")

        artifacts = get_run_artifacts(repo, run_id)
        valid_names = filter_expired_artifacts(artifacts)
        playwright_names = [a for a in valid_names if is_playwright_artifact(a)]

        if playwright_names:
            return run_id, run_url, valid_names, run_created_at

    # Second pass: return first run with any artifacts
    for run in runs:
        run_id = str(run["id"])
        run_url = run.get("html_url", "")
        run_created_at = run.get("created_at")

        artifacts = get_run_artifacts(repo, run_id)
        valid_names = filter_expired_artifacts(artifacts)

        if valid_names:
            return run_id, run_url, valid_names, run_created_at

    # No artifacts found, return first run info
    first_run = runs[0]
    return str(first_run["id"]), first_run.get("html_url", ""), [], first_run.get("created_at")


def determine_status(
    run_id: str | None,
    artifact_names: list[str],
    playwright_artifacts: list[str],
    failure_count: int | None = None,
) -> SourceStatus:
    """Determine the status of a source based on its data.

    Args:
        run_id: Workflow run ID
        artifact_names: All artifact names
        playwright_artifacts: Playwright-specific artifact names
        failure_count: Number of test failures (None = not verified)
    """
    if not run_id:
        return SourceStatus.NO_FAILED_RUNS
    if not artifact_names:
        return SourceStatus.NO_ARTIFACTS
    if not playwright_artifacts:
        return SourceStatus.HAS_ARTIFACTS
    # If failure_count was verified and is 0, mark as NO_FAILURES
    if failure_count is not None and failure_count == 0:
        return SourceStatus.NO_FAILURES
    return SourceStatus.COMPATIBLE


def analyze_source_with_status(
    repo: str,
    stars: int | None = None,
    verify_failures: bool = False,
    on_status: callable | None = None,
    cache: RunCache | None = None,
) -> ProjectSource:
    """Analyze a repository with status updates for each stage.

    Args:
        repo: Repository in owner/repo format
        stars: Star count (fetched if None)
        verify_failures: If True, download artifact to verify it has failures
        on_status: Optional callback(stage_description) for status updates
        cache: Optional RunCache for caching verification results

    Returns:
        ProjectSource with analysis results
    """

    def report(stage: str) -> None:
        if on_status:
            on_status(stage)

    report("Fetching repo info...")

    if stars is None:
        stars = get_repo_stars(repo)

    report("Fetching failed runs...")

    run_id, run_url, artifact_names, run_created_at = find_valid_artifacts(repo)
    playwright_artifacts = [a for a in artifact_names if is_playwright_artifact(a)]

    # Optionally verify that artifact has actual failures
    failure_count = None
    if verify_failures and playwright_artifacts and run_id:
        # Skip verification for KNOWN_GOOD_REPOS (they're trusted to have failures)
        if repo in KNOWN_GOOD_REPOS:
            failure_count = 1  # Trust that it has failures
        else:
            report(
                "Downloading artifact..."
                if not cache or not cache.get(run_id)
                else "Checking cache..."
            )
            # Try the first Playwright artifact
            if cache and run_created_at:
                has_failures = verify_has_failures_cached(
                    repo, run_id, playwright_artifacts[0], cache, run_created_at
                )
            else:
                has_failures = verify_has_failures(repo, run_id, playwright_artifacts[0])
            failure_count = 1 if has_failures else 0

    status = determine_status(run_id, artifact_names, playwright_artifacts, failure_count)

    return ProjectSource(
        repo=repo,
        stars=stars,
        status=status,
        artifact_names=artifact_names,
        playwright_artifacts=playwright_artifacts,
        run_id=run_id,
        run_url=run_url,
    )


def analyze_source(
    repo: str,
    stars: int | None = None,
    verify_failures: bool = False,
) -> ProjectSource:
    """Analyze a repository as a source for testing.

    Args:
        repo: Repository in owner/repo format
        stars: Star count (fetched if None)
        verify_failures: If True, download artifact to verify it has failures
    """
    if stars is None:
        stars = get_repo_stars(repo)

    run_id, run_url, artifact_names, run_created_at = find_valid_artifacts(repo)
    playwright_artifacts = [a for a in artifact_names if is_playwright_artifact(a)]

    # Optionally verify that artifact has actual failures
    failure_count = None
    if verify_failures and playwright_artifacts and run_id:
        # Skip verification for KNOWN_GOOD_REPOS (they're trusted to have failures)
        # This avoids downloading massive artifacts (50-200MB) for microsoft/playwright
        if repo in KNOWN_GOOD_REPOS:
            failure_count = 1  # Trust that it has failures
        else:
            # Try the first Playwright artifact
            has_failures = verify_has_failures(repo, run_id, playwright_artifacts[0])
            failure_count = 1 if has_failures else 0

    status = determine_status(run_id, artifact_names, playwright_artifacts, failure_count)

    return ProjectSource(
        repo=repo,
        stars=stars,
        status=status,
        artifact_names=artifact_names,
        playwright_artifacts=playwright_artifacts,
        run_id=run_id,
        run_url=run_url,
    )


def filter_by_min_stars(sources: list[ProjectSource], min_stars: int = 100) -> list[ProjectSource]:
    """Filter sources by minimum star count."""
    return [c for c in sources if c.stars >= min_stars]


def sort_sources(sources: list[ProjectSource]) -> list[ProjectSource]:
    """Sort sources by compatibility (desc), then stars (desc)."""
    return sorted(sources, key=lambda c: (-c.compatible, -c.stars))


# =============================================================================
# DISCOVERY ORCHESTRATION
# =============================================================================


_USE_DEFAULT_CACHE = object()  # Sentinel for "use default cache path"


def discover_sources(
    global_limit: int = 30,
    min_stars: int = 100,
    queries: list[str] | None = None,
    verify_failures: bool = False,
    on_progress: callable | None = None,
    show_progress: bool = False,
    cache_path: str | None | object = _USE_DEFAULT_CACHE,
) -> list[ProjectSource]:
    """Discover source projects from GitHub.

    Args:
        global_limit: Maximum total repos to analyze across all queries
        min_stars: Minimum star count to include
        queries: Custom search queries (uses DEFAULT_QUERIES if None)
        verify_failures: If True, download artifacts to verify they have failures
        on_progress: Optional callback(ProgressInfo) for progress updates (legacy)
        show_progress: If True, show Rich progress display with spinners
        cache_path: Path to cache file for verified runs. Default uses
            ~/.cache/heisenberg/verified_runs.json. Set to None to disable caching.

    Returns:
        List of analyzed ProjectSource objects, sorted by compatibility
    """
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if queries is None:
        queries = DEFAULT_QUERIES

    # Determine cache path: default, explicit path, or disabled (None)
    actual_cache_path = None
    if verify_failures:
        if cache_path is _USE_DEFAULT_CACHE:
            actual_cache_path = get_default_cache_path()
        elif cache_path is not None:
            actual_cache_path = cache_path

    # Initialize verification cache (with 90-day TTL based on run creation time)
    cache = RunCache(cache_path=actual_cache_path) if actual_cache_path else None

    # Start with known good repos (high probability of having failures)
    all_repos: set[str] = set(KNOWN_GOOD_REPOS)

    # Add repos from search queries
    for query in queries:
        results = search_repos(query, limit=global_limit)
        all_repos.update(results)
        if len(all_repos) >= global_limit:
            break

    repos_to_analyze = list(all_repos)[:global_limit]
    total = len(repos_to_analyze)
    sources: list[ProjectSource] = []

    # Thread-safe counter for sequential completion numbers
    completion_counter = [0]  # Use list to allow mutation in nested function
    counter_lock = threading.Lock()

    # Rich progress display (if enabled)
    progress = create_progress_display() if show_progress else None
    task_ids: dict[str, int] = {}  # repo -> task_id mapping

    def analyze_with_progress(repo: str) -> ProjectSource | None:
        """Analyze a repo and report progress."""
        start_time = time.time()
        result = None
        message = None

        def on_status(stage: str) -> None:
            """Update Rich progress with current stage."""
            if progress and repo in task_ids:
                # Use Rich markup: repo in cyan, stage in dim
                progress.update(
                    task_ids[repo],
                    description=f"⏳ [cyan]{repo}[/cyan] [dim]│[/dim] {stage}",
                )

        try:
            # Check if this is a known good repo (for message)
            if verify_failures and repo in KNOWN_GOOD_REPOS:
                message = "skipped verify"

            result = analyze_source_with_status(
                repo,
                verify_failures=verify_failures,
                on_status=on_status if progress else None,
                cache=cache,
            )
        except Exception:
            pass

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Update Rich progress (mark task complete)
        if progress and repo in task_ids:
            is_compatible = result and result.status == SourceStatus.COMPATIBLE
            status_icon = "[green]✓[/green]" if is_compatible else "[red]✗[/red]"
            status_text = result.status.value if result else "error"
            time_str = f"{elapsed_ms / 1000:.1f}s" if elapsed_ms >= 1000 else f"{elapsed_ms}ms"
            extra = f" [dim]({message})[/dim]" if message else ""
            progress.update(
                task_ids[repo],
                description=f"{status_icon} [cyan]{repo}[/cyan] [dim]│[/dim] {status_text} [dim]{time_str}[/dim]{extra}",
                completed=1,
            )

        # Legacy callback support
        if on_progress:
            status = result.status.value if result else "error"

            with counter_lock:
                completion_counter[0] += 1
                completed = completion_counter[0]

                info = ProgressInfo(
                    completed=completed,
                    total=total,
                    repo=repo,
                    status=status,
                    elapsed_ms=elapsed_ms,
                    message=message,
                )
                on_progress(info)

        return result

    def run_discovery():
        """Run the actual discovery with ThreadPoolExecutor."""
        nonlocal sources

        # Add tasks to Rich progress (shows spinner while running)
        if progress:
            for repo in repos_to_analyze:
                task_id = progress.add_task(
                    f"⏳ [cyan]{repo}[/cyan] [dim]│[/dim] Waiting...",
                    total=1,
                )
                task_ids[repo] = task_id

        # Use parallel processing for faster execution
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(analyze_with_progress, repo): repo for repo in repos_to_analyze
            }

            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    sources.append(result)

    # Run with or without Rich progress context
    if progress:
        with progress:
            run_discovery()
    else:
        run_discovery()

    # Save verification cache to disk
    if cache:
        cache.save()

    # Filter and sort
    sources = filter_by_min_stars(sources, min_stars=min_stars)
    sources = sort_sources(sources)

    return sources


# =============================================================================
# PRESENTER (CLI Output Formatting)
# =============================================================================


def create_progress_display():
    """Create a Rich Progress display for tracking repo analysis.

    Returns a Progress object with spinner for active tasks.
    """
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        transient=False,  # Keep completed tasks visible
    )


def format_progress_line(info: ProgressInfo) -> str:
    """Format a progress line for CLI output.

    Args:
        info: ProgressInfo with completion details

    Returns:
        Formatted string like "[ 3/10] ✓ owner/repo (1.5s)"
    """
    # Status icon
    icon = "✓" if info.status == "compatible" else "✗"

    # Format elapsed time
    if info.elapsed_ms >= 1000:
        time_str = f"{info.elapsed_ms / 1000:.1f}s"
    else:
        time_str = f"{info.elapsed_ms}ms"

    # Base line
    line = f"[{info.completed:2}/{info.total}] {icon} {info.repo} ({time_str})"

    # Add optional message
    if info.message:
        line += f" - {info.message}"

    return line


def format_status_icon(status: SourceStatus) -> str:
    """Get the icon for a source status."""
    icons = {
        SourceStatus.COMPATIBLE: "✅",
        SourceStatus.NO_FAILURES: "🟡",
        SourceStatus.HAS_ARTIFACTS: "⚠️ ",
        SourceStatus.NO_ARTIFACTS: "❌",
        SourceStatus.NO_FAILED_RUNS: "⏭️ ",
    }
    return icons.get(status, "?")


def format_status_detail(source: ProjectSource) -> str:
    """Format the detail text for a source's status."""
    if source.status == SourceStatus.COMPATIBLE:
        artifacts = ", ".join(source.playwright_artifacts[:3])
        return f"{source.stars:>5}⭐ ✓ {artifacts}"
    elif source.status == SourceStatus.NO_FAILURES:
        return "0 test failures (tests passed)"
    elif source.status == SourceStatus.HAS_ARTIFACTS:
        artifacts = ", ".join(source.artifact_names[:3])
        return f"Artifacts: {artifacts}"
    elif source.status == SourceStatus.NO_ARTIFACTS:
        return "No artifacts"
    else:
        return "No failed runs"


def print_source_line(
    source: ProjectSource,
    index: int,
    total: int,
    out: TextIO = sys.stdout,
) -> None:
    """Print a single source line."""
    icon = format_status_icon(source.status)
    detail = format_status_detail(source)
    print(f"  [{index:2}/{total}] {source.repo:<45} {icon} {detail}", file=out)


def print_summary(
    sources: list[ProjectSource],
    min_stars: int,
    out: TextIO = sys.stdout,
) -> None:
    """Print the analysis summary."""
    compatible_count = sum(1 for c in sources if c.compatible)

    print(f"📋 Analyzed {len(sources)} repositories (min {min_stars}⭐)", file=out)
    print("🔬 Results:\n", file=out)

    for i, source in enumerate(sources, 1):
        print_source_line(source, i, len(sources), out)

    print(f"\n{'=' * 70}", file=out)
    print(f"📊 Results: {compatible_count} compatible / {len(sources)} checked", file=out)
    print(f"{'=' * 70}\n", file=out)


def print_compatible_projects(
    sources: list[ProjectSource],
    out: TextIO = sys.stdout,
) -> None:
    """Print details of compatible projects."""
    compatible = [c for c in sources if c.compatible]
    if not compatible:
        return

    print("🎯 Compatible Projects (ready for Heisenberg):\n", file=out)
    for c in compatible:
        print(f"  ⭐ {c.stars:>6} | {c.repo}", file=out)
        print(f"            Artifacts: {', '.join(c.artifact_names[:5])}", file=out)
        if c.run_url:
            print(f"            Run: {c.run_url}", file=out)
        print(file=out)


def save_results(sources: list[ProjectSource], output_path: str) -> None:
    """Save results to JSON file."""
    output_data = [
        {
            "repo": c.repo,
            "stars": c.stars,
            "compatible": c.compatible,
            "status": c.status.value,
            "artifacts": c.artifact_names,
            "playwright_artifacts": c.playwright_artifacts,
            "run_id": c.run_id,
            "run_url": c.run_url,
        }
        for c in sources
    ]
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"💾 Results saved to {output_path}")


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser for CLI."""
    parser = argparse.ArgumentParser(description="Discover projects for Heisenberg testing")
    parser.add_argument("--min-stars", type=int, default=100, help="Minimum stars")
    parser.add_argument("--limit", type=int, default=30, help="Max repos to analyze (global)")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Download artifacts to verify they have actual failures (slower)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        dest="no_cache",
        help="Disable verification cache (force re-download of artifacts)",
    )
    return parser


def main() -> None:
    """Main entry point for CLI."""
    parser = create_argument_parser()
    args = parser.parse_args()

    print("🔍 Searching GitHub for Playwright projects with artifacts...\n")
    if args.verify:
        cache_info = " (cache disabled)" if args.no_cache else ""
        print(
            f"📦 Verification enabled - downloading artifacts to check for failures{cache_info}\n"
        )

    # Determine cache_path: None to disable, or use default
    cache_path = None if args.no_cache else _USE_DEFAULT_CACHE

    sources = discover_sources(
        global_limit=args.limit,
        min_stars=args.min_stars,
        verify_failures=args.verify,
        show_progress=True,  # Use Rich progress display
        cache_path=cache_path,
    )

    print_summary(sources, args.min_stars)
    print_compatible_projects(sources)

    if args.output:
        save_results(sources, args.output)


if __name__ == "__main__":
    main()
