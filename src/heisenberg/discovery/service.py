"""Discovery orchestration — coordinates search, analysis, and event emission."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from .analysis import analyze_source_with_status, sort_sources
from .cache import QuarantineCache, RunCache, get_default_cache_path, get_default_quarantine_path
from .client import fetch_stars_batch, search_repos
from .events import (
    AnalysisCompleted,
    AnalysisStarted,
    DiscoveryCompleted,
    DiscoveryEvent,
    EventHandler,
    QueryCompleted,
    SearchCompleted,
    SearchStarted,
)
from .models import (
    DEFAULT_QUERIES,
    ProjectSource,
    SourceStatus,
)

logger = logging.getLogger(__name__)

_USE_DEFAULT_CACHE = object()  # Sentinel for "use default cache path"
_USE_DEFAULT_QUARANTINE = object()  # Sentinel for "use default quarantine path"

# Statuses that should be quarantined (not worth re-checking)
# Note: RATE_LIMITED is NOT quarantined - it should be retried later
_QUARANTINE_STATUSES = frozenset(
    {
        SourceStatus.NO_ARTIFACTS,
        SourceStatus.NO_FAILED_RUNS,
        SourceStatus.HAS_ARTIFACTS,
        SourceStatus.NO_FAILURES,
        SourceStatus.UNSUPPORTED_FORMAT,
    }
)


def _resolve_cache_path(cache_path: str | None | object, verify_failures: bool) -> str | None:
    """Resolve cache path from sentinel, explicit path, or None."""
    if not verify_failures:
        return None
    if cache_path is _USE_DEFAULT_CACHE:
        return get_default_cache_path()
    if cache_path is None:
        return None
    try:
        return os.fspath(cache_path)  # type: ignore[arg-type]
    except TypeError:
        return None


def _resolve_quarantine_path(quarantine_path: str | None | object) -> str | None:
    """Resolve quarantine path from sentinel, explicit path, or None."""
    if quarantine_path is _USE_DEFAULT_QUARANTINE:
        return get_default_quarantine_path()
    if quarantine_path is None:
        return None
    try:
        return os.fspath(quarantine_path)  # type: ignore[arg-type]
    except TypeError:
        return None


def _emit(handler: EventHandler | None, event: DiscoveryEvent) -> None:
    """Emit event to handler if present."""
    if handler:
        handler(event)


def _collect_repos_from_queries(
    queries: list[str],
    global_limit: int,
    quarantine: QuarantineCache | None,
    min_stars: int,
    on_event: EventHandler | None,
) -> tuple[list[tuple[str, int]], int, int]:
    """Collect repos from search queries, skipping quarantined and low-star ones.

    When min_stars > 0, fetches real star counts via Repository API (Code Search
    API doesn't return stars). This is lazy - no fetch when min_stars = 0.

    Emits QueryCompleted events for each query.

    Returns:
        Tuple of (repos_with_stars, quarantine_skipped, stars_filtered)
        where repos_with_stars is list of (repo, stars) tuples.
    """
    # Phase 1: Collect repos from queries, filtering only by quarantine
    all_repos: set[str] = set()
    quarantine_skipped = 0

    for query_idx, query in enumerate(queries):
        repos_before = len(all_repos)
        results = search_repos(query, limit=global_limit)

        for repo, _ in results:  # Ignore stars from Code Search (always 0)
            if repo in all_repos:
                continue
            if quarantine and quarantine.is_quarantined(repo):
                quarantine_skipped += 1
            else:
                all_repos.add(repo)

        new_repos = len(all_repos) - repos_before
        query_preview = query[:40] if len(query) <= 40 else query[:37] + "..."

        _emit(
            on_event,
            QueryCompleted(
                query_index=query_idx,
                query_preview=query_preview,
                repos_found=len(results),
                new_repos=new_repos,
            ),
        )

        if len(all_repos) >= global_limit:
            break

    # Phase 2: Fetch real stars if min_stars filter is active (lazy loading)
    stars_filtered = 0
    if min_stars > 0 and all_repos:
        stars_map = fetch_stars_batch(list(all_repos))
        # Filter by min_stars using real star counts
        repos_with_stars: dict[str, int] = {}
        for repo, stars in stars_map.items():
            if stars >= min_stars:
                repos_with_stars[repo] = stars
            else:
                stars_filtered += 1
    else:
        # No min_stars filter - use 0 as placeholder (stars not needed)
        repos_with_stars = dict.fromkeys(all_repos, 0)

    repos_list = list(repos_with_stars.items())[:global_limit]
    return repos_list, quarantine_skipped, stars_filtered


def _update_quarantine(quarantine: QuarantineCache | None, result: ProjectSource | None) -> None:
    """Update quarantine cache based on analysis result."""
    if not quarantine or not result:
        return
    if result.status == SourceStatus.COMPATIBLE:
        quarantine.remove(result.repo)
    elif result.status in _QUARANTINE_STATUSES:
        quarantine.set(result.repo, result.status.value)


@dataclass
class _DiscoveryRunner:
    """Encapsulates state and methods for running discovery."""

    repos: list[tuple[str, int]]  # (repo_name, stars) tuples
    verify_failures: bool
    cache: RunCache | None
    quarantine: QuarantineCache | None
    on_event: EventHandler | None

    # Mutable state
    sources: list[ProjectSource] = field(default_factory=list)
    completion_counter: list[int] = field(default_factory=lambda: [0])
    counter_lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def total(self) -> int:
        return len(self.repos)

    def _emit_analysis_completed(
        self,
        repo: str,
        stars: int,
        result: ProjectSource | None,
        elapsed_ms: int,
        index: int,
    ) -> None:
        """Emit AnalysisCompleted event."""
        if not self.on_event:
            return

        status = result.status if result else SourceStatus.NO_ARTIFACTS
        artifact_name = (
            result.playwright_artifacts[0] if result and result.playwright_artifacts else None
        )

        with self.counter_lock:
            self.completion_counter[0] += 1
            event = AnalysisCompleted(
                repo=repo,
                stars=stars,
                status=status,
                artifact_name=artifact_name,
                failure_count=None,  # Not tracked currently
                cache_hit=False,  # Not tracked currently
                elapsed_ms=elapsed_ms,
                index=self.completion_counter[0] - 1,
                total=self.total,
            )
            self.on_event(event)

    def _emit_analysis_started(self, repo: str, stars: int, index: int) -> None:
        """Emit AnalysisStarted event."""
        if not self.on_event:
            return
        self.on_event(AnalysisStarted(repo=repo, stars=stars, index=index, total=self.total))

    def analyze_repo(self, repo: str, stars: int, index: int) -> ProjectSource | None:
        """Analyze a single repo and emit events."""
        self._emit_analysis_started(repo, stars, index)
        start_time = time.time()
        result = None

        try:
            result = analyze_source_with_status(
                repo,
                stars=stars,
                verify_failures=self.verify_failures,
                on_status=None,
                cache=self.cache,
            )
            _update_quarantine(self.quarantine, result)
        except Exception as e:  # noqa: S110  # NOSONAR - graceful degradation
            logger.debug("Analysis failed for %s: %s", repo, e)

        elapsed_ms = int((time.time() - start_time) * 1000)
        self._emit_analysis_completed(repo, stars, result, elapsed_ms, index)

        return result

    def run(self) -> None:
        """Run parallel discovery."""
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self.analyze_repo, repo, stars, idx): repo
                for idx, (repo, stars) in enumerate(self.repos)
            }
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    self.sources.append(result)


def discover_sources(
    global_limit: int = 30,
    queries: list[str] | None = None,
    verify_failures: bool = True,
    on_event: EventHandler | None = None,
    cache_path: str | None | object = _USE_DEFAULT_CACHE,
    quarantine_path: str | None | object = _USE_DEFAULT_QUARANTINE,
    min_stars: int = 0,
) -> list[ProjectSource]:
    """Discover source projects from GitHub.

    Args:
        global_limit: Maximum number of repos to analyze.
        queries: Search queries (defaults to DEFAULT_QUERIES).
        verify_failures: Download artifacts to verify actual failures (default: True).
        on_event: Event handler for UI updates.
        cache_path: Path to run cache, or None to disable.
        quarantine_path: Path to quarantine cache, or None to disable.
        min_stars: Minimum stars required (repos below this are filtered before analysis).

    Returns:
        List of ProjectSource objects sorted by compatibility and stars.
    """
    queries = queries or DEFAULT_QUERIES

    # Initialize caches
    actual_cache_path = _resolve_cache_path(cache_path, verify_failures)
    cache = RunCache(cache_path=actual_cache_path) if actual_cache_path else None

    actual_quarantine_path = _resolve_quarantine_path(quarantine_path)
    quarantine = (
        QuarantineCache(cache_path=actual_quarantine_path) if actual_quarantine_path else None
    )

    # Emit SearchStarted
    _emit(on_event, SearchStarted(total_queries=len(queries)))

    # Collect repos (filtering by min_stars happens here, emits QueryCompleted events)
    repos_to_analyze, quarantine_skipped, stars_filtered = _collect_repos_from_queries(
        queries, global_limit, quarantine, min_stars, on_event
    )

    # Calculate total candidates (repos we actually looked at)
    total_candidates = len(repos_to_analyze) + quarantine_skipped + stars_filtered

    # Emit SearchCompleted
    _emit(
        on_event,
        SearchCompleted(
            total_candidates=total_candidates,
            quarantine_skipped=quarantine_skipped,
            stars_filtered=stars_filtered,
            to_analyze=len(repos_to_analyze),
        ),
    )

    # Run discovery
    runner = _DiscoveryRunner(
        repos=repos_to_analyze,
        verify_failures=verify_failures,
        cache=cache,
        quarantine=quarantine,
        on_event=on_event,
    )

    runner.run()

    # Save cache
    if cache:
        cache.save()

    # Sort results
    sorted_sources = sort_sources(runner.sources)

    # Emit DiscoveryCompleted with stats
    stats: Counter[SourceStatus] = Counter()
    for source in sorted_sources:
        stats[source.status] += 1

    _emit(
        on_event,
        DiscoveryCompleted(
            results=sorted_sources,
            stats=dict(stats),
        ),
    )

    return sorted_sources
