"""Tests for discover_projects.py script."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

from heisenberg.playground.discover import (
    DEFAULT_QUERIES,
    GH_MAX_RETRIES,
    ProjectSource,
    SourceStatus,
    _gh_subprocess,
    _is_rate_limit_error,
    analyze_source,
    determine_status,
    download_and_check_failures,
    filter_by_min_stars,
    filter_expired_artifacts,
    find_valid_artifacts,
    format_size,
    format_stars,
    format_status_color,
    format_status_icon,
    format_status_label,
    get_failed_runs,
    get_run_artifacts,
    is_playwright_artifact,
    search_repos,
    sort_sources,
    verify_has_failures,
)

# =============================================================================
# CONFIGURATION TESTS
# =============================================================================


class TestConfiguration:
    """Tests for module-level configuration."""

    def test_default_queries_exist(self):
        """DEFAULT_QUERIES should be defined at module level."""
        assert DEFAULT_QUERIES is not None
        assert len(DEFAULT_QUERIES) >= 1

    def test_default_queries_contain_playwright(self):
        """All default queries should search for Playwright-related content."""
        for query in DEFAULT_QUERIES:
            assert "playwright" in query.lower() or "blob-report" in query.lower()


# =============================================================================
# DOMAIN MODEL TESTS
# =============================================================================


class TestSourceStatus:
    """Tests for SourceStatus enum."""

    def test_has_all_statuses(self):
        """Should have all expected status values."""
        assert SourceStatus.COMPATIBLE.value == "compatible"
        assert SourceStatus.HAS_ARTIFACTS.value == "has_artifacts"
        assert SourceStatus.NO_ARTIFACTS.value == "no_artifacts"
        assert SourceStatus.NO_FAILED_RUNS.value == "no_failed_runs"


class TestProjectSource:
    """Tests for ProjectSource dataclass."""

    def test_compatible_property_true_when_compatible(self):
        """compatible property should return True for COMPATIBLE status."""
        source = ProjectSource(
            repo="owner/repo",
            stars=100,
            status=SourceStatus.COMPATIBLE,
        )
        assert source.compatible is True

    def test_compatible_property_false_for_other_statuses(self):
        """compatible property should return False for non-COMPATIBLE status."""
        for status in [
            SourceStatus.HAS_ARTIFACTS,
            SourceStatus.NO_ARTIFACTS,
            SourceStatus.NO_FAILED_RUNS,
        ]:
            source = ProjectSource(repo="owner/repo", stars=100, status=status)
            assert source.compatible is False

    def test_has_artifacts_property(self):
        """has_artifacts property should check artifact_names list."""
        with_artifacts = ProjectSource(
            repo="owner/repo",
            stars=100,
            status=SourceStatus.HAS_ARTIFACTS,
            artifact_names=["report"],
        )
        without_artifacts = ProjectSource(
            repo="owner/repo",
            stars=100,
            status=SourceStatus.NO_ARTIFACTS,
            artifact_names=[],
        )
        assert with_artifacts.has_artifacts is True
        assert without_artifacts.has_artifacts is False


# =============================================================================
# DOMAIN LOGIC TESTS
# =============================================================================


class TestIsPlaywrightArtifact:
    """Tests for is_playwright_artifact function - STRICT matching."""

    def test_matches_playwright_report(self):
        """Should match 'playwright-report' artifact."""
        assert is_playwright_artifact("playwright-report") is True

    def test_matches_playwright_report_with_suffix(self):
        """Should match 'playwright-report-ubuntu' artifact."""
        assert is_playwright_artifact("playwright-report-ubuntu") is True

    def test_matches_trace_zip(self):
        """Should match 'trace.zip' artifact."""
        assert is_playwright_artifact("trace.zip") is True

    def test_matches_blob_report(self):
        """Should match 'blob-report' artifact (Playwright sharding)."""
        assert is_playwright_artifact("blob-report") is True

    def test_matches_playwright_traces(self):
        """Should match 'playwright-traces' artifact."""
        assert is_playwright_artifact("playwright-traces") is True

    def test_rejects_generic_report(self):
        """Should NOT match generic 'coverage-report' - too loose."""
        assert is_playwright_artifact("coverage-report") is False

    def test_rejects_jest_report(self):
        """Should NOT match 'jest-coverage-report'."""
        assert is_playwright_artifact("jest-coverage-report") is False

    def test_rejects_cypress_e2e(self):
        """Should NOT match 'cypress-e2e-results'."""
        assert is_playwright_artifact("cypress-e2e-results") is False

    def test_rejects_generic_e2e(self):
        """Should NOT match generic 'e2e-results'."""
        assert is_playwright_artifact("e2e-results") is False

    def test_rejects_lighthouse_report(self):
        """Should NOT match 'lighthouse-report'."""
        assert is_playwright_artifact("lighthouse-report") is False

    def test_rejects_blob_storage(self):
        """Should NOT match 'blob-storage' - not Playwright blob-report."""
        assert is_playwright_artifact("blob-storage") is False

    def test_rejects_generic_test_results(self):
        """Should NOT match generic 'test-results'."""
        assert is_playwright_artifact("test-results") is False

    def test_case_insensitive(self):
        """Should match case-insensitively."""
        assert is_playwright_artifact("Playwright-Report") is True
        assert is_playwright_artifact("BLOB-REPORT") is True


class TestDetermineStatus:
    """Tests for determine_status function."""

    def test_no_failed_runs(self):
        """Should return NO_FAILED_RUNS when run_id is None."""
        status = determine_status(None, [], [])
        assert status == SourceStatus.NO_FAILED_RUNS

    def test_no_artifacts(self):
        """Should return NO_ARTIFACTS when artifact list is empty."""
        status = determine_status("123", [], [])
        assert status == SourceStatus.NO_ARTIFACTS

    def test_has_artifacts_but_no_playwright(self):
        """Should return HAS_ARTIFACTS when artifacts exist but none are Playwright."""
        status = determine_status("123", ["coverage-report"], [])
        assert status == SourceStatus.HAS_ARTIFACTS

    def test_compatible(self):
        """Should return COMPATIBLE when Playwright artifacts exist."""
        status = determine_status("123", ["playwright-report"], ["playwright-report"])
        assert status == SourceStatus.COMPATIBLE


class TestFilterExpiredArtifacts:
    """Tests for filter_expired_artifacts function."""

    def test_filters_expired(self):
        """Should filter out expired artifacts."""
        artifacts = [
            {"name": "report1", "expired": False},
            {"name": "report2", "expired": True},
            {"name": "report3", "expired": False},
        ]
        result = filter_expired_artifacts(artifacts)
        assert result == ["report1", "report3"]

    def test_handles_missing_expired_field(self):
        """Should treat missing expired field as not expired."""
        artifacts = [{"name": "report1"}]
        result = filter_expired_artifacts(artifacts)
        assert result == ["report1"]


class TestFilterByMinStars:
    """Tests for filter_by_min_stars function."""

    def test_filters_below_threshold(self):
        """Should filter out repos below min_stars threshold."""
        sources = [
            ProjectSource(
                repo="low/stars",
                stars=50,
                status=SourceStatus.COMPATIBLE,
            ),
            ProjectSource(
                repo="high/stars",
                stars=500,
                status=SourceStatus.COMPATIBLE,
            ),
        ]
        filtered = filter_by_min_stars(sources, min_stars=100)
        assert len(filtered) == 1
        assert filtered[0].repo == "high/stars"

    def test_keeps_at_threshold(self):
        """Should keep repos at exactly min_stars threshold."""
        sources = [
            ProjectSource(
                repo="exact/threshold",
                stars=100,
                status=SourceStatus.COMPATIBLE,
            ),
        ]
        filtered = filter_by_min_stars(sources, min_stars=100)
        assert len(filtered) == 1


class TestSortSources:
    """Tests for sort_sources function."""

    def test_sorts_compatible_first(self):
        """Compatible sources should come before non-compatible."""
        sources = [
            ProjectSource(repo="a", stars=1000, status=SourceStatus.HAS_ARTIFACTS),
            ProjectSource(repo="b", stars=100, status=SourceStatus.COMPATIBLE),
        ]
        sorted_list = sort_sources(sources)
        assert sorted_list[0].repo == "b"  # Compatible first

    def test_sorts_by_stars_within_same_status(self):
        """Higher stars should come first within same compatibility."""
        sources = [
            ProjectSource(repo="a", stars=100, status=SourceStatus.COMPATIBLE),
            ProjectSource(repo="b", stars=500, status=SourceStatus.COMPATIBLE),
        ]
        sorted_list = sort_sources(sources)
        assert sorted_list[0].repo == "b"  # Higher stars first


# =============================================================================
# GITHUB CLIENT TESTS
# =============================================================================


class TestGetFailedRuns:
    """Tests for get_failed_runs function."""

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_workflow_runs(self, mock_run, _mock_sleep):
        """Should return list of workflow runs."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "workflow_runs": [
                        {"id": 100, "html_url": "url1"},
                        {"id": 200, "html_url": "url2"},
                    ]
                }
            ),
            returncode=0,
        )

        runs = get_failed_runs("owner/repo")

        assert len(runs) == 2
        assert runs[0]["id"] == 100

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_requests_multiple_runs(self, mock_run, _mock_sleep):
        """Should request per_page=5 by default."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"workflow_runs": []}),
            returncode=0,
        )

        get_failed_runs("owner/repo")

        call_args = " ".join(mock_run.call_args[0][0])
        assert "per_page=5" in call_args


class TestGetRunArtifacts:
    """Tests for get_run_artifacts function."""

    @patch("heisenberg.playground.discover.gh_api")
    def test_returns_artifacts_list(self, mock_gh_api):
        """Should return list of artifact dicts."""
        mock_gh_api.return_value = {
            "artifacts": [
                {"name": "report1", "expired": False},
                {"name": "report2", "expired": True},
            ]
        }

        artifacts = get_run_artifacts("owner/repo", "123")

        assert len(artifacts) == 2
        assert artifacts[0]["name"] == "report1"


class TestFindValidArtifacts:
    """Tests for find_valid_artifacts function."""

    @patch("heisenberg.playground.discover.get_run_artifacts")
    @patch("heisenberg.playground.discover.get_failed_runs")
    def test_checks_multiple_runs(self, mock_get_runs, mock_get_artifacts):
        """Should check multiple runs until valid artifacts found."""
        mock_get_runs.return_value = [
            {"id": 100, "html_url": "url1", "created_at": "2024-01-01T00:00:00Z"},
            {"id": 200, "html_url": "url2", "created_at": "2024-01-02T00:00:00Z"},
        ]

        # First run has no artifacts, second has valid ones
        def artifacts_side_effect(repo, run_id):
            if run_id == "100":
                return []
            return [{"name": "playwright-report", "expired": False}]

        mock_get_artifacts.side_effect = artifacts_side_effect

        run_id, run_url, artifacts, run_created_at, _ = find_valid_artifacts("owner/repo")

        assert run_id == "200"
        assert "playwright-report" in artifacts
        assert run_created_at == "2024-01-02T00:00:00Z"

    @patch("heisenberg.playground.discover.get_run_artifacts")
    @patch("heisenberg.playground.discover.get_failed_runs")
    def test_skips_expired_artifacts(self, mock_get_runs, mock_get_artifacts):
        """Should skip expired artifacts."""
        mock_get_runs.return_value = [
            {"id": 100, "html_url": "url1", "created_at": "2024-01-15T10:00:00Z"}
        ]
        mock_get_artifacts.return_value = [
            {"name": "playwright-report", "expired": True},
            {"name": "trace.zip", "expired": False},
        ]

        run_id, run_url, artifacts, run_created_at, _ = find_valid_artifacts("owner/repo")

        assert "playwright-report" not in artifacts
        assert "trace.zip" in artifacts


class TestSearchRepos:
    """Tests for search_repos function."""

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_repo_names(self, mock_run, _mock_sleep):
        """Should return list of repo names."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"items": [{"repository": {"full_name": "owner/repo"}}]}),
            returncode=0,
        )

        results = search_repos("playwright", limit=10)

        assert len(results) == 1
        assert results[0] == "owner/repo"

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_deduplicates_across_results(self, mock_run, _mock_sleep):
        """Should deduplicate repos that appear multiple times."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "items": [
                        {"repository": {"full_name": "owner/repo"}},
                        {"repository": {"full_name": "owner/repo"}},
                    ]
                }
            ),
            returncode=0,
        )

        results = search_repos("query", limit=10)

        assert len(results) == 1


class TestAnalyzeCandidate:
    """Tests for analyze_source function."""

    @patch("heisenberg.playground.discover.find_valid_artifacts")
    @patch("heisenberg.playground.discover.get_repo_stars")
    def test_uses_provided_stars(self, mock_get_stars, mock_find_artifacts):
        """Should use stars provided as argument, not make API call."""
        mock_find_artifacts.return_value = (
            "123",
            "url",
            ["playwright-report"],
            "2024-01-15T10:00:00Z",
            {"playwright-report": 50_000_000},
        )
        mock_get_stars.return_value = 999

        source = analyze_source("owner/repo", stars=5000)

        assert source.stars == 5000
        mock_get_stars.assert_not_called()

    @patch("heisenberg.playground.discover.find_valid_artifacts")
    @patch("heisenberg.playground.discover.get_repo_stars")
    def test_fetches_stars_when_not_provided(self, mock_get_stars, mock_find_artifacts):
        """Should fetch stars via API when not provided."""
        mock_find_artifacts.return_value = (
            "123",
            "url",
            ["playwright-report"],
            "2024-01-15T10:00:00Z",
            {"playwright-report": 50_000_000},
        )
        mock_get_stars.return_value = 1234

        source = analyze_source("owner/repo")

        assert source.stars == 1234
        mock_get_stars.assert_called_once_with("owner/repo")

    @patch("heisenberg.playground.discover.find_valid_artifacts")
    @patch("heisenberg.playground.discover.get_repo_stars")
    def test_sets_correct_status(self, mock_get_stars, mock_find_artifacts):
        """Should set correct status based on artifacts."""
        mock_find_artifacts.return_value = (
            "123",
            "url",
            ["playwright-report"],
            "2024-01-15T10:00:00Z",
            {"playwright-report": 50_000_000},
        )
        mock_get_stars.return_value = 100

        source = analyze_source("owner/repo")

        assert source.status == SourceStatus.COMPATIBLE
        assert source.playwright_artifacts == ["playwright-report"]


# =============================================================================
# PRESENTER TESTS
# =============================================================================


class TestFormatStatusIcon:
    """Tests for format_status_icon function."""

    def test_compatible_icon(self):
        """COMPATIBLE status should show plus."""
        assert format_status_icon(SourceStatus.COMPATIBLE) == "+"

    def test_no_failures_icon(self):
        """NO_FAILURES status should show tilde."""
        assert format_status_icon(SourceStatus.NO_FAILURES) == "~"

    def test_has_artifacts_icon(self):
        """HAS_ARTIFACTS status should show exclamation."""
        assert format_status_icon(SourceStatus.HAS_ARTIFACTS) == "!"

    def test_no_artifacts_icon(self):
        """NO_ARTIFACTS status should show dash."""
        assert format_status_icon(SourceStatus.NO_ARTIFACTS) == "-"

    def test_no_failed_runs_icon(self):
        """NO_FAILED_RUNS status should show dot."""
        assert format_status_icon(SourceStatus.NO_FAILED_RUNS) == "."


class TestFormatStatusColor:
    """Tests for format_status_color function."""

    def test_compatible_color(self):
        """COMPATIBLE status should be green."""
        assert format_status_color(SourceStatus.COMPATIBLE) == "green"

    def test_no_failures_color(self):
        """NO_FAILURES status should be yellow."""
        assert format_status_color(SourceStatus.NO_FAILURES) == "yellow"

    def test_has_artifacts_color(self):
        """HAS_ARTIFACTS status should be yellow."""
        assert format_status_color(SourceStatus.HAS_ARTIFACTS) == "yellow"

    def test_no_artifacts_color(self):
        """NO_ARTIFACTS status should be red."""
        assert format_status_color(SourceStatus.NO_ARTIFACTS) == "red"

    def test_no_failed_runs_color(self):
        """NO_FAILED_RUNS status should be dim."""
        assert format_status_color(SourceStatus.NO_FAILED_RUNS) == "dim"


class TestFormatStatusLabel:
    """Tests for format_status_label function."""

    def test_compatible_label(self):
        """COMPATIBLE status should return 'compatible'."""
        assert format_status_label(SourceStatus.COMPATIBLE) == "compatible"

    def test_no_failures_label(self):
        """NO_FAILURES status should return 'tests passing'."""
        assert format_status_label(SourceStatus.NO_FAILURES) == "tests passing"

    def test_has_artifacts_label(self):
        """HAS_ARTIFACTS status should return 'has artifacts'."""
        assert format_status_label(SourceStatus.HAS_ARTIFACTS) == "has artifacts"

    def test_no_artifacts_label(self):
        """NO_ARTIFACTS status should return 'no artifacts'."""
        assert format_status_label(SourceStatus.NO_ARTIFACTS) == "no artifacts"

    def test_no_failed_runs_label(self):
        """NO_FAILED_RUNS status should return 'no failed runs'."""
        assert format_status_label(SourceStatus.NO_FAILED_RUNS) == "no failed runs"

    def test_all_labels_have_spaces(self):
        """All multi-word labels should use spaces, not underscores."""
        for status in SourceStatus:
            label = format_status_label(status)
            assert "_" not in label, f"{status.name} label contains underscore: {label}"

    def test_all_labels_fit_column_width(self):
        """All labels should fit within COL_STATUS (14 chars)."""
        from heisenberg.playground.discover import COL_STATUS

        for status in SourceStatus:
            label = format_status_label(status)
            assert len(label) <= COL_STATUS, (
                f"{status.name} label '{label}' is {len(label)} chars, max {COL_STATUS}"
            )


class TestFormatStars:
    """Tests for format_stars function."""

    def test_small_numbers_unchanged(self):
        """Numbers under 1000 should be returned as-is."""
        assert format_stars(0) == "0"
        assert format_stars(293) == "293"
        assert format_stars(999) == "999"

    def test_thousands(self):
        """Numbers >= 1000 should use 'k' suffix with one decimal."""
        assert format_stars(1000) == "1.0k"
        assert format_stars(5962) == "6.0k"
        assert format_stars(6746) == "6.7k"
        assert format_stars(81807) == "81.8k"

    def test_millions(self):
        """Numbers >= 1M should use 'M' suffix with one decimal."""
        assert format_stars(1_000_000) == "1.0M"
        assert format_stars(2_500_000) == "2.5M"


class TestFormatSize:
    """Tests for format_size function."""

    def test_bytes(self):
        """Small values should show bytes."""
        assert format_size(0) == "0 B"
        assert format_size(512) == "512 B"

    def test_kilobytes(self):
        """Values in KB range should show KB."""
        assert format_size(1024) == "1 KB"
        assert format_size(150_000) == "146 KB"

    def test_megabytes(self):
        """Values in MB range should show MB."""
        assert format_size(1_048_576) == "1 MB"
        assert format_size(52_000_000) == "50 MB"
        assert format_size(500_000_000) == "477 MB"

    def test_gigabytes(self):
        """Values in GB range should show GB with one decimal."""
        assert format_size(1_073_741_824) == "1.0 GB"
        assert format_size(1_500_000_000) == "1.4 GB"


# =============================================================================
# TIMEOUT HANDLING
# =============================================================================


class TestSubprocessTimeouts:
    """Tests for subprocess timeout handling."""

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_gh_api_returns_none_on_timeout(self, mock_run, _mock_sleep):
        """gh_api should return None when subprocess times out."""
        from heisenberg.playground.discover import gh_api

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        result = gh_api("/repos/owner/repo")

        assert result is None

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_search_repos_returns_empty_on_timeout(self, mock_run, _mock_sleep):
        """search_repos should return empty list on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        result = search_repos("query", limit=10)

        assert result == []

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_get_failed_runs_returns_empty_on_timeout(self, mock_run, _mock_sleep):
        """get_failed_runs should return empty list on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        result = get_failed_runs("owner/repo")

        assert result == []

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_download_artifact_returns_false_on_timeout(self, mock_run, _mock_sleep):
        """download_artifact_to_dir should return False on timeout."""
        from heisenberg.playground.discover import download_artifact_to_dir

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=120)

        result = download_artifact_to_dir("owner/repo", "artifact", "/tmp/target")

        assert result is False

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_download_artifact_passes_timeout(self, mock_run, _mock_sleep):
        """download_artifact_to_dir should pass timeout to subprocess."""
        from heisenberg.playground.discover import TIMEOUT_DOWNLOAD, download_artifact_to_dir

        mock_run.return_value = MagicMock(returncode=0)

        download_artifact_to_dir("owner/repo", "artifact", "/tmp/target")

        _, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == TIMEOUT_DOWNLOAD

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_gh_api_passes_timeout(self, mock_run, _mock_sleep):
        """gh_api should pass timeout to subprocess."""
        from heisenberg.playground.discover import TIMEOUT_API, gh_api

        mock_run.return_value = MagicMock(
            stdout='{"ok": true}',
            returncode=0,
        )

        gh_api("/repos/owner/repo")

        _, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == TIMEOUT_API


# =============================================================================
# RATE LIMIT HANDLING
# =============================================================================


class TestRateLimitHandling:
    """Tests for rate limit handling."""

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_handles_rate_limit_error_gracefully(self, mock_run, _mock_sleep):
        """gh_api should return None after retries are exhausted."""
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, "gh", stderr="API rate limit exceeded")

        from heisenberg.playground.discover import gh_api

        result = gh_api("/repos/owner/repo")

        assert result is None


class TestIsRateLimitError:
    """Tests for _is_rate_limit_error helper."""

    def test_detects_rate_limit_text(self):
        """Should detect 'rate limit' in stderr."""
        exc = subprocess.CalledProcessError(1, "gh", stderr="API rate limit exceeded")
        assert _is_rate_limit_error(exc) is True

    def test_detects_abuse_text(self):
        """Should detect 'abuse' in stderr (GitHub secondary rate limit)."""
        exc = subprocess.CalledProcessError(
            1, "gh", stderr="You have triggered an abuse detection mechanism"
        )
        assert _is_rate_limit_error(exc) is True

    def test_case_insensitive(self):
        """Should detect rate limit regardless of case."""
        exc = subprocess.CalledProcessError(1, "gh", stderr="Rate Limit Exceeded")
        assert _is_rate_limit_error(exc) is True

    def test_false_for_other_errors(self):
        """Should return False for non-rate-limit errors."""
        exc = subprocess.CalledProcessError(1, "gh", stderr="Not Found")
        assert _is_rate_limit_error(exc) is False

    def test_false_for_empty_stderr(self):
        """Should return False when stderr is empty string."""
        exc = subprocess.CalledProcessError(1, "gh", stderr="")
        assert _is_rate_limit_error(exc) is False

    def test_false_for_none_stderr(self):
        """Should return False when stderr is None."""
        exc = subprocess.CalledProcessError(1, "gh", stderr=None)
        assert _is_rate_limit_error(exc) is False


class TestGhSubprocess:
    """Tests for _gh_subprocess throttle + retry wrapper."""

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_result_on_success(self, mock_run, mock_sleep, _mock_random):
        """Should return subprocess result on first attempt."""
        mock_run.return_value = MagicMock(stdout='{"ok": true}', returncode=0)

        result = _gh_subprocess(["gh", "api", "/test"])

        assert result.stdout == '{"ok": true}'
        mock_run.assert_called_once()

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_retries_on_rate_limit(self, mock_run, mock_sleep, _mock_random):
        """Should retry and succeed after transient rate limit."""
        rate_error = subprocess.CalledProcessError(1, "gh", stderr="rate limit exceeded")
        success = MagicMock(stdout='{"ok": true}', returncode=0)
        mock_run.side_effect = [rate_error, success]

        result = _gh_subprocess(["gh", "api", "/test"])

        assert result.stdout == '{"ok": true}'
        assert mock_run.call_count == 2

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_raises_after_max_retries(self, mock_run, mock_sleep, _mock_random):
        """Should raise CalledProcessError after exhausting all retries."""
        import pytest

        rate_error = subprocess.CalledProcessError(1, "gh", stderr="rate limit exceeded")
        mock_run.side_effect = rate_error

        with pytest.raises(subprocess.CalledProcessError):
            _gh_subprocess(["gh", "api", "/test"])

        assert mock_run.call_count == GH_MAX_RETRIES + 1

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_no_retry_on_other_errors(self, mock_run, mock_sleep, _mock_random):
        """Should raise immediately for non-rate-limit errors."""
        import pytest

        other_error = subprocess.CalledProcessError(1, "gh", stderr="Not Found")
        mock_run.side_effect = other_error

        with pytest.raises(subprocess.CalledProcessError):
            _gh_subprocess(["gh", "api", "/test"])

        mock_run.assert_called_once()

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_no_retry_on_timeout(self, mock_run, mock_sleep, _mock_random):
        """Should raise immediately on timeout (not retryable)."""
        import pytest

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        with pytest.raises(subprocess.TimeoutExpired):
            _gh_subprocess(["gh", "api", "/test"])

        mock_run.assert_called_once()

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_passes_timeout_parameter(self, mock_run, mock_sleep, _mock_random):
        """Should forward timeout to subprocess.run."""
        mock_run.return_value = MagicMock(stdout="{}", returncode=0)

        _gh_subprocess(["gh", "api", "/test"], timeout=60)

        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 60

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_jitter_before_each_attempt(self, mock_run, mock_sleep, _mock_random):
        """Should sleep with small jitter before each API call."""
        mock_run.return_value = MagicMock(stdout="{}", returncode=0)

        _gh_subprocess(["gh", "api", "/test"])

        # First sleep call is the jitter (0.1 from mocked random.uniform)
        assert mock_sleep.call_count >= 1
        assert mock_sleep.call_args_list[0] == ((0.1,),)

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_backoff_delays_increase(self, mock_run, mock_sleep, _mock_random):
        """Retry backoff delays should increase exponentially."""
        import pytest

        rate_error = subprocess.CalledProcessError(1, "gh", stderr="rate limit")
        mock_run.side_effect = rate_error

        with pytest.raises(subprocess.CalledProcessError):
            _gh_subprocess(["gh", "api", "/test"])

        # Extract backoff delays (>= 1.0s, vs jitter which is 0.1s)
        backoff_delays = [call[0][0] for call in mock_sleep.call_args_list if call[0][0] >= 1.0]
        assert len(backoff_delays) == GH_MAX_RETRIES
        # Each delay should be larger than the previous (exponential)
        for i in range(1, len(backoff_delays)):
            assert backoff_delays[i] > backoff_delays[i - 1]


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestDiscoverSources:
    """Tests for discover_sources function."""

    @patch("time.sleep")
    @patch("heisenberg.playground.discover.analyze_source")
    @patch("heisenberg.playground.discover.search_repos")
    def test_uses_default_queries(self, mock_search, mock_analyze, _mock_sleep):
        """Should use DEFAULT_QUERIES when queries not provided."""
        mock_search.return_value = []
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=100,
            status=SourceStatus.COMPATIBLE,
        )

        from heisenberg.playground.discover import discover_sources

        discover_sources(global_limit=10)

        # Should have called search for each default query
        assert mock_search.call_count == len(DEFAULT_QUERIES)


# =============================================================================
# FAILURE VERIFICATION TESTS (TDD - new functionality)
# =============================================================================


class TestSourceStatusNoFailures:
    """Tests for NO_FAILURES status - artifacts exist but no test failures."""

    def test_no_failures_status_exists(self):
        """SourceStatus should have NO_FAILURES value."""
        assert SourceStatus.NO_FAILURES.value == "no_failures"

    def test_no_failures_is_not_compatible(self):
        """NO_FAILURES status should NOT be considered compatible."""
        source = ProjectSource(
            repo="owner/repo",
            stars=1000,
            status=SourceStatus.NO_FAILURES,
            playwright_artifacts=["playwright-report"],
        )
        assert source.compatible is False


class TestVerifyHasFailures:
    """Tests for verify_has_failures function."""

    @patch("heisenberg.playground.discover.download_and_check_failures")
    def test_returns_true_when_failures_found(self, mock_download):
        """Should return True when artifact contains test failures."""

        mock_download.return_value = 5  # 5 failures found

        result = verify_has_failures("owner/repo", "123", "playwright-report")

        assert result is True

    @patch("heisenberg.playground.discover.download_and_check_failures")
    def test_returns_false_when_zero_failures(self, mock_download):
        """Should return False when artifact has zero failures."""

        mock_download.return_value = 0

        result = verify_has_failures("owner/repo", "123", "playwright-report")

        assert result is False

    @patch("heisenberg.playground.discover.download_and_check_failures")
    def test_returns_false_on_download_error(self, mock_download):
        """Should return False if artifact can't be downloaded/parsed."""

        mock_download.return_value = None  # Error indicator

        result = verify_has_failures("owner/repo", "123", "playwright-report")

        assert result is False


class TestDownloadAndCheckFailures:
    """Tests for download_and_check_failures function (legacy tests updated)."""

    @patch("heisenberg.playground.discover.extract_failure_count_from_dir")
    @patch("heisenberg.playground.discover.download_artifact_to_dir")
    def test_extracts_failure_count_from_blob_report(self, mock_download, mock_extract):
        """Should extract failure count from blob report stats."""

        mock_download.return_value = True
        mock_extract.return_value = 3  # 3 failures found

        result = download_and_check_failures("owner/repo", "123", "blob-report")

        assert result == 3

    @patch("heisenberg.playground.discover.extract_failure_count_from_dir")
    @patch("heisenberg.playground.discover.download_artifact_to_dir")
    def test_extracts_failure_count_from_json_report(self, mock_download, mock_extract):
        """Should extract failure count from JSON report stats."""

        mock_download.return_value = True
        mock_extract.return_value = 2  # 2 failures (unexpected)

        result = download_and_check_failures("owner/repo", "123", "playwright-report")

        assert result == 2

    @patch("heisenberg.playground.discover.download_artifact_to_dir")
    def test_returns_none_on_download_failure(self, mock_download):
        """Should return None if download fails."""

        mock_download.return_value = False

        result = download_and_check_failures("owner/repo", "123", "playwright-report")

        assert result is None


class TestDetermineStatusWithFailures:
    """Tests for determine_status with failure verification."""

    def test_no_failures_status_when_zero_failures(self):
        """Should return NO_FAILURES when has artifacts but failure_count=0."""
        status = determine_status(
            run_id="123",
            artifact_names=["playwright-report"],
            playwright_artifacts=["playwright-report"],
            failure_count=0,
        )
        assert status == SourceStatus.NO_FAILURES

    def test_compatible_when_has_failures(self):
        """Should return COMPATIBLE when has artifacts AND failures."""
        status = determine_status(
            run_id="123",
            artifact_names=["playwright-report"],
            playwright_artifacts=["playwright-report"],
            failure_count=5,
        )
        assert status == SourceStatus.COMPATIBLE

    def test_compatible_when_failure_count_none(self):
        """Should return COMPATIBLE when failure_count not checked (None)."""
        # Backwards compatibility - if we don't verify, assume compatible
        status = determine_status(
            run_id="123",
            artifact_names=["playwright-report"],
            playwright_artifacts=["playwright-report"],
            failure_count=None,
        )
        assert status == SourceStatus.COMPATIBLE


class TestAnalyzeSourceWithVerification:
    """Tests for analyze_source with failure verification."""

    @patch("heisenberg.playground.discover.verify_has_failures")
    @patch("heisenberg.playground.discover.find_valid_artifacts")
    @patch("heisenberg.playground.discover.get_repo_stars")
    def test_verifies_failures_when_enabled(self, mock_stars, mock_artifacts, mock_verify):
        """Should verify failures when verify_failures=True."""
        from heisenberg.playground.discover import analyze_source

        mock_stars.return_value = 100
        mock_artifacts.return_value = (
            "123",
            "url",
            ["playwright-report"],
            "2024-01-15T10:00:00Z",
            {"playwright-report": 50_000_000},
        )
        mock_verify.return_value = True  # Has failures

        source = analyze_source("owner/repo", verify_failures=True)

        mock_verify.assert_called_once()
        assert source.status == SourceStatus.COMPATIBLE

    @patch("heisenberg.playground.discover.verify_has_failures")
    @patch("heisenberg.playground.discover.find_valid_artifacts")
    @patch("heisenberg.playground.discover.get_repo_stars")
    def test_sets_no_failures_when_verification_fails(
        self, mock_stars, mock_artifacts, mock_verify
    ):
        """Should set NO_FAILURES when verification finds no failures."""
        from heisenberg.playground.discover import analyze_source

        mock_stars.return_value = 100
        mock_artifacts.return_value = (
            "123",
            "url",
            ["playwright-report"],
            "2024-01-15T10:00:00Z",
            {"playwright-report": 50_000_000},
        )
        mock_verify.return_value = False  # No failures

        source = analyze_source("owner/repo", verify_failures=True)

        assert source.status == SourceStatus.NO_FAILURES

    @patch("heisenberg.playground.discover.verify_has_failures")
    @patch("heisenberg.playground.discover.find_valid_artifacts")
    @patch("heisenberg.playground.discover.get_repo_stars")
    def test_skips_verification_when_disabled(self, mock_stars, mock_artifacts, mock_verify):
        """Should skip verification when verify_failures=False (default)."""
        from heisenberg.playground.discover import analyze_source

        mock_stars.return_value = 100
        mock_artifacts.return_value = (
            "123",
            "url",
            ["playwright-report"],
            "2024-01-15T10:00:00Z",
            {"playwright-report": 50_000_000},
        )

        source = analyze_source("owner/repo", verify_failures=False)

        mock_verify.assert_not_called()
        # Still marked compatible (legacy behavior)
        assert source.status == SourceStatus.COMPATIBLE


# =============================================================================
# KNOWN GOOD REPOS TESTS (TDD - curated list of reliable sources)
# =============================================================================


class TestKnownGoodRepos:
    """Tests for KNOWN_GOOD_REPOS - curated list of repos with Playwright failures."""

    def test_known_good_repos_exists(self):
        """KNOWN_GOOD_REPOS should be defined at module level."""
        from heisenberg.playground.discover import KNOWN_GOOD_REPOS

        assert KNOWN_GOOD_REPOS is not None
        assert isinstance(KNOWN_GOOD_REPOS, list)

    def test_known_good_repos_contains_microsoft_playwright(self):
        """microsoft/playwright should be in KNOWN_GOOD_REPOS."""
        from heisenberg.playground.discover import KNOWN_GOOD_REPOS

        assert "microsoft/playwright" in KNOWN_GOOD_REPOS

    def test_known_good_repos_are_strings(self):
        """All entries should be owner/repo format strings."""
        from heisenberg.playground.discover import KNOWN_GOOD_REPOS

        for repo in KNOWN_GOOD_REPOS:
            assert isinstance(repo, str)
            assert "/" in repo
            assert len(repo.split("/")) == 2


class TestDiscoverWithKnownGoodRepos:
    """Tests for discover_sources including known good repos."""

    @patch("heisenberg.playground.discover.analyze_source_with_status")
    @patch("heisenberg.playground.discover.search_repos")
    def test_includes_known_good_repos(self, mock_search, mock_analyze):
        """Should include KNOWN_GOOD_REPOS in addition to search results."""
        from heisenberg.playground.discover import KNOWN_GOOD_REPOS, discover_sources

        mock_search.return_value = ["other/repo"]
        mock_analyze.return_value = ProjectSource(
            repo="test/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        discover_sources(global_limit=50)

        # Should have analyzed known good repos
        analyzed_repos = [call[0][0] for call in mock_analyze.call_args_list]
        for known_repo in KNOWN_GOOD_REPOS:
            assert known_repo in analyzed_repos

    @patch("heisenberg.playground.discover.analyze_source_with_status")
    @patch("heisenberg.playground.discover.search_repos")
    def test_deduplicates_known_good_repos(self, mock_search, mock_analyze):
        """Should not analyze known good repo twice if also in search results."""
        from heisenberg.playground.discover import discover_sources

        # Search returns microsoft/playwright which is also in KNOWN_GOOD_REPOS
        mock_search.return_value = ["microsoft/playwright", "other/repo"]
        mock_analyze.return_value = ProjectSource(
            repo="test/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        discover_sources(global_limit=50)

        # microsoft/playwright should only be analyzed once
        analyzed_repos = [call[0][0] for call in mock_analyze.call_args_list]
        assert analyzed_repos.count("microsoft/playwright") == 1


class TestCheckMultipleRuns:
    """Tests for checking multiple failed runs to find one with failures."""

    @patch("heisenberg.playground.discover.get_run_artifacts")
    @patch("heisenberg.playground.discover.get_failed_runs")
    def test_find_valid_artifacts_returns_run_with_playwright_artifacts(
        self, mock_get_runs, mock_get_artifacts
    ):
        """Should return the first run that has non-expired Playwright artifacts."""
        mock_get_runs.return_value = [
            {"id": 100, "html_url": "url1", "created_at": "2024-01-01T00:00:00Z"},
            {"id": 200, "html_url": "url2", "created_at": "2024-01-02T00:00:00Z"},
            {"id": 300, "html_url": "url3", "created_at": "2024-01-03T00:00:00Z"},
        ]

        def artifacts_side_effect(repo, run_id):
            if run_id == "100":
                return [{"name": "coverage-report", "expired": False}]  # Not playwright
            if run_id == "200":
                return [{"name": "blob-report-1", "expired": False}]  # Playwright!
            return []

        mock_get_artifacts.side_effect = artifacts_side_effect

        run_id, run_url, artifacts, run_created_at, _ = find_valid_artifacts("owner/repo")

        # Should return run 200 which has playwright artifacts
        assert run_id == "200"
        assert "blob-report-1" in artifacts
        assert run_created_at == "2024-01-02T00:00:00Z"


class TestImprovedQueries:
    """Tests for improved search queries."""

    def test_queries_include_blob_report_pattern(self):
        """DEFAULT_QUERIES should include a query for blob-report pattern."""
        # At least one query should find repos that use blob-report
        blob_queries = [q for q in DEFAULT_QUERIES if "blob-report" in q.lower()]
        assert len(blob_queries) >= 1

    def test_queries_find_custom_upload_actions(self):
        """Should have query that finds repos with custom upload actions."""
        # Query that would find repos using blob-report without standard upload-artifact
        from heisenberg.playground.discover import DEFAULT_QUERIES

        # At least one query should not require "upload-artifact" verbatim
        flexible_queries = [
            q
            for q in DEFAULT_QUERIES
            if "blob-report" in q.lower() and "upload-artifact" not in q.lower()
        ]
        assert len(flexible_queries) >= 1


# =============================================================================
# PERFORMANCE OPTIMIZATION TESTS (TDD - fix slow --verify)
# =============================================================================


class TestDirectFileReading:
    """Tests for reading files directly from temp dir (no re-zipping)."""

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_download_artifact_to_dir_extracts_to_path(self, mock_run, _mock_sleep):
        """download_artifact_to_dir should extract artifact directly to given path."""
        from heisenberg.playground.discover import download_artifact_to_dir

        mock_run.return_value = MagicMock(returncode=0)

        result = download_artifact_to_dir("owner/repo", "artifact-name", "/tmp/target")

        assert result is True
        # Should call gh run download with -D flag pointing to target dir
        call_args = mock_run.call_args[0][0]
        assert "-D" in call_args
        assert "/tmp/target" in call_args

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_download_artifact_to_dir_returns_false_on_failure(self, mock_run, _mock_sleep):
        """download_artifact_to_dir should return False if gh command fails."""
        from subprocess import CalledProcessError

        from heisenberg.playground.discover import download_artifact_to_dir

        mock_run.side_effect = CalledProcessError(1, "gh")

        result = download_artifact_to_dir("owner/repo", "artifact-name", "/tmp/target")

        assert result is False


class TestExtractFailureCountFromDir:
    """Tests for extracting failure count directly from extracted files."""

    def test_extract_failure_count_from_dir_finds_json_stats(self, tmp_path):
        """Should find and parse JSON files with stats in extracted directory."""
        from heisenberg.playground.discover import extract_failure_count_from_dir

        # Create a mock extracted artifact structure
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps({"stats": {"failed": 7, "passed": 100}}))

        result = extract_failure_count_from_dir(tmp_path)

        assert result == 7

    def test_extract_failure_count_from_dir_handles_nested_zips(self, tmp_path):
        """Should handle blob reports with nested zip files."""
        import io
        import zipfile

        from heisenberg.playground.discover import extract_failure_count_from_dir

        # Create inner zip with stats
        inner_zip = io.BytesIO()
        with zipfile.ZipFile(inner_zip, "w") as zf:
            zf.writestr("data.json", json.dumps({"stats": {"failed": 3, "passed": 50}}))

        # Write as file in temp dir
        (tmp_path / "report-shard1.zip").write_bytes(inner_zip.getvalue())

        result = extract_failure_count_from_dir(tmp_path)

        assert result == 3

    def test_extract_failure_count_from_dir_returns_none_if_no_stats(self, tmp_path):
        """Should return None if no stats found in any file."""
        from heisenberg.playground.discover import extract_failure_count_from_dir

        # Create file without stats
        (tmp_path / "readme.txt").write_text("No stats here")

        result = extract_failure_count_from_dir(tmp_path)

        assert result is None


class TestOptimizedDownloadAndCheck:
    """Tests for optimized download_and_check_failures (no re-zipping)."""

    @patch("heisenberg.playground.discover.extract_failure_count_from_dir")
    @patch("heisenberg.playground.discover.download_artifact_to_dir")
    def test_uses_direct_file_reading(self, mock_download, mock_extract):
        """Should use direct file reading, not re-zipping."""

        mock_download.return_value = True
        mock_extract.return_value = 5

        result = download_and_check_failures("owner/repo", "123", "blob-report")

        assert result == 5
        mock_download.assert_called_once()
        mock_extract.assert_called_once()

    @patch("heisenberg.playground.discover.download_artifact_to_dir")
    def test_returns_none_on_download_failure(self, mock_download):
        """Should return None if download fails."""

        mock_download.return_value = False

        result = download_and_check_failures("owner/repo", "123", "blob-report")

        assert result is None


class TestParallelProcessing:
    """Tests for parallel source analysis."""

    @patch("heisenberg.playground.discover.analyze_source_with_status")
    @patch("heisenberg.playground.discover.search_repos")
    def test_discover_sources_uses_parallel_processing(self, mock_search, mock_analyze):
        """discover_sources should process repos in parallel when verify=True."""
        from heisenberg.playground.discover import discover_sources

        mock_search.return_value = ["repo1", "repo2", "repo3"]
        mock_analyze.return_value = ProjectSource(
            repo="test/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        # This should complete faster due to parallelism
        # We can't easily test timing, but we can verify it doesn't break
        discover_sources(global_limit=5, verify_failures=True)

        # Should have analyzed all repos (3 from search + 1 from KNOWN_GOOD_REPOS)
        assert mock_analyze.call_count >= 3

    @patch("heisenberg.playground.discover.analyze_source_with_status")
    @patch("heisenberg.playground.discover.search_repos")
    def test_parallel_processing_handles_exceptions(self, mock_search, mock_analyze):
        """Parallel processing should handle individual repo failures gracefully."""
        from heisenberg.playground.discover import discover_sources

        mock_search.return_value = ["repo1", "repo2"]

        def analyze_side_effect(repo, **kwargs):
            if repo == "repo1":
                raise Exception("API error")
            return ProjectSource(
                repo=repo,
                stars=1000,
                status=SourceStatus.COMPATIBLE,
            )

        mock_analyze.side_effect = analyze_side_effect

        # Should not raise, should return results for successful repos
        result = discover_sources(global_limit=5, verify_failures=True)

        # Should have at least one result (repo2)
        assert len(result) >= 1


class TestProgressCallback:
    """Tests for progress feedback during discovery."""

    @patch("time.sleep")
    @patch("heisenberg.playground.discover.analyze_source")
    @patch("heisenberg.playground.discover.search_repos")
    def test_discover_accepts_progress_callback(self, mock_search, mock_analyze, _mock_sleep):
        """discover_sources should accept optional progress callback."""
        from heisenberg.playground.discover import ProgressInfo, discover_sources

        mock_search.return_value = ["repo1", "repo2"]
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

        # Should have called progress for each repo
        assert len(progress_calls) >= 2


# =============================================================================
# IMPROVED LOGGING TESTS (TDD - better progress feedback)
# =============================================================================


class TestProgressInfo:
    """Tests for ProgressInfo dataclass."""

    def test_progress_info_exists(self):
        """ProgressInfo should be importable."""
        from heisenberg.playground.discover import ProgressInfo

        assert ProgressInfo is not None

    def test_progress_info_has_required_fields(self):
        """ProgressInfo should have completed, total, repo, status, elapsed_ms."""
        from heisenberg.playground.discover import ProgressInfo

        info = ProgressInfo(
            completed=1,
            total=10,
            repo="owner/repo",
            status="compatible",
            elapsed_ms=1234,
        )

        assert info.completed == 1
        assert info.total == 10
        assert info.repo == "owner/repo"
        assert info.status == "compatible"
        assert info.elapsed_ms == 1234

    def test_progress_info_optional_message(self):
        """ProgressInfo should support optional message field."""
        from heisenberg.playground.discover import ProgressInfo

        info = ProgressInfo(
            completed=1,
            total=10,
            repo="microsoft/playwright",
            status="compatible",
            elapsed_ms=50,
            message="skipped verify - known good",
        )

        assert info.message == "skipped verify - known good"


class TestFormatProgressLine:
    """Tests for format_progress_line function."""

    def test_format_progress_line_basic(self):
        """Should format progress line with completion order."""
        from heisenberg.playground.discover import ProgressInfo, format_progress_line

        info = ProgressInfo(
            completed=3,
            total=10,
            repo="owner/repo",
            status="compatible",
            elapsed_ms=1500,
        )

        line = format_progress_line(info)

        assert "[ 3/10]" in line
        assert "owner/repo" in line
        assert "1.5s" in line or "1500" in line

    def test_format_progress_line_shows_plus_for_compatible(self):
        """Should show + for compatible repos."""
        from heisenberg.playground.discover import ProgressInfo, format_progress_line

        info = ProgressInfo(
            completed=1, total=5, repo="good/repo", status="compatible", elapsed_ms=100
        )

        line = format_progress_line(info)

        assert "+" in line

    def test_format_progress_line_shows_dash_for_incompatible(self):
        """Should show - for non-compatible repos."""
        from heisenberg.playground.discover import ProgressInfo, format_progress_line

        info = ProgressInfo(
            completed=1, total=5, repo="bad/repo", status="no_artifacts", elapsed_ms=100
        )

        line = format_progress_line(info)

        assert "-" in line

    def test_format_progress_line_includes_message(self):
        """Should include optional message."""
        from heisenberg.playground.discover import ProgressInfo, format_progress_line

        info = ProgressInfo(
            completed=1,
            total=5,
            repo="microsoft/playwright",
            status="compatible",
            elapsed_ms=50,
            message="skipped verify",
        )

        line = format_progress_line(info)

        assert "skipped verify" in line


class TestThreadSafeProgress:
    """Tests for thread-safe progress reporting."""

    @patch("time.sleep")
    def test_discover_sources_returns_progress_info(self, _mock_sleep):
        """Progress callback should receive ProgressInfo objects."""
        from heisenberg.playground.discover import ProgressInfo, discover_sources

        with (
            patch("heisenberg.playground.discover.search_repos") as mock_search,
            patch("heisenberg.playground.discover.analyze_source") as mock_analyze,
        ):
            mock_search.return_value = ["repo1"]
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
        from heisenberg.playground.discover import discover_sources

        with (
            patch("heisenberg.playground.discover.search_repos") as mock_search,
            patch("heisenberg.playground.discover.analyze_source") as mock_analyze,
        ):
            mock_search.return_value = ["repo1", "repo2", "repo3"]
            mock_analyze.return_value = ProjectSource(
                repo="test/repo",
                stars=1000,
                status=SourceStatus.COMPATIBLE,
            )

            completed_numbers = []

            def on_progress(info):
                completed_numbers.append(info.completed)

            discover_sources(global_limit=5, on_progress=on_progress)

            # Should be sequential: 1, 2, 3, ... (not jumping around)
            assert completed_numbers == sorted(completed_numbers)

    @patch("time.sleep")
    def test_progress_output_order_matches_completed_number(self, _mock_sleep):
        """Progress callback should be called in order matching completed number.

        This tests that the callback is inside the lock to prevent race conditions.
        We run the test multiple times to increase chance of catching race conditions.
        """
        import threading

        from heisenberg.playground.discover import (
            discover_sources,
        )

        # Run multiple times to increase chance of catching race condition
        for attempt in range(5):
            with (
                patch("heisenberg.playground.discover.search_repos") as mock_search,
                patch("heisenberg.playground.discover.analyze_source") as mock_analyze,
                patch("heisenberg.playground.discover.KNOWN_GOOD_REPOS", []),
            ):  # Disable known good repos
                mock_search.return_value = ["repo1", "repo2", "repo3", "repo4"]

                # Simulate varying processing times to trigger race condition
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

                # The completed numbers in order of callback should be sequential: 1, 2, 3, 4
                # If race condition exists, we might see [2, 1, 3, 4] or similar
                assert results == [1, 2, 3, 4], (
                    f"Attempt {attempt}: Got {results}, expected [1, 2, 3, 4]"
                )


# =============================================================================
# RICH PROGRESS DISPLAY TESTS (TDD - real-time progress with spinners)
# =============================================================================


class TestRichProgressDisplay:
    """Tests for Rich-based progress display."""

    def test_create_progress_display_returns_rich_progress(self):
        """create_progress_display should return a Rich Progress object."""
        from heisenberg.playground.discover import create_progress_display

        progress = create_progress_display()

        # Should be a Rich Progress instance
        from rich.progress import Progress

        assert isinstance(progress, Progress)

    def test_progress_display_has_spinner_column(self):
        """Progress display should include a spinner for active tasks."""
        from heisenberg.playground.discover import create_progress_display

        progress = create_progress_display()

        # Check that SpinnerColumn is included
        column_types = [type(col).__name__ for col in progress.columns]
        assert "SpinnerColumn" in column_types

    def test_progress_display_has_elapsed_column(self):
        """Progress display should include a live elapsed timer."""
        from heisenberg.playground.discover import create_progress_display

        progress = create_progress_display()

        column_types = [type(col).__name__ for col in progress.columns]
        assert "TimeElapsedColumn" in column_types

    def test_progress_display_has_task_description(self):
        """Progress display should show task description."""
        from heisenberg.playground.discover import create_progress_display

        progress = create_progress_display()

        column_types = [type(col).__name__ for col in progress.columns]
        # Should have TextColumn or similar for description
        assert any("Column" in t for t in column_types)


class TestDiscoverWithRichProgress:
    """Tests for discover_sources with Rich progress display."""

    @patch("time.sleep")
    @patch("heisenberg.playground.discover.analyze_source")
    @patch("heisenberg.playground.discover.search_repos")
    def test_discover_shows_active_tasks(self, mock_search, mock_analyze, _mock_sleep):
        """discover_sources should show tasks while they're running."""
        from heisenberg.playground.discover import discover_sources

        mock_search.return_value = ["repo1", "repo2"]
        mock_analyze.return_value = ProjectSource(
            repo="test/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        # Should complete without error when show_progress=True
        result = discover_sources(
            global_limit=5,
            show_progress=True,
        )

        assert len(result) >= 1

    @patch("time.sleep")
    @patch("heisenberg.playground.discover.analyze_source")
    @patch("heisenberg.playground.discover.search_repos")
    def test_discover_works_without_progress(self, mock_search, mock_analyze, _mock_sleep):
        """discover_sources should work with show_progress=False."""
        from heisenberg.playground.discover import discover_sources

        mock_search.return_value = ["repo1"]
        mock_analyze.return_value = ProjectSource(
            repo="test/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        # Should work silently
        result = discover_sources(
            global_limit=5,
            show_progress=False,
        )

        assert len(result) >= 1


class TestAnalyzeWithStatusUpdates:
    """Tests for analyze_source_with_status showing current operation."""

    def test_analyze_source_with_status_exists(self):
        """analyze_source_with_status function should exist."""
        from heisenberg.playground.discover import analyze_source_with_status

        assert callable(analyze_source_with_status)

    @patch("heisenberg.playground.discover.get_repo_stars")
    @patch("heisenberg.playground.discover.find_valid_artifacts")
    def test_calls_status_callback_with_stages(self, mock_artifacts, mock_stars):
        """Should call status_callback with different stages."""
        from heisenberg.playground.discover import analyze_source_with_status

        mock_stars.return_value = 1000
        mock_artifacts.return_value = (
            "123",
            "url",
            ["playwright-report"],
            "2024-01-15T10:00:00Z",
            {"playwright-report": 50_000_000},
        )

        stages_seen = []

        def on_status(stage: str):
            stages_seen.append(stage)

        analyze_source_with_status(
            "owner/repo",
            verify_failures=False,
            on_status=on_status,
        )

        # Should have reported at least "fetching runs" stage
        assert len(stages_seen) >= 1
        assert any("runs" in s.lower() or "info" in s.lower() for s in stages_seen)

    @patch("heisenberg.playground.discover.verify_has_failures")
    @patch("heisenberg.playground.discover.get_repo_stars")
    @patch("heisenberg.playground.discover.find_valid_artifacts")
    def test_shows_downloading_stage_when_verifying(self, mock_artifacts, mock_stars, mock_verify):
        """Should show 'Downloading...' stage when verify_failures=True."""
        from heisenberg.playground.discover import analyze_source_with_status

        mock_stars.return_value = 1000
        mock_artifacts.return_value = (
            "123",
            "url",
            ["playwright-report"],
            "2024-01-15T10:00:00Z",
            {"playwright-report": 50_000_000},
        )
        mock_verify.return_value = True

        stages_seen = []

        def on_status(stage: str):
            stages_seen.append(stage)

        analyze_source_with_status(
            "other/repo",  # Not in KNOWN_GOOD_REPOS
            verify_failures=True,
            on_status=on_status,
        )

        # Should have a download/verify stage (stage text is "dl {size}" or "downloading...")
        assert any("dl" in s.lower() or "download" in s.lower() for s in stages_seen)


class TestSkipVerificationForKnownGoodRepos:
    """Tests for skipping verification on KNOWN_GOOD_REPOS."""

    @patch("heisenberg.playground.discover.verify_has_failures")
    @patch("heisenberg.playground.discover.find_valid_artifacts")
    @patch("heisenberg.playground.discover.get_repo_stars")
    def test_skips_verification_for_known_good_repos(self, mock_stars, mock_artifacts, mock_verify):
        """Should NOT call verify_has_failures for repos in KNOWN_GOOD_REPOS."""
        from heisenberg.playground.discover import KNOWN_GOOD_REPOS, analyze_source

        mock_stars.return_value = 80000
        mock_artifacts.return_value = (
            "123",
            "url",
            ["blob-report-1"],
            "2024-01-15T10:00:00Z",
            {"blob-report-1": 200_000_000},
        )

        # Analyze a known good repo with verify=True
        source = analyze_source(
            KNOWN_GOOD_REPOS[0],  # microsoft/playwright
            verify_failures=True,
        )

        # Should NOT have called verify (expensive download)
        mock_verify.assert_not_called()
        # Should still be marked COMPATIBLE (trusted)
        assert source.status == SourceStatus.COMPATIBLE

    @patch("heisenberg.playground.discover.verify_has_failures")
    @patch("heisenberg.playground.discover.find_valid_artifacts")
    @patch("heisenberg.playground.discover.get_repo_stars")
    def test_still_verifies_unknown_repos(self, mock_stars, mock_artifacts, mock_verify):
        """Should still verify repos NOT in KNOWN_GOOD_REPOS."""
        from heisenberg.playground.discover import analyze_source

        mock_stars.return_value = 1000
        mock_artifacts.return_value = (
            "123",
            "url",
            ["playwright-report"],
            "2024-01-15T10:00:00Z",
            {"playwright-report": 50_000_000},
        )
        mock_verify.return_value = True

        source = analyze_source("unknown/repo", verify_failures=True)

        # Should have called verify for unknown repo
        mock_verify.assert_called_once()
        assert source.status == SourceStatus.COMPATIBLE


# =============================================================================
# VERIFICATION CACHE TESTS (TDD - cache verified run results with TTL)
# =============================================================================


class TestRunCache:
    """Tests for RunCache - caching verified run results."""

    def test_run_cache_class_exists(self):
        """RunCache class should be importable."""
        from heisenberg.playground.discover import RunCache

        assert RunCache is not None

    def test_run_cache_get_returns_none_for_unknown_run(self):
        """get() should return None for runs not in cache."""
        from heisenberg.playground.discover import RunCache

        cache = RunCache()
        result = cache.get("unknown-run-id")

        assert result is None

    def test_run_cache_set_and_get(self):
        """set() should store value, get() should retrieve it."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache

        cache = RunCache()
        cache.set("run-123", 5, datetime.now().isoformat())

        result = cache.get("run-123")

        assert result == 5

    def test_run_cache_stores_zero_failures(self):
        """Should correctly store and retrieve 0 failures (not None)."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache

        cache = RunCache()
        cache.set("run-456", 0, datetime.now().isoformat())

        result = cache.get("run-456")

        assert result == 0
        assert result is not None


class TestRunCacheTTL:
    """Tests for RunCache TTL (90 days from run creation on GitHub)."""

    def test_cache_expires_when_run_older_than_90_days(self):
        """Entries for runs older than 90 days should return None."""
        from datetime import datetime, timedelta

        from heisenberg.playground.discover import RunCache

        cache = RunCache()

        # Run created 91 days ago on GitHub
        old_run_date = datetime.now() - timedelta(days=91)
        cache._data["runs"]["old-run"] = {
            "failure_count": 3,
            "run_created_at": old_run_date.isoformat(),
        }

        result = cache.get("old-run")

        assert result is None  # Expired - GitHub artifacts gone

    def test_cache_valid_when_run_within_90_days(self):
        """Entries for recent runs should be returned."""
        from datetime import datetime, timedelta

        from heisenberg.playground.discover import RunCache

        cache = RunCache()

        # Run created 30 days ago on GitHub
        recent_run_date = datetime.now() - timedelta(days=30)
        cache._data["runs"]["recent-run"] = {
            "failure_count": 7,
            "run_created_at": recent_run_date.isoformat(),
        }

        result = cache.get("recent-run")

        assert result == 7

    def test_cache_entry_at_89_days_is_valid(self):
        """Entry for run at 89 days should still be valid (just under TTL)."""
        from datetime import datetime, timedelta

        from heisenberg.playground.discover import RunCache

        cache = RunCache()

        # Run created 89 days ago on GitHub (within 90-day TTL)
        boundary_date = datetime.now() - timedelta(days=89)
        cache._data["runs"]["boundary-run"] = {
            "failure_count": 2,
            "run_created_at": boundary_date.isoformat(),
        }

        result = cache.get("boundary-run")

        assert result == 2


class TestRunCachePersistence:
    """Tests for RunCache persistence to JSON file."""

    def test_cache_save_creates_json_file(self, tmp_path):
        """save() should create JSON file at specified path."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache

        cache_file = tmp_path / ".cache" / "verified_runs.json"
        cache = RunCache(cache_path=cache_file)
        cache.set("run-123", 5, datetime.now().isoformat())
        cache.save()

        assert cache_file.exists()

    def test_cache_save_creates_parent_directory(self, tmp_path):
        """save() should create parent .cache directory if needed."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache

        cache_file = tmp_path / ".cache" / "verified_runs.json"
        cache = RunCache(cache_path=cache_file)
        cache.set("run-123", 5, datetime.now().isoformat())
        cache.save()

        assert (tmp_path / ".cache").is_dir()

    def test_cache_load_reads_existing_file(self, tmp_path):
        """load() should read data from existing JSON file."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache

        cache_file = tmp_path / "cache.json"
        # Write a cache file manually
        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "runs": {
                        "existing-run": {
                            "failure_count": 10,
                            "run_created_at": datetime.now().isoformat(),
                        }
                    },
                }
            )
        )

        cache = RunCache(cache_path=cache_file)

        result = cache.get("existing-run")

        assert result == 10

    def test_cache_handles_missing_file(self, tmp_path):
        """Should handle missing cache file gracefully."""
        from heisenberg.playground.discover import RunCache

        cache_file = tmp_path / "nonexistent.json"
        cache = RunCache(cache_path=cache_file)

        # Should not raise, should return None
        result = cache.get("any-run")

        assert result is None

    def test_cache_handles_corrupt_json(self, tmp_path):
        """Should handle corrupt JSON file gracefully."""
        from heisenberg.playground.discover import RunCache

        cache_file = tmp_path / "corrupt.json"
        cache_file.write_text("not valid json {{{")

        cache = RunCache(cache_path=cache_file)

        # Should not raise, should return None
        result = cache.get("any-run")

        assert result is None


class TestRunCacheSchemaVersion:
    """Tests for cache schema versioning."""

    def test_cache_includes_schema_version(self, tmp_path):
        """Saved cache should include schema_version."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache

        cache_file = tmp_path / "cache.json"
        cache = RunCache(cache_path=cache_file)
        cache.set("run-1", 3, datetime.now().isoformat())
        cache.save()

        data = json.loads(cache_file.read_text())

        assert "schema_version" in data
        assert data["schema_version"] == 1

    def test_cache_ignores_old_schema_version(self, tmp_path):
        """Should ignore cache with older schema version."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache

        cache_file = tmp_path / "cache.json"
        # Write cache with old schema
        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": 0,  # Old version
                    "runs": {
                        "old-run": {
                            "failure_count": 5,
                            "run_created_at": datetime.now().isoformat(),
                        }
                    },
                }
            )
        )

        cache = RunCache(cache_path=cache_file)

        # Should ignore old schema data
        result = cache.get("old-run")

        assert result is None


class TestVerifyWithCache:
    """Tests for integration of cache with verification."""

    @patch("heisenberg.playground.discover.download_and_check_failures")
    def test_verify_uses_cache_hit(self, mock_download):
        """verify_has_failures should use cached result if available."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache, verify_has_failures_cached

        cache = RunCache()
        # Pre-populate cache with recent run
        run_created_at = datetime.now().isoformat()
        cache.set("123", 5, run_created_at)

        result = verify_has_failures_cached("owner/repo", "123", "artifact", cache, run_created_at)

        # Should NOT call download - used cache
        mock_download.assert_not_called()
        assert result is True

    @patch("heisenberg.playground.discover.download_and_check_failures")
    def test_verify_downloads_on_cache_miss(self, mock_download):
        """verify_has_failures should download if not in cache."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache, verify_has_failures_cached

        mock_download.return_value = 3

        cache = RunCache()
        run_created_at = datetime.now().isoformat()
        result = verify_has_failures_cached("owner/repo", "999", "artifact", cache, run_created_at)

        mock_download.assert_called_once()
        assert result is True

    @patch("heisenberg.playground.discover.download_and_check_failures")
    def test_verify_stores_result_in_cache(self, mock_download):
        """verify_has_failures should store result in cache after download."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache, verify_has_failures_cached

        mock_download.return_value = 7

        cache = RunCache()
        run_created_at = datetime.now().isoformat()
        verify_has_failures_cached("owner/repo", "new-run", "artifact", cache, run_created_at)

        # Should be in cache now
        assert cache.get("new-run") == 7

    @patch("heisenberg.playground.discover.download_and_check_failures")
    def test_verify_caches_zero_failures(self, mock_download):
        """Should cache 0 failures (important for NO_FAILURES status)."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache, verify_has_failures_cached

        mock_download.return_value = 0

        cache = RunCache()
        run_created_at = datetime.now().isoformat()
        result = verify_has_failures_cached(
            "owner/repo", "zero-run", "artifact", cache, run_created_at
        )

        assert result is False  # 0 failures = False
        assert cache.get("zero-run") == 0  # But stored as 0, not None


class TestRunCacheThreadSafety:
    """Tests for thread-safe RunCache with auto-save."""

    def test_cache_has_lock(self):
        """RunCache should have a threading lock (reentrant for nested calls)."""
        import threading

        from heisenberg.playground.discover import RunCache

        cache = RunCache()

        assert hasattr(cache, "_lock")
        assert isinstance(cache._lock, type(threading.RLock()))

    def test_cache_auto_saves_on_set(self, tmp_path):
        """set() should automatically save to disk."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache

        cache_file = tmp_path / "cache.json"
        cache = RunCache(cache_path=cache_file)

        cache.set("run-1", 5, datetime.now().isoformat())

        # File should exist immediately after set()
        assert cache_file.exists()

        # Read back and verify
        cache2 = RunCache(cache_path=cache_file)
        assert cache2.get("run-1") == 5

    def test_cache_thread_safe_concurrent_writes(self, tmp_path):
        """Multiple threads writing should not corrupt cache."""
        import threading
        from datetime import datetime

        from heisenberg.playground.discover import RunCache

        cache_file = tmp_path / "cache.json"
        cache = RunCache(cache_path=cache_file)
        run_created_at = datetime.now().isoformat()

        errors = []

        def write_entry(i):
            try:
                cache.set(f"run-{i}", i, run_created_at)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_entry, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # All entries should be present
        for i in range(20):
            assert cache.get(f"run-{i}") == i

    def test_cache_get_uses_lock(self, tmp_path):
        """get() should use lock for thread-safe reads."""
        import threading
        from datetime import datetime

        from heisenberg.playground.discover import RunCache

        cache_file = tmp_path / "cache.json"
        cache = RunCache(cache_path=cache_file)
        run_created_at = datetime.now().isoformat()

        # Pre-populate cache
        for i in range(10):
            cache.set(f"run-{i}", i, run_created_at)

        errors = []
        results = []

        def read_and_write(i):
            try:
                # Concurrent reads and writes
                cache.get(f"run-{i % 10}")
                cache.set(f"new-run-{i}", i, run_created_at)
                result = cache.get(f"new-run-{i}")
                results.append((i, result))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_and_write, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # All writes should be readable
        for i, result in results:
            assert result == i

    def test_cache_save_uses_lock(self, tmp_path):
        """save() should use lock to prevent file corruption."""
        import threading
        from datetime import datetime

        from heisenberg.playground.discover import RunCache

        cache_file = tmp_path / "cache.json"
        cache = RunCache(cache_path=cache_file)
        run_created_at = datetime.now().isoformat()

        errors = []

        def write_and_save(i):
            try:
                cache._data["runs"][f"direct-{i}"] = {
                    "failure_count": i,
                    "run_created_at": run_created_at,
                }
                cache.save()  # Direct save call
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_and_save, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # File should be valid JSON
        cache2 = RunCache(cache_path=cache_file)
        assert cache2._data["schema_version"] == 1


class TestRunCachePruning:
    """Tests for automatic cleanup of expired cache entries."""

    def test_cache_prunes_expired_entries_on_load(self, tmp_path):
        """Expired entries should be removed when cache is loaded."""
        from datetime import datetime, timedelta

        from heisenberg.playground.discover import CACHE_TTL_DAYS, RunCache

        cache_file = tmp_path / "cache.json"

        # Create cache with old and new entries
        old_date = (datetime.now() - timedelta(days=CACHE_TTL_DAYS + 10)).isoformat()
        recent_date = datetime.now().isoformat()

        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "runs": {
                        "old-run": {"failure_count": 5, "run_created_at": old_date},
                        "recent-run": {"failure_count": 3, "run_created_at": recent_date},
                    },
                }
            )
        )

        # Load cache - should prune old entries
        cache = RunCache(cache_path=cache_file)

        # Old entry should be gone
        assert "old-run" not in cache._data["runs"]
        # Recent entry should remain
        assert "recent-run" in cache._data["runs"]

    def test_cache_prunes_corrupt_entries(self, tmp_path):
        """Entries with invalid dates should be pruned."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache

        cache_file = tmp_path / "cache.json"

        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "runs": {
                        "corrupt-run": {"failure_count": 5, "run_created_at": "not-a-date"},
                        "missing-date-run": {"failure_count": 3},
                        "valid-run": {
                            "failure_count": 1,
                            "run_created_at": datetime.now().isoformat(),
                        },
                    },
                }
            )
        )

        cache = RunCache(cache_path=cache_file)

        # Corrupt entries should be gone
        assert "corrupt-run" not in cache._data["runs"]
        assert "missing-date-run" not in cache._data["runs"]
        # Valid entry should remain
        assert "valid-run" in cache._data["runs"]

    def test_cache_saves_after_pruning(self, tmp_path):
        """Cache should save to disk after pruning expired entries."""
        from datetime import datetime, timedelta

        from heisenberg.playground.discover import CACHE_TTL_DAYS, RunCache

        cache_file = tmp_path / "cache.json"

        old_date = (datetime.now() - timedelta(days=CACHE_TTL_DAYS + 10)).isoformat()
        recent_date = datetime.now().isoformat()

        cache_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "runs": {
                        "old-run": {"failure_count": 5, "run_created_at": old_date},
                        "recent-run": {"failure_count": 3, "run_created_at": recent_date},
                    },
                }
            )
        )

        # Load and prune
        RunCache(cache_path=cache_file)

        # Reload and verify old entry is gone from disk
        data = json.loads(cache_file.read_text())
        assert "old-run" not in data["runs"]
        assert "recent-run" in data["runs"]

    def test_cache_no_save_if_nothing_pruned(self, tmp_path):
        """Cache should not save if no entries were pruned."""
        from datetime import datetime

        from heisenberg.playground.discover import RunCache

        cache_file = tmp_path / "cache.json"
        recent_date = datetime.now().isoformat()

        original_content = json.dumps(
            {
                "schema_version": 1,
                "runs": {
                    "run-1": {"failure_count": 5, "run_created_at": recent_date},
                },
            }
        )
        cache_file.write_text(original_content)
        original_mtime = cache_file.stat().st_mtime

        # Small delay to detect mtime change
        import time

        time.sleep(0.01)

        # Load cache - nothing to prune
        RunCache(cache_path=cache_file)

        # File should not be modified
        assert cache_file.stat().st_mtime == original_mtime


class TestDefaultCachePath:
    """Tests for XDG-compliant default cache path."""

    def test_default_cache_path_is_absolute(self):
        """DEFAULT_CACHE_PATH should be an absolute path in user's home."""
        from heisenberg.playground.discover import get_default_cache_path

        path = get_default_cache_path()

        assert path.is_absolute()

    def test_default_cache_path_in_user_cache_dir(self):
        """Default cache should be in ~/.cache/heisenberg/."""
        from pathlib import Path

        from heisenberg.playground.discover import get_default_cache_path

        path = get_default_cache_path()

        # Should be under user's home directory
        assert str(Path.home()) in str(path)
        assert "heisenberg" in str(path)

    def test_default_cache_path_filename(self):
        """Default cache filename should be verified_runs.json."""
        from heisenberg.playground.discover import get_default_cache_path

        path = get_default_cache_path()

        assert path.name == "verified_runs.json"


class TestNoCacheFlag:
    """Tests for --no-cache CLI flag."""

    @patch("heisenberg.playground.discover.analyze_source_with_status")
    @patch("heisenberg.playground.discover.search_repos")
    def test_discover_accepts_no_cache_flag(self, mock_search, mock_analyze):
        """discover_sources should accept cache_path=None to disable cache."""
        from heisenberg.playground.discover import discover_sources

        mock_search.return_value = ["repo1"]
        mock_analyze.return_value = ProjectSource(
            repo="repo1",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        # Should not raise when cache_path=None
        result = discover_sources(
            global_limit=5,
            verify_failures=True,
            cache_path=None,  # Explicitly disable cache
        )

        assert len(result) >= 1

    def test_cli_has_no_cache_argument(self):
        """CLI parser should have --no-cache argument."""
        from heisenberg.playground.discover import create_argument_parser

        parser = create_argument_parser()
        args = parser.parse_args(["--no-cache"])

        assert args.no_cache is True

    def test_cli_no_cache_disables_caching(self):
        """--no-cache should set cache_path to None."""
        from heisenberg.playground.discover import create_argument_parser

        parser = create_argument_parser()

        # Without --no-cache
        args1 = parser.parse_args([])
        assert args1.no_cache is False

        # With --no-cache
        args2 = parser.parse_args(["--no-cache"])
        assert args2.no_cache is True


class TestFindValidArtifactsReturnsRunCreatedAt:
    """Tests for find_valid_artifacts returning run_created_at for cache."""

    @patch("heisenberg.playground.discover.get_run_artifacts")
    @patch("heisenberg.playground.discover.get_failed_runs")
    def test_find_valid_artifacts_returns_run_created_at(self, mock_get_runs, mock_get_artifacts):
        """find_valid_artifacts should return run's created_at timestamp."""
        from heisenberg.playground.discover import find_valid_artifacts

        mock_get_runs.return_value = [
            {
                "id": 100,
                "html_url": "url1",
                "created_at": "2024-01-15T10:30:00Z",
            },
        ]
        mock_get_artifacts.return_value = [{"name": "playwright-report", "expired": False}]

        run_id, run_url, artifacts, run_created_at, _ = find_valid_artifacts("owner/repo")

        assert run_id == "100"
        assert run_created_at == "2024-01-15T10:30:00Z"
