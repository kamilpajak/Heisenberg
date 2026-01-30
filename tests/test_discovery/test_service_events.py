"""Tests for event emission in discovery service."""

from __future__ import annotations

from unittest.mock import patch

from heisenberg.discovery.events import (
    AnalysisCompleted,
    DiscoveryCompleted,
    DiscoveryEvent,
    QueryCompleted,
    SearchCompleted,
    SearchStarted,
)
from heisenberg.discovery.models import ProjectSource, SourceStatus


class TestSearchPhaseEvents:
    """Tests for search phase event emission."""

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_emits_search_started_event(self, mock_search, mock_analyze, _mock_sleep):
        """discover_sources should emit SearchStarted with query count."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = []
        events: list[DiscoveryEvent] = []

        discover_sources(
            global_limit=10,
            on_event=events.append,
        )

        search_started = [e for e in events if isinstance(e, SearchStarted)]
        assert len(search_started) == 1
        assert search_started[0].total_queries == 4  # DEFAULT_QUERIES has 4

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_emits_query_completed_events(self, mock_search, mock_analyze, _mock_sleep):
        """discover_sources should emit QueryCompleted for each query."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [("owner/repo", 1000)]
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )
        events: list[DiscoveryEvent] = []

        discover_sources(
            global_limit=10,
            on_event=events.append,
        )

        query_events = [e for e in events if isinstance(e, QueryCompleted)]
        assert len(query_events) == 4  # One per query

        # First query should have index 0
        assert query_events[0].query_index == 0
        assert query_events[0].repos_found >= 0

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_emits_search_completed_event(self, mock_search, mock_analyze, _mock_sleep):
        """discover_sources should emit SearchCompleted with filter stats."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [("owner/repo", 1000)]
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )
        events: list[DiscoveryEvent] = []

        discover_sources(
            global_limit=10,
            on_event=events.append,
        )

        search_completed = [e for e in events if isinstance(e, SearchCompleted)]
        assert len(search_completed) == 1
        assert search_completed[0].to_analyze >= 0


class TestAnalysisPhaseEvents:
    """Tests for analysis phase event emission."""

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_emits_analysis_completed_for_each_repo(self, mock_search, mock_analyze, _mock_sleep):
        """discover_sources should emit AnalysisCompleted for each repo."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [
            ("repo1", 1000),
            ("repo2", 2000),
        ]

        # Use function for side_effect to handle parallel execution correctly
        def analyze_side_effect(repo, **kwargs):
            if repo == "repo1":
                return ProjectSource(repo="repo1", stars=1000, status=SourceStatus.COMPATIBLE)
            return ProjectSource(repo="repo2", stars=2000, status=SourceStatus.NO_ARTIFACTS)

        mock_analyze.side_effect = analyze_side_effect
        events: list[DiscoveryEvent] = []

        # Use single query and disable caches for predictable results
        discover_sources(
            global_limit=10,
            queries=["single query"],
            on_event=events.append,
            quarantine_path=None,
            cache_path=None,
        )

        analysis_events = [e for e in events if isinstance(e, AnalysisCompleted)]
        assert len(analysis_events) == 2

        repos_analyzed = {e.repo for e in analysis_events}
        assert "repo1" in repos_analyzed
        assert "repo2" in repos_analyzed

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_analysis_completed_has_status_and_stars(self, mock_search, mock_analyze, _mock_sleep):
        """AnalysisCompleted should include status and stars."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [("owner/repo", 5000)]
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=5000,
            status=SourceStatus.COMPATIBLE,
            playwright_artifacts=["blob-report"],
        )
        events: list[DiscoveryEvent] = []

        discover_sources(
            global_limit=10,
            on_event=events.append,
        )

        analysis_events = [e for e in events if isinstance(e, AnalysisCompleted)]
        assert len(analysis_events) == 1

        event = analysis_events[0]
        assert event.stars == 5000
        assert event.status == SourceStatus.COMPATIBLE


class TestDiscoveryCompletedEvent:
    """Tests for final DiscoveryCompleted event."""

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_emits_discovery_completed_at_end(self, mock_search, mock_analyze, _mock_sleep):
        """discover_sources should emit DiscoveryCompleted with results and stats."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [("owner/repo", 1000)]
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )
        events: list[DiscoveryEvent] = []

        discover_sources(
            global_limit=10,
            on_event=events.append,
        )

        completed_events = [e for e in events if isinstance(e, DiscoveryCompleted)]
        assert len(completed_events) == 1

        event = completed_events[0]
        assert len(event.results) >= 1
        assert SourceStatus.COMPATIBLE in event.stats

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_discovery_completed_stats_match_results(self, mock_search, mock_analyze, _mock_sleep):
        """DiscoveryCompleted stats should match actual result counts."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [
            ("repo1", 1000),
            ("repo2", 2000),
            ("repo3", 3000),
        ]

        # Use function for side_effect to handle parallel execution correctly
        def analyze_side_effect(repo, **kwargs):
            if repo == "repo1":
                return ProjectSource(repo="repo1", stars=1000, status=SourceStatus.COMPATIBLE)
            return ProjectSource(repo=repo, stars=2000, status=SourceStatus.NO_ARTIFACTS)

        mock_analyze.side_effect = analyze_side_effect
        events: list[DiscoveryEvent] = []

        # Use single query and disable caches for predictable results
        discover_sources(
            global_limit=10,
            queries=["single query"],
            on_event=events.append,
            quarantine_path=None,
            cache_path=None,
        )

        completed = [e for e in events if isinstance(e, DiscoveryCompleted)][0]
        assert completed.stats[SourceStatus.COMPATIBLE] == 1
        assert completed.stats[SourceStatus.NO_ARTIFACTS] == 2


class TestEventOrder:
    """Tests for correct event ordering."""

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_event_order_is_correct(self, mock_search, mock_analyze, _mock_sleep):
        """Events should be emitted in correct order."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [("owner/repo", 1000)]
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )
        events: list[DiscoveryEvent] = []

        discover_sources(
            global_limit=10,
            on_event=events.append,
        )

        # Find event types in order
        event_types = [type(e).__name__ for e in events]

        # SearchStarted should come first
        assert event_types[0] == "SearchStarted"

        # DiscoveryCompleted should come last
        assert event_types[-1] == "DiscoveryCompleted"

        # SearchCompleted should come before any AnalysisCompleted
        search_completed_idx = event_types.index("SearchCompleted")
        analysis_completed_indices = [
            i for i, t in enumerate(event_types) if t == "AnalysisCompleted"
        ]
        if analysis_completed_indices:
            assert search_completed_idx < min(analysis_completed_indices)


class TestNoEventHandler:
    """Tests for behavior when no event handler is provided."""

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_works_without_event_handler(self, mock_search, mock_analyze, _mock_sleep):
        """discover_sources should work when on_event is None."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [("owner/repo", 1000)]
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        # Should not raise
        results = discover_sources(
            global_limit=10,
            on_event=None,
        )

        assert len(results) == 1
