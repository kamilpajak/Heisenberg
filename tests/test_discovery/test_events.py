"""Tests for discovery event types."""

from __future__ import annotations

from heisenberg.discovery.models import SourceStatus


class TestSearchEvents:
    """Tests for search phase events."""

    def test_search_started_has_total_queries(self):
        """SearchStarted should have total_queries field."""
        from heisenberg.discovery.events import SearchStarted

        event = SearchStarted(total_queries=4)
        assert event.total_queries == 4

    def test_query_completed_has_all_fields(self):
        """QueryCompleted should have index, preview, counts."""
        from heisenberg.discovery.events import QueryCompleted

        event = QueryCompleted(
            query_index=0,
            query_preview="playwright upload-artifact",
            repos_found=23,
            new_repos=23,
        )
        assert event.query_index == 0
        assert event.query_preview == "playwright upload-artifact"
        assert event.repos_found == 23
        assert event.new_repos == 23

    def test_search_completed_has_filter_stats(self):
        """SearchCompleted should have filtering statistics."""
        from heisenberg.discovery.events import SearchCompleted

        event = SearchCompleted(
            total_candidates=39,
            quarantine_skipped=12,
            stars_filtered=6,
            to_analyze=21,
        )
        assert event.total_candidates == 39
        assert event.quarantine_skipped == 12
        assert event.stars_filtered == 6
        assert event.to_analyze == 21


class TestAnalysisEvents:
    """Tests for analysis phase events."""

    def test_analysis_started_has_repo_info(self):
        """AnalysisStarted should have repo, stars, progress."""
        from heisenberg.discovery.events import AnalysisStarted

        event = AnalysisStarted(
            repo="microsoft/playwright",
            stars=81500,
            index=0,
            total=21,
        )
        assert event.repo == "microsoft/playwright"
        assert event.stars == 81500
        assert event.index == 0
        assert event.total == 21

    def test_analysis_progress_has_stage(self):
        """AnalysisProgress should have repo and stage."""
        from heisenberg.discovery.events import AnalysisProgress

        event = AnalysisProgress(
            repo="microsoft/playwright",
            stage="fetching runs",
        )
        assert event.repo == "microsoft/playwright"
        assert event.stage == "fetching runs"

    def test_analysis_completed_has_result_details(self):
        """AnalysisCompleted should have full result information."""
        from heisenberg.discovery.events import AnalysisCompleted

        event = AnalysisCompleted(
            repo="microsoft/playwright",
            stars=81500,
            status=SourceStatus.COMPATIBLE,
            artifact_name="blob-report",
            failure_count=5,
            cache_hit=False,
            elapsed_ms=2100,
            index=0,
            total=21,
        )
        assert event.repo == "microsoft/playwright"
        assert event.stars == 81500
        assert event.status == SourceStatus.COMPATIBLE
        assert event.artifact_name == "blob-report"
        assert event.failure_count == 5
        assert event.cache_hit is False
        assert event.elapsed_ms == 2100

    def test_analysis_completed_optional_fields(self):
        """AnalysisCompleted should allow None for optional fields."""
        from heisenberg.discovery.events import AnalysisCompleted

        event = AnalysisCompleted(
            repo="owner/repo",
            stars=100,
            status=SourceStatus.NO_ARTIFACTS,
            artifact_name=None,
            failure_count=None,
            cache_hit=False,
            elapsed_ms=500,
            index=0,
            total=1,
        )
        assert event.artifact_name is None
        assert event.failure_count is None


class TestDiscoveryCompleted:
    """Tests for final discovery completed event."""

    def test_discovery_completed_has_results_and_stats(self):
        """DiscoveryCompleted should have results list and stats dict."""
        from heisenberg.discovery.events import DiscoveryCompleted
        from heisenberg.discovery.models import ProjectSource

        results = [
            ProjectSource(
                repo="microsoft/playwright",
                stars=81500,
                status=SourceStatus.COMPATIBLE,
            ),
        ]
        stats = {
            SourceStatus.COMPATIBLE: 1,
            SourceStatus.NO_ARTIFACTS: 5,
        }

        event = DiscoveryCompleted(results=results, stats=stats)
        assert len(event.results) == 1
        assert event.results[0].repo == "microsoft/playwright"
        assert event.stats[SourceStatus.COMPATIBLE] == 1


class TestEventUnionType:
    """Tests for DiscoveryEvent union type."""

    def test_all_events_are_in_union(self):
        """All event types should be part of DiscoveryEvent union."""
        from typing import get_args

        from heisenberg.discovery.events import (
            AnalysisCompleted,
            AnalysisProgress,
            AnalysisStarted,
            DiscoveryCompleted,
            DiscoveryEvent,
            QueryCompleted,
            SearchCompleted,
            SearchStarted,
        )

        union_types = get_args(DiscoveryEvent)
        assert SearchStarted in union_types
        assert QueryCompleted in union_types
        assert SearchCompleted in union_types
        assert AnalysisStarted in union_types
        assert AnalysisProgress in union_types
        assert AnalysisCompleted in union_types
        assert DiscoveryCompleted in union_types


class TestEventHandler:
    """Tests for EventHandler callable type."""

    def test_event_handler_type_accepts_callable(self):
        """EventHandler should accept a callable that takes DiscoveryEvent."""
        from heisenberg.discovery.events import (
            DiscoveryEvent,
            EventHandler,
            SearchStarted,
        )

        events_received: list[DiscoveryEvent] = []

        def handler(event: DiscoveryEvent) -> None:
            events_received.append(event)

        # Type check: handler should match EventHandler signature
        typed_handler: EventHandler = handler

        typed_handler(SearchStarted(total_queries=4))
        assert len(events_received) == 1
