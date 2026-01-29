"""Discovery orchestration — coordinates search, analysis, and progress display."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

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
    """Collect repos from search queries, skipping quarantined ones."""
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


@dataclass
class _DiscoveryRunner:
    """Encapsulates state and methods for running discovery."""

    repos: list[str]
    verify_failures: bool
    cache: RunCache | None
    quarantine: QuarantineCache | None
    progress: object | None  # Rich Progress or None
    on_progress: callable | None

    # Mutable state
    sources: list[ProjectSource] = field(default_factory=list)
    task_ids: dict[str, int] = field(default_factory=dict)
    completion_counter: list[int] = field(default_factory=lambda: [0])
    counter_lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def total(self) -> int:
        return len(self.repos)

    def _start_task(self, repo: str) -> None:
        """Start the Rich timer for a task."""
        if self.progress and repo in self.task_ids:
            self.progress.start_task(self.task_ids[repo])

    def _update_task_stage(self, repo: str, stage: str) -> None:
        """Update Rich progress with current stage."""
        if self.progress and repo in self.task_ids:
            self.progress.update(
                self.task_ids[repo], description=_format_stage_description(repo, stage)
            )

    def _complete_task(self, repo: str, result: ProjectSource | None, message: str | None) -> None:
        """Mark task as complete in Rich progress."""
        if self.progress and repo in self.task_ids:
            self.progress.update(
                self.task_ids[repo],
                description=_format_complete_description(repo, result, message),
                completed=1,
            )

    def _report_progress(
        self, repo: str, result: ProjectSource | None, elapsed_ms: int, message: str | None
    ) -> None:
        """Report progress via legacy callback."""
        if not self.on_progress:
            return
        status = result.status.value if result else "error"
        with self.counter_lock:
            self.completion_counter[0] += 1
            info = ProgressInfo(
                completed=self.completion_counter[0],
                total=self.total,
                repo=repo,
                status=status,
                elapsed_ms=elapsed_ms,
                message=message,
            )
            self.on_progress(info)

    def analyze_repo(self, repo: str) -> ProjectSource | None:
        """Analyze a single repo and report progress."""
        start_time = time.time()
        result = None
        message = None

        self._start_task(repo)

        def on_status(stage: str) -> None:
            self._update_task_stage(repo, stage)

        try:
            result = analyze_source_with_status(
                repo,
                verify_failures=self.verify_failures,
                on_status=on_status if self.progress else None,
                cache=self.cache,
            )
            _update_quarantine(self.quarantine, result)
        except Exception:
            pass

        elapsed_ms = int((time.time() - start_time) * 1000)
        self._complete_task(repo, result, message)
        self._report_progress(repo, result, elapsed_ms, message)

        return result

    def add_progress_tasks(self) -> None:
        """Add all repos as tasks to Rich progress."""
        if not self.progress:
            return
        for repo in self.repos:
            task_id = self.progress.add_task(
                _format_waiting_description(repo), total=1, start=False
            )
            self.task_ids[repo] = task_id

    def run(self) -> None:
        """Run parallel discovery."""
        self.add_progress_tasks()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(self.analyze_repo, repo): repo for repo in self.repos}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    self.sources.append(result)


def discover_sources(
    global_limit: int = 30,
    queries: list[str] | None = None,
    verify_failures: bool = False,
    on_progress: callable | None = None,
    show_progress: bool = False,
    cache_path: str | None | object = _USE_DEFAULT_CACHE,
    quarantine_path: str | None | object = _USE_DEFAULT_QUARANTINE,
) -> list[ProjectSource]:
    """Discover source projects from GitHub."""
    queries = queries or DEFAULT_QUERIES

    # Initialize caches
    actual_cache_path = _resolve_cache_path(cache_path, verify_failures)
    cache = RunCache(cache_path=actual_cache_path) if actual_cache_path else None

    actual_quarantine_path = _resolve_quarantine_path(quarantine_path)
    quarantine = (
        QuarantineCache(cache_path=actual_quarantine_path) if actual_quarantine_path else None
    )

    # Collect repos
    repos_to_analyze, quarantine_skipped = _collect_repos_from_queries(
        queries, global_limit, quarantine
    )

    if show_progress and quarantine_skipped > 0:
        print(f"  ({quarantine_skipped} repos quarantined, analyzing {len(repos_to_analyze)})\n")

    # Create progress display
    progress = create_progress_display() if show_progress else None

    # Run discovery
    runner = _DiscoveryRunner(
        repos=repos_to_analyze,
        verify_failures=verify_failures,
        cache=cache,
        quarantine=quarantine,
        progress=progress,
        on_progress=on_progress,
    )

    if progress:
        with progress:
            runner.run()
    else:
        runner.run()

    # Save cache
    if cache:
        cache.save()

    return sort_sources(runner.sources)
