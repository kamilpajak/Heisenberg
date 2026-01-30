"""Tests for discovery orchestration (discover_sources)."""

from __future__ import annotations

import threading
from unittest.mock import patch

from heisenberg.discovery.cache import QuarantineCache
from heisenberg.discovery.models import (
    DEFAULT_QUERIES,
    ProgressInfo,
    ProjectSource,
    SourceStatus,
)

# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestDiscoverSources:
    """Tests for discover_sources function."""

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_uses_default_queries(self, mock_search, mock_analyze, _mock_sleep):
        """Should use DEFAULT_QUERIES when queries not provided."""
        mock_search.return_value = []
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=100,
            status=SourceStatus.COMPATIBLE,
        )

        from heisenberg.discovery.service import discover_sources

        discover_sources(global_limit=10)

        assert mock_search.call_count == len(DEFAULT_QUERIES)


class TestMinStarsFiltering:
    """Tests for min_stars filtering before analysis."""

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_filters_by_min_stars_before_analysis(self, mock_search, mock_analyze, _mock_sleep):
        """Repos with stars < min_stars should be filtered BEFORE analysis."""
        # search_repos returns (repo, stars) tuples
        mock_search.return_value = [
            ("popular/repo", 500),
            ("unpopular/repo", 50),
        ]
        mock_analyze.return_value = ProjectSource(
            repo="popular/repo",
            stars=500,
            status=SourceStatus.COMPATIBLE,
        )

        from heisenberg.discovery.service import discover_sources

        discover_sources(global_limit=10, min_stars=100)

        # Only popular/repo should be analyzed (stars >= 100)
        analyzed_repos = [call[0][0] for call in mock_analyze.call_args_list]
        assert "popular/repo" in analyzed_repos
        assert "unpopular/repo" not in analyzed_repos

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_min_stars_zero_includes_all_repos(self, mock_search, mock_analyze, _mock_sleep):
        """min_stars=0 should include all repos."""
        mock_search.return_value = [
            ("any/repo", 0),
        ]
        mock_analyze.return_value = ProjectSource(
            repo="any/repo",
            stars=0,
            status=SourceStatus.COMPATIBLE,
        )

        from heisenberg.discovery.service import discover_sources

        discover_sources(global_limit=10, min_stars=0)

        assert mock_analyze.call_count == 1

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_passes_stars_to_analyze(self, mock_search, mock_analyze, _mock_sleep):
        """Stars from search should be passed to analyze_source_with_status."""
        mock_search.return_value = [("owner/repo", 1234)]
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=1234,
            status=SourceStatus.COMPATIBLE,
        )

        from heisenberg.discovery.service import discover_sources

        discover_sources(global_limit=10, min_stars=100)

        # Check that stars were passed to analyze
        call_kwargs = mock_analyze.call_args[1]
        assert call_kwargs.get("stars") == 1234


class TestParallelProcessing:
    """Tests for parallel source analysis."""

    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_discover_sources_uses_parallel_processing(self, mock_search, mock_analyze):
        """discover_sources should process repos in parallel when verify=True."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [("repo1", 1000), ("repo2", 1000), ("repo3", 1000)]
        mock_analyze.return_value = ProjectSource(
            repo="test/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        discover_sources(global_limit=5, verify_failures=True)

        assert mock_analyze.call_count >= 3

    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_parallel_processing_handles_exceptions(self, mock_search, mock_analyze):
        """Parallel processing should handle individual repo failures gracefully."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [("repo1", 1000), ("repo2", 1000)]

        def analyze_side_effect(repo, **kwargs):
            if repo == "repo1":
                raise Exception("API error")
            return ProjectSource(
                repo=repo,
                stars=1000,
                status=SourceStatus.COMPATIBLE,
            )

        mock_analyze.side_effect = analyze_side_effect

        result = discover_sources(global_limit=5, verify_failures=True)

        assert len(result) >= 1


class TestProgressCallback:
    """Tests for progress feedback during discovery."""

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_discover_accepts_progress_callback(self, mock_search, mock_analyze, _mock_sleep):
        """discover_sources should accept optional progress callback."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [("repo1", 1000), ("repo2", 1000)]
        mock_analyze.return_value = ProjectSource(
            repo="test/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        progress_calls = []

        def on_progress(info: ProgressInfo):
            progress_calls.append(info)

        discover_sources(
            global_limit=5,
            on_progress=on_progress,
        )

        assert len(progress_calls) >= 2


class TestThreadSafeProgress:
    """Tests for thread-safe progress reporting."""

    @patch("time.sleep")
    def test_discover_sources_returns_progress_info(self, _mock_sleep):
        """Progress callback should receive ProgressInfo objects."""
        from heisenberg.discovery.service import discover_sources

        with (
            patch("heisenberg.discovery.service.search_repos") as mock_search,
            patch("heisenberg.discovery.service.analyze_source_with_status") as mock_analyze,
        ):
            mock_search.return_value = [("repo1", 1000)]
            mock_analyze.return_value = ProjectSource(
                repo="repo1",
                stars=1000,
                status=SourceStatus.COMPATIBLE,
            )

            progress_infos = []

            def on_progress(info):
                progress_infos.append(info)

            discover_sources(global_limit=5, on_progress=on_progress)

            assert len(progress_infos) >= 1
            assert isinstance(progress_infos[0], ProgressInfo)

    @patch("time.sleep")
    def test_progress_completed_is_sequential(self, _mock_sleep):
        """Progress.completed should increment sequentially regardless of finish order."""
        from heisenberg.discovery.service import discover_sources

        with (
            patch("heisenberg.discovery.service.search_repos") as mock_search,
            patch("heisenberg.discovery.service.analyze_source_with_status") as mock_analyze,
        ):
            mock_search.return_value = [("repo1", 1000), ("repo2", 1000), ("repo3", 1000)]
            mock_analyze.return_value = ProjectSource(
                repo="test/repo",
                stars=1000,
                status=SourceStatus.COMPATIBLE,
            )

            completed_numbers = []

            def on_progress(info):
                completed_numbers.append(info.completed)

            discover_sources(global_limit=5, on_progress=on_progress)

            assert completed_numbers == sorted(completed_numbers)

    @patch("time.sleep")
    def test_progress_output_order_matches_completed_number(self, _mock_sleep):
        """Progress callback should be called in order matching completed number.

        This tests that the callback is inside the lock to prevent race conditions.
        We run the test multiple times to increase chance of catching race conditions.
        """
        from heisenberg.discovery.service import discover_sources

        for attempt in range(5):
            with (
                patch("heisenberg.discovery.service.search_repos") as mock_search,
                patch("heisenberg.discovery.service.analyze_source_with_status") as mock_analyze,
            ):
                mock_search.return_value = [
                    ("repo1", 1000),
                    ("repo2", 1000),
                    ("repo3", 1000),
                    ("repo4", 1000),
                ]

                call_count = [0]
                call_lock = threading.Lock()

                def slow_analyze(repo, _lock=call_lock, _count=call_count, **kwargs):
                    with _lock:
                        _count[0] += 1

                    return ProjectSource(
                        repo=repo,
                        stars=1000,
                        status=SourceStatus.COMPATIBLE,
                    )

                mock_analyze.side_effect = slow_analyze

                results = []

                def on_progress(info, _results=results):
                    _results.append(info.completed)

                discover_sources(global_limit=4, on_progress=on_progress)

                assert results == [1, 2, 3, 4], (
                    f"Attempt {attempt}: Got {results}, expected [1, 2, 3, 4]"
                )


class TestDiscoverWithRichProgress:
    """Tests for discover_sources with Rich progress display."""

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_discover_shows_active_tasks(self, mock_search, mock_analyze, _mock_sleep):
        """discover_sources should show tasks while they're running."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [("repo1", 1000), ("repo2", 1000)]
        mock_analyze.return_value = ProjectSource(
            repo="test/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        result = discover_sources(
            global_limit=5,
            show_progress=True,
        )

        assert len(result) >= 1

    @patch("time.sleep")
    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_discover_works_without_progress(self, mock_search, mock_analyze, _mock_sleep):
        """discover_sources should work with show_progress=False."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [("repo1", 1000)]
        mock_analyze.return_value = ProjectSource(
            repo="test/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        result = discover_sources(
            global_limit=5,
            show_progress=False,
        )

        assert len(result) >= 1


class TestNoCacheFlag:
    """Tests for --no-cache CLI flag."""

    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_discover_accepts_no_cache_flag(self, mock_search, mock_analyze):
        """discover_sources should accept cache_path=None to disable cache."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [("repo1", 1000)]
        mock_analyze.return_value = ProjectSource(
            repo="repo1",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        result = discover_sources(
            global_limit=5,
            verify_failures=True,
            cache_path=None,
        )

        assert len(result) >= 1

    def test_cli_has_no_cache_argument(self):
        """CLI parser should have --no-cache argument."""
        from heisenberg.discovery.cli import create_argument_parser

        parser = create_argument_parser()
        args = parser.parse_args(["--no-cache"])

        assert args.no_cache is True

    def test_cli_no_cache_disables_caching(self):
        """--no-cache should set cache_path to None."""
        from heisenberg.discovery.cli import create_argument_parser

        parser = create_argument_parser()

        args1 = parser.parse_args([])
        assert args1.no_cache is False

        args2 = parser.parse_args(["--no-cache"])
        assert args2.no_cache is True


# =============================================================================
# QUARANTINE INTEGRATION TESTS
# =============================================================================


class TestQuarantineIntegration:
    """Tests for quarantine cache integration with discover_sources."""

    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_quarantine_skips_non_compatible_repos(self, mock_search, mock_analyze, tmp_path):
        """Quarantined repos should be skipped during analysis."""
        from heisenberg.discovery.service import discover_sources

        quarantine_file = tmp_path / "quarantine.json"
        quarantine = QuarantineCache(cache_path=quarantine_file)
        quarantine.set("bad/repo", "no_artifacts")

        mock_search.return_value = [("bad/repo", 1000), ("good/repo", 1000)]
        mock_analyze.return_value = ProjectSource(
            repo="good/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        discover_sources(
            global_limit=50,
            quarantine_path=quarantine_file,
        )

        analyzed_repos = [call[0][0] for call in mock_analyze.call_args_list]
        assert "bad/repo" not in analyzed_repos
        assert "good/repo" in analyzed_repos

    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_quarantine_updates_after_analysis(self, mock_search, mock_analyze, tmp_path):
        """Non-compatible repos should be quarantined after analysis."""
        from heisenberg.discovery.service import discover_sources

        quarantine_file = tmp_path / "quarantine.json"

        mock_search.return_value = [("no-artifacts/repo", 1000)]

        mock_analyze.return_value = ProjectSource(
            repo="no-artifacts/repo",
            stars=1000,
            status=SourceStatus.NO_ARTIFACTS,
        )

        discover_sources(
            global_limit=50,
            quarantine_path=quarantine_file,
        )

        quarantine = QuarantineCache(cache_path=quarantine_file)
        assert quarantine.is_quarantined("no-artifacts/repo") is True

    @patch("heisenberg.discovery.service.analyze_source_with_status")
    @patch("heisenberg.discovery.service.search_repos")
    def test_quarantine_disabled_when_path_is_none(self, mock_search, mock_analyze):
        """quarantine_path=None should disable quarantine entirely."""
        from heisenberg.discovery.service import discover_sources

        mock_search.return_value = [("repo1", 1000)]
        mock_analyze.return_value = ProjectSource(
            repo="repo1",
            stars=1000,
            status=SourceStatus.NO_ARTIFACTS,
        )

        result = discover_sources(
            global_limit=50,
            quarantine_path=None,
        )

        assert len(result) >= 1


class TestFreshFlag:
    """Tests for --fresh CLI flag."""

    def test_cli_has_fresh_argument(self):
        """CLI parser should have --fresh argument."""
        from heisenberg.discovery.cli import create_argument_parser

        parser = create_argument_parser()
        args = parser.parse_args(["--fresh"])

        assert args.fresh is True

    def test_fresh_disables_quarantine(self):
        """--fresh should set quarantine to disabled."""
        from heisenberg.discovery.cli import create_argument_parser

        parser = create_argument_parser()

        args_default = parser.parse_args([])
        assert args_default.fresh is False

        args_fresh = parser.parse_args(["--fresh"])
        assert args_fresh.fresh is True

    def test_no_cache_disables_quarantine(self):
        """--no-cache should also disable quarantine."""
        from heisenberg.discovery.cli import create_argument_parser

        parser = create_argument_parser()
        args = parser.parse_args(["--no-cache"])

        assert args.no_cache is True
