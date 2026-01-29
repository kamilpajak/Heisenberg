"""Discovery orchestration — coordinates search, analysis, and progress display."""

from __future__ import annotations

from .analysis import analyze_source_with_status, sort_sources
from .cache import QuarantineCache, RunCache, get_default_cache_path, get_default_quarantine_path
from .client import search_repos
from .models import (
    DEFAULT_QUERIES,
    ProgressInfo,
    ProjectSource,
    SourceStatus,
)
from .ui import (
    COL_REPO,
    COL_STATUS,
    create_progress_display,
    format_status_color,
    format_status_icon,
    format_status_label,
)

_USE_DEFAULT_CACHE = object()  # Sentinel for "use default cache path"
_USE_DEFAULT_QUARANTINE = object()  # Sentinel for "use default quarantine path"

# Statuses that should be quarantined (not worth re-checking)
_QUARANTINE_STATUSES = frozenset(
    {
        SourceStatus.NO_ARTIFACTS,
        SourceStatus.NO_FAILED_RUNS,
        SourceStatus.HAS_ARTIFACTS,
        SourceStatus.NO_FAILURES,
    }
)


def _resolve_cache_path(cache_path: str | None | object, verify_failures: bool) -> str | None:
    """Resolve cache path from sentinel, explicit path, or None."""
    if not verify_failures:
        return None
    if cache_path is _USE_DEFAULT_CACHE:
        return get_default_cache_path()
    if cache_path is not None:
        return cache_path
    return None


def _resolve_quarantine_path(quarantine_path: str | None | object) -> str | None:
    """Resolve quarantine path from sentinel, explicit path, or None."""
    if quarantine_path is _USE_DEFAULT_QUARANTINE:
        return get_default_quarantine_path()
    if quarantine_path is not None:
        return quarantine_path
    return None


def _collect_repos_from_queries(
    queries: list[str],
    global_limit: int,
    quarantine: QuarantineCache | None,
) -> tuple[list[str], int]:
    """Collect repos from search queries, skipping quarantined ones.

    Returns tuple of (repos_to_analyze, quarantine_skipped_count).
    """
    all_repos: set[str] = set()
    quarantine_skipped = 0

    for query in queries:
        results = search_repos(query, limit=global_limit)
        for repo in results:
            if quarantine and quarantine.is_quarantined(repo):
                quarantine_skipped += 1
            else:
                all_repos.add(repo)
        if len(all_repos) >= global_limit:
            break

    return list(all_repos)[:global_limit], quarantine_skipped


def _update_quarantine(quarantine: QuarantineCache | None, result: ProjectSource | None) -> None:
    """Update quarantine cache based on analysis result."""
    if not quarantine or not result:
        return
    if result.status == SourceStatus.COMPATIBLE:
        quarantine.remove(result.repo)
    elif result.status in _QUARANTINE_STATUSES:
        quarantine.set(result.repo, result.status.value)


def _format_waiting_description(repo: str) -> str:
    """Format Rich progress description for waiting state."""
    return (
        f"[dim].[/dim] [cyan]{repo:<{COL_REPO}}[/cyan]"
        f" [dim]\u2502[/dim] [dim]{'waiting...':<{COL_STATUS}}[/dim]"
    )


def _format_stage_description(repo: str, stage: str) -> str:
    """Format Rich progress description for in-progress state."""
    stage_display = (stage[: COL_STATUS - 1] + "\u2026") if len(stage) > COL_STATUS else stage
    return (
        f"[dim].[/dim] [cyan]{repo:<{COL_REPO}}[/cyan]"
        f" [dim]\u2502[/dim] [dim]{stage_display:<{COL_STATUS}}[/dim]"
    )


def _format_complete_description(
    repo: str, result: ProjectSource | None, message: str | None
) -> str:
    """Format Rich progress description for completed state."""
    icon = format_status_icon(result.status) if result else "?"
    color = format_status_color(result.status) if result else "white"
    status_text = format_status_label(result.status) if result else "error"
    extra = f" [dim]({message})[/dim]" if message else ""
    return (
        f"[{color}]{icon}[/{color}] [cyan]{repo:<{COL_REPO}}[/cyan]"
        f" [dim]\u2502[/dim] [{color}]{status_text:<{COL_STATUS}}[/{color}]"
        f"{extra}"
    )


def discover_sources(
    global_limit: int = 30,
    queries: list[str] | None = None,
    verify_failures: bool = False,
    on_progress: callable | None = None,
    show_progress: bool = False,
    cache_path: str | None | object = _USE_DEFAULT_CACHE,
    quarantine_path: str | None | object = _USE_DEFAULT_QUARANTINE,
) -> list[ProjectSource]:
    """Discover source projects from GitHub.

    Args:
        global_limit: Maximum total repos to analyze across all queries
        queries: Custom search queries (uses DEFAULT_QUERIES if None)
        verify_failures: If True, download artifacts to verify they have failures
        on_progress: Optional callback(ProgressInfo) for progress updates (legacy)
        show_progress: If True, show Rich progress display with spinners
        cache_path: Path to cache file for verified runs. Set to None to disable.
        quarantine_path: Path to quarantine cache file. Set to None to disable.

    Returns:
        List of analyzed ProjectSource objects, sorted by compatibility
    """
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    queries = queries or DEFAULT_QUERIES

    # Initialize caches
    actual_cache_path = _resolve_cache_path(cache_path, verify_failures)
    cache = RunCache(cache_path=actual_cache_path) if actual_cache_path else None

    actual_quarantine_path = _resolve_quarantine_path(quarantine_path)
    quarantine = (
        QuarantineCache(cache_path=actual_quarantine_path) if actual_quarantine_path else None
    )

    # Collect repos to analyze
    repos_to_analyze, quarantine_skipped = _collect_repos_from_queries(
        queries, global_limit, quarantine
    )

    if show_progress and quarantine_skipped > 0:
        print(f"  ({quarantine_skipped} repos quarantined, analyzing {len(repos_to_analyze)})\n")

    total = len(repos_to_analyze)
    sources: list[ProjectSource] = []

    # Thread-safe counter for sequential completion numbers
    completion_counter = [0]
    counter_lock = threading.Lock()

    # Rich progress display (if enabled)
    progress = create_progress_display() if show_progress else None
    task_ids: dict[str, int] = {}

    def analyze_with_progress(repo: str) -> ProjectSource | None:
        """Analyze a repo and report progress."""
        start_time = time.time()
        result = None
        message = None

        if progress and repo in task_ids:
            progress.start_task(task_ids[repo])

        def on_status(stage: str) -> None:
            if progress and repo in task_ids:
                progress.update(task_ids[repo], description=_format_stage_description(repo, stage))

        try:
            result = analyze_source_with_status(
                repo,
                verify_failures=verify_failures,
                on_status=on_status if progress else None,
                cache=cache,
            )
            _update_quarantine(quarantine, result)
        except Exception:
            pass

        elapsed_ms = int((time.time() - start_time) * 1000)

        if progress and repo in task_ids:
            progress.update(
                task_ids[repo],
                description=_format_complete_description(repo, result, message),
                completed=1,
            )

        if on_progress:
            status = result.status.value if result else "error"
            with counter_lock:
                completion_counter[0] += 1
                info = ProgressInfo(
                    completed=completion_counter[0],
                    total=total,
                    repo=repo,
                    status=status,
                    elapsed_ms=elapsed_ms,
                    message=message,
                )
                on_progress(info)

        return result

    def run_discovery() -> None:
        """Run the actual discovery with ThreadPoolExecutor."""
        nonlocal sources

        if progress:
            for repo in repos_to_analyze:
                task_id = progress.add_task(_format_waiting_description(repo), total=1, start=False)
                task_ids[repo] = task_id

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(analyze_with_progress, repo): repo for repo in repos_to_analyze
            }
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    sources.append(result)

    if progress:
        with progress:
            run_discovery()
    else:
        run_discovery()

    if cache:
        cache.save()

    return sort_sources(sources)
