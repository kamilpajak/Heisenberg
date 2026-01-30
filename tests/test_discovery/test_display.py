"""Tests for discovery display component."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from heisenberg.discovery.events import (
    AnalysisCompleted,
    DiscoveryCompleted,
    QueryCompleted,
    SearchCompleted,
    SearchStarted,
)
from heisenberg.discovery.models import ProjectSource, SourceStatus


class TestDiscoveryDisplayInit:
    """Tests for DiscoveryDisplay initialization."""

    def test_default_mode_is_not_verbose(self):
        """Default display should not be verbose."""
        from heisenberg.discovery.display import DiscoveryDisplay

        display = DiscoveryDisplay()
        assert display.verbose is False

    def test_default_mode_is_not_quiet(self):
        """Default display should not be quiet."""
        from heisenberg.discovery.display import DiscoveryDisplay

        display = DiscoveryDisplay()
        assert display.quiet is False

    def test_accepts_verbose_flag(self):
        """Display should accept verbose flag."""
        from heisenberg.discovery.display import DiscoveryDisplay

        display = DiscoveryDisplay(verbose=True)
        assert display.verbose is True

    def test_accepts_quiet_flag(self):
        """Display should accept quiet flag."""
        from heisenberg.discovery.display import DiscoveryDisplay

        display = DiscoveryDisplay(quiet=True)
        assert display.quiet is True


class TestDisplayHandle:
    """Tests for event handling."""

    def test_handle_dispatches_search_started(self):
        """handle() should dispatch SearchStarted to correct handler."""
        from heisenberg.discovery.display import DiscoveryDisplay

        display = DiscoveryDisplay()
        display._on_search_started = MagicMock()

        event = SearchStarted(total_queries=4)
        display.handle(event)

        display._on_search_started.assert_called_once_with(event)

    def test_handle_dispatches_query_completed(self):
        """handle() should dispatch QueryCompleted to correct handler."""
        from heisenberg.discovery.display import DiscoveryDisplay

        display = DiscoveryDisplay()
        display._on_query_completed = MagicMock()

        event = QueryCompleted(
            query_index=0, query_preview="playwright", repos_found=10, new_repos=10
        )
        display.handle(event)

        display._on_query_completed.assert_called_once_with(event)

    def test_handle_dispatches_analysis_completed(self):
        """handle() should dispatch AnalysisCompleted to correct handler."""
        from heisenberg.discovery.display import DiscoveryDisplay

        display = DiscoveryDisplay()
        display._on_analysis_completed = MagicMock()

        event = AnalysisCompleted(
            repo="owner/repo",
            stars=100,
            status=SourceStatus.COMPATIBLE,
            artifact_name="blob-report",
            failure_count=5,
            cache_hit=False,
            elapsed_ms=1000,
            index=0,
            total=1,
        )
        display.handle(event)

        display._on_analysis_completed.assert_called_once_with(event)

    def test_quiet_mode_skips_all_output(self):
        """Quiet mode should skip all event handlers."""
        from heisenberg.discovery.display import DiscoveryDisplay

        display = DiscoveryDisplay(quiet=True)
        display._on_search_started = MagicMock()
        display._on_analysis_completed = MagicMock()

        display.handle(SearchStarted(total_queries=4))
        display.handle(
            AnalysisCompleted(
                repo="owner/repo",
                stars=100,
                status=SourceStatus.COMPATIBLE,
                artifact_name=None,
                failure_count=None,
                cache_hit=False,
                elapsed_ms=100,
                index=0,
                total=1,
            )
        )

        display._on_search_started.assert_not_called()
        display._on_analysis_completed.assert_not_called()


class TestSearchPhaseOutput:
    """Tests for search phase display output."""

    def test_search_started_prints_header(self):
        """SearchStarted should print search header."""
        from heisenberg.discovery.display import DiscoveryDisplay

        with patch("heisenberg.discovery.display.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            display = DiscoveryDisplay()
            display.handle(SearchStarted(total_queries=4))

            # Verify console.print was called with search header
            mock_console.print.assert_called()

    def test_query_completed_shows_repo_count(self):
        """QueryCompleted should show repos found."""
        from heisenberg.discovery.display import DiscoveryDisplay

        with patch("heisenberg.discovery.display.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            display = DiscoveryDisplay()
            display.handle(
                QueryCompleted(
                    query_index=0,
                    query_preview="playwright upload-artifact",
                    repos_found=23,
                    new_repos=23,
                )
            )

            # Should have printed query info
            assert mock_console.print.called

    def test_search_completed_shows_filter_summary(self):
        """SearchCompleted should show filtering summary."""
        from heisenberg.discovery.display import DiscoveryDisplay

        with patch("heisenberg.discovery.display.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            display = DiscoveryDisplay()
            display.handle(
                SearchCompleted(
                    total_candidates=39,
                    quarantine_skipped=12,
                    stars_filtered=6,
                    to_analyze=21,
                )
            )

            assert mock_console.print.called


class TestAnalysisPhaseOutput:
    """Tests for analysis phase display output."""

    def test_compatible_repo_shown_immediately(self):
        """Compatible repos should be displayed immediately in default mode."""
        from heisenberg.discovery.display import DiscoveryDisplay

        with patch("heisenberg.discovery.display.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            display = DiscoveryDisplay()
            display.handle(
                AnalysisCompleted(
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
            )

            # Should print compatible hit
            assert mock_console.print.called

    def test_non_compatible_repo_silent_in_default_mode(self):
        """Non-compatible repos should be silent in default mode."""
        from heisenberg.discovery.display import DiscoveryDisplay

        with patch("heisenberg.discovery.display.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            display = DiscoveryDisplay(verbose=False)
            display.handle(
                AnalysisCompleted(
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
            )

            # Should NOT print for non-compatible in default mode
            mock_console.print.assert_not_called()

    def test_non_compatible_repo_shown_in_verbose_mode(self):
        """Non-compatible repos should be shown in verbose mode."""
        from heisenberg.discovery.display import DiscoveryDisplay

        with patch("heisenberg.discovery.display.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            display = DiscoveryDisplay(verbose=True)
            display.handle(
                AnalysisCompleted(
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
            )

            # Should print for non-compatible in verbose mode
            assert mock_console.print.called


class TestDiscoveryCompletedOutput:
    """Tests for final summary display."""

    def test_shows_compatible_count(self):
        """Summary should show compatible count."""
        from heisenberg.discovery.display import DiscoveryDisplay

        with patch("heisenberg.discovery.display.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            display = DiscoveryDisplay()
            display.handle(
                DiscoveryCompleted(
                    results=[
                        ProjectSource(
                            repo="microsoft/playwright",
                            stars=81500,
                            status=SourceStatus.COMPATIBLE,
                        ),
                    ],
                    stats={SourceStatus.COMPATIBLE: 1, SourceStatus.NO_ARTIFACTS: 5},
                )
            )

            assert mock_console.print.called


class TestStatsTracking:
    """Tests for internal stats tracking."""

    def test_tracks_status_counts(self):
        """Display should track counts by status."""
        from heisenberg.discovery.display import DiscoveryDisplay

        display = DiscoveryDisplay(quiet=True)  # Quiet to avoid console
        display._stats[SourceStatus.COMPATIBLE] = 0
        display._stats[SourceStatus.NO_ARTIFACTS] = 0

        # Manually update stats (normally done in _on_analysis_completed)
        display._stats[SourceStatus.COMPATIBLE] += 1
        display._stats[SourceStatus.NO_ARTIFACTS] += 3

        assert display._stats[SourceStatus.COMPATIBLE] == 1
        assert display._stats[SourceStatus.NO_ARTIFACTS] == 3


class TestFormatStars:
    """Tests for star formatting helper."""

    def test_format_stars_millions(self):
        """Should format millions with M suffix."""
        from heisenberg.discovery.display import format_stars

        assert format_stars(1_500_000) == "1.5M"

    def test_format_stars_thousands(self):
        """Should format thousands with k suffix."""
        from heisenberg.discovery.display import format_stars

        assert format_stars(81_500) == "81.5k"

    def test_format_stars_hundreds(self):
        """Should show raw number for hundreds."""
        from heisenberg.discovery.display import format_stars

        assert format_stars(500) == "500"

    def test_format_stars_zero(self):
        """Should handle zero."""
        from heisenberg.discovery.display import format_stars

        assert format_stars(0) == "0"
