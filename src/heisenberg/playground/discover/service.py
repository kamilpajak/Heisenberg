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
        cache_path: Path to cache file for verified runs. Default uses
            ~/.cache/heisenberg/verified_runs.json. Set to None to disable caching.
        quarantine_path: Path to quarantine cache file. Default uses
            ~/.cache/heisenberg/quarantined_repos.json. Set to None to disable.

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

    # Initialize quarantine cache (24-hour wall-clock TTL)
    actual_quarantine_path = None
    if quarantine_path is _USE_DEFAULT_QUARANTINE:
        actual_quarantine_path = get_default_quarantine_path()
    elif quarantine_path is not None:
        actual_quarantine_path = quarantine_path
    quarantine = (
        QuarantineCache(cache_path=actual_quarantine_path) if actual_quarantine_path else None
    )

    all_repos: set[str] = set()

    # Add repos from search queries, skipping quarantined repos so the
    # limit is filled with fresh (non-quarantined) repos instead.
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

    repos_to_analyze = list(all_repos)[:global_limit]

    if show_progress and quarantine_skipped > 0:
        print(f"  ({quarantine_skipped} repos quarantined, analyzing {len(repos_to_analyze)})\n")

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

        # Start the Rich timer for this task (was created with start=False)
        if progress and repo in task_ids:
            progress.start_task(task_ids[repo])

        def on_status(stage: str) -> None:
            """Update Rich progress with current stage."""
            if progress and repo in task_ids:
                stage_display = (
                    (stage[: COL_STATUS - 1] + "\u2026") if len(stage) > COL_STATUS else stage
                )
                progress.update(
                    task_ids[repo],
                    description=(
                        f"[dim].[/dim] [cyan]{repo:<{COL_REPO}}[/cyan]"
                        f" [dim]\u2502[/dim] [dim]{stage_display:<{COL_STATUS}}[/dim]"
                    ),
                )

        try:
            result = analyze_source_with_status(
                repo,
                verify_failures=verify_failures,
                on_status=on_status if progress else None,
                cache=cache,
            )

            # Update quarantine based on analysis result
            if quarantine and result:
                if result.status == SourceStatus.COMPATIBLE:
                    quarantine.remove(repo)
                elif result.status in (
                    SourceStatus.NO_ARTIFACTS,
                    SourceStatus.NO_FAILED_RUNS,
                    SourceStatus.HAS_ARTIFACTS,
                    SourceStatus.NO_FAILURES,
                ):
                    quarantine.set(repo, result.status.value)
        except Exception:
            pass

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Update Rich progress (mark task complete — stops TimeElapsedColumn)
        if progress and repo in task_ids:
            icon = format_status_icon(result.status) if result else "?"
            color = format_status_color(result.status) if result else "white"
            status_text = format_status_label(result.status) if result else "error"
            extra = f" [dim]({message})[/dim]" if message else ""
            progress.update(
                task_ids[repo],
                description=(
                    f"[{color}]{icon}[/{color}] [cyan]{repo:<{COL_REPO}}[/cyan]"
                    f" [dim]\u2502[/dim] [{color}]{status_text:<{COL_STATUS}}[/{color}]"
                    f"{extra}"
                ),
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
                    (
                        f"[dim].[/dim] [cyan]{repo:<{COL_REPO}}[/cyan]"
                        f" [dim]\u2502[/dim] [dim]{'waiting...':<{COL_STATUS}}[/dim]"
                    ),
                    total=1,
                    start=False,
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

    # Sort (filtering is caller's responsibility)
    sources = sort_sources(sources)

    return sources
