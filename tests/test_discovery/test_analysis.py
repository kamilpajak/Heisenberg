"""Tests for artifact analysis, verification, and status determination."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from heisenberg.discovery.analysis import (
    _extract_failure_count_from_html,
    _extract_failure_count_from_jsonl,
    determine_status,
    download_and_check_failures,
    extract_failure_count_from_dir,
    filter_expired_artifacts,
    find_valid_artifacts,
    is_playwright_artifact,
    sort_sources,
    verify_has_failures,
)
from heisenberg.discovery.models import (
    ProjectSource,
    SourceStatus,
)

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


class TestSortSources:
    """Tests for sort_sources function."""

    def test_sorts_compatible_first(self):
        """Compatible sources should come before non-compatible."""
        sources = [
            ProjectSource(repo="a", stars=1000, status=SourceStatus.HAS_ARTIFACTS),
            ProjectSource(repo="b", stars=100, status=SourceStatus.COMPATIBLE),
        ]
        sorted_list = sort_sources(sources)
        assert sorted_list[0].repo == "b"

    def test_sorts_by_stars_within_same_status(self):
        """Higher stars should come first within same compatibility."""
        sources = [
            ProjectSource(repo="a", stars=100, status=SourceStatus.COMPATIBLE),
            ProjectSource(repo="b", stars=500, status=SourceStatus.COMPATIBLE),
        ]
        sorted_list = sort_sources(sources)
        assert sorted_list[0].repo == "b"


class TestFindValidArtifacts:
    """Tests for find_valid_artifacts function."""

    @patch("heisenberg.discovery.analysis.get_run_artifacts")
    @patch("heisenberg.discovery.analysis.get_failed_runs")
    def test_checks_multiple_runs(self, mock_get_runs, mock_get_artifacts):
        """Should check multiple runs until valid artifacts found."""
        mock_get_runs.return_value = [
            {"id": 100, "html_url": "url1", "created_at": "2024-01-01T00:00:00Z"},
            {"id": 200, "html_url": "url2", "created_at": "2024-01-02T00:00:00Z"},
        ]

        def artifacts_side_effect(repo, run_id):
            if run_id == "100":
                return []
            return [{"name": "playwright-report", "expired": False}]

        mock_get_artifacts.side_effect = artifacts_side_effect

        run_id, run_url, artifacts, run_created_at, _ = find_valid_artifacts("owner/repo")

        assert run_id == "200"
        assert "playwright-report" in artifacts
        assert run_created_at == "2024-01-02T00:00:00Z"

    @patch("heisenberg.discovery.analysis.get_run_artifacts")
    @patch("heisenberg.discovery.analysis.get_failed_runs")
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


class TestAnalyzeCandidate:
    """Tests for analyze_source function."""

    @patch("heisenberg.discovery.analysis.find_valid_artifacts")
    @patch("heisenberg.discovery.analysis.get_repo_stars")
    def test_uses_provided_stars(self, mock_get_stars, mock_find_artifacts):
        """Should use stars provided as argument, not make API call."""
        from heisenberg.discovery.analysis import analyze_source

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

    @patch("heisenberg.discovery.analysis.find_valid_artifacts")
    @patch("heisenberg.discovery.analysis.get_repo_stars")
    def test_fetches_stars_when_not_provided(self, mock_get_stars, mock_find_artifacts):
        """Should fetch stars via API when not provided."""
        from heisenberg.discovery.analysis import analyze_source

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

    @patch("heisenberg.discovery.analysis.find_valid_artifacts")
    @patch("heisenberg.discovery.analysis.get_repo_stars")
    def test_sets_correct_status(self, mock_get_stars, mock_find_artifacts):
        """Should set correct status based on artifacts."""
        from heisenberg.discovery.analysis import analyze_source

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
# FAILURE VERIFICATION TESTS
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

    @patch("heisenberg.discovery.analysis.download_and_check_failures")
    def test_returns_true_when_failures_found(self, mock_download):
        """Should return True when artifact contains test failures."""
        mock_download.return_value = 5

        result = verify_has_failures("owner/repo", "playwright-report")

        assert result is True

    @patch("heisenberg.discovery.analysis.download_and_check_failures")
    def test_returns_false_when_zero_failures(self, mock_download):
        """Should return False when artifact has zero failures."""
        mock_download.return_value = 0

        result = verify_has_failures("owner/repo", "playwright-report")

        assert result is False

    @patch("heisenberg.discovery.analysis.download_and_check_failures")
    def test_returns_false_on_download_error(self, mock_download):
        """Should return False if artifact can't be downloaded/parsed."""
        mock_download.return_value = None

        result = verify_has_failures("owner/repo", "playwright-report")

        assert result is False


class TestDownloadAndCheckFailures:
    """Tests for download_and_check_failures function (legacy tests updated)."""

    @patch("heisenberg.discovery.analysis.extract_failure_count_from_dir")
    @patch("heisenberg.discovery.analysis.download_artifact_to_dir")
    def test_extracts_failure_count_from_blob_report(self, mock_download, mock_extract):
        """Should extract failure count from blob report stats."""
        mock_download.return_value = True
        mock_extract.return_value = 3

        result = download_and_check_failures("owner/repo", "blob-report")

        assert result == 3

    @patch("heisenberg.discovery.analysis.extract_failure_count_from_dir")
    @patch("heisenberg.discovery.analysis.download_artifact_to_dir")
    def test_extracts_failure_count_from_json_report(self, mock_download, mock_extract):
        """Should extract failure count from JSON report stats."""
        mock_download.return_value = True
        mock_extract.return_value = 2

        result = download_and_check_failures("owner/repo", "playwright-report")

        assert result == 2

    @patch("heisenberg.discovery.analysis.download_artifact_to_dir")
    def test_returns_none_on_download_failure(self, mock_download):
        """Should return None if download fails."""
        mock_download.return_value = False

        result = download_and_check_failures("owner/repo", "playwright-report")

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
        status = determine_status(
            run_id="123",
            artifact_names=["playwright-report"],
            playwright_artifacts=["playwright-report"],
            failure_count=None,
        )
        assert status == SourceStatus.COMPATIBLE


class TestAnalyzeSourceWithVerification:
    """Tests for analyze_source with failure verification."""

    @patch("heisenberg.discovery.analysis.verify_has_failures")
    @patch("heisenberg.discovery.analysis.find_valid_artifacts")
    @patch("heisenberg.discovery.analysis.get_repo_stars")
    def test_verifies_failures_when_enabled(self, mock_stars, mock_artifacts, mock_verify):
        """Should verify failures when verify_failures=True."""
        from heisenberg.discovery.analysis import analyze_source

        mock_stars.return_value = 100
        mock_artifacts.return_value = (
            "123",
            "url",
            ["playwright-report"],
            "2024-01-15T10:00:00Z",
            {"playwright-report": 50_000_000},
        )
        mock_verify.return_value = True

        source = analyze_source("owner/repo", verify_failures=True)

        mock_verify.assert_called_once()
        assert source.status == SourceStatus.COMPATIBLE

    @patch("heisenberg.discovery.analysis.verify_has_failures")
    @patch("heisenberg.discovery.analysis.find_valid_artifacts")
    @patch("heisenberg.discovery.analysis.get_repo_stars")
    def test_sets_no_failures_when_verification_fails(
        self, mock_stars, mock_artifacts, mock_verify
    ):
        """Should set NO_FAILURES when verification finds no failures."""
        from heisenberg.discovery.analysis import analyze_source

        mock_stars.return_value = 100
        mock_artifacts.return_value = (
            "123",
            "url",
            ["playwright-report"],
            "2024-01-15T10:00:00Z",
            {"playwright-report": 50_000_000},
        )
        mock_verify.return_value = False

        source = analyze_source("owner/repo", verify_failures=True)

        assert source.status == SourceStatus.NO_FAILURES

    @patch("heisenberg.discovery.analysis.verify_has_failures")
    @patch("heisenberg.discovery.analysis.find_valid_artifacts")
    @patch("heisenberg.discovery.analysis.get_repo_stars")
    def test_skips_verification_when_disabled(self, mock_stars, mock_artifacts, mock_verify):
        """Should skip verification when verify_failures=False (default)."""
        from heisenberg.discovery.analysis import analyze_source

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
        assert source.status == SourceStatus.COMPATIBLE


class TestCheckMultipleRuns:
    """Tests for checking multiple failed runs to find one with failures."""

    @patch("heisenberg.discovery.analysis.get_run_artifacts")
    @patch("heisenberg.discovery.analysis.get_failed_runs")
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
                return [{"name": "coverage-report", "expired": False}]
            if run_id == "200":
                return [{"name": "blob-report-1", "expired": False}]
            return []

        mock_get_artifacts.side_effect = artifacts_side_effect

        run_id, run_url, artifacts, run_created_at, _ = find_valid_artifacts("owner/repo")

        assert run_id == "200"
        assert "blob-report-1" in artifacts
        assert run_created_at == "2024-01-02T00:00:00Z"


# =============================================================================
# PERFORMANCE OPTIMIZATION TESTS
# =============================================================================


class TestDirectFileReading:
    """Tests for reading files directly from temp dir (no re-zipping)."""

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_download_artifact_to_dir_extracts_to_path(self, mock_run, _mock_sleep):
        """download_artifact_to_dir should extract artifact directly to given path."""
        from heisenberg.discovery.client import download_artifact_to_dir

        mock_run.return_value = MagicMock(returncode=0)

        result = download_artifact_to_dir("owner/repo", "artifact-name", "/tmp/target")

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert "-D" in call_args
        assert "/tmp/target" in call_args

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_download_artifact_to_dir_returns_false_on_failure(self, mock_run, _mock_sleep):
        """download_artifact_to_dir should return False if gh command fails."""
        from subprocess import CalledProcessError

        from heisenberg.discovery.client import download_artifact_to_dir

        mock_run.side_effect = CalledProcessError(1, "gh")

        result = download_artifact_to_dir("owner/repo", "artifact-name", "/tmp/target")

        assert result is False


class TestExtractFailureCountFromDir:
    """Tests for extracting failure count directly from extracted files."""

    def test_extract_failure_count_from_dir_finds_json_stats(self, tmp_path):
        """Should find and parse JSON files with stats in extracted directory."""
        from heisenberg.discovery.analysis import extract_failure_count_from_dir

        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps({"stats": {"failed": 7, "passed": 100}}))

        result = extract_failure_count_from_dir(tmp_path)

        assert result == 7

    def test_extract_failure_count_from_dir_handles_nested_zips(self, tmp_path):
        """Should handle blob reports with nested zip files."""
        import io
        import zipfile

        from heisenberg.discovery.analysis import extract_failure_count_from_dir

        inner_zip = io.BytesIO()
        with zipfile.ZipFile(inner_zip, "w") as zf:
            zf.writestr("data.json", json.dumps({"stats": {"failed": 3, "passed": 50}}))

        (tmp_path / "report-shard1.zip").write_bytes(inner_zip.getvalue())

        result = extract_failure_count_from_dir(tmp_path)

        assert result == 3

    def test_extract_failure_count_from_dir_returns_none_if_no_stats(self, tmp_path):
        """Should return None if no stats found in any file."""
        from heisenberg.discovery.analysis import extract_failure_count_from_dir

        (tmp_path / "readme.txt").write_text("No stats here")

        result = extract_failure_count_from_dir(tmp_path)

        assert result is None


class TestOptimizedDownloadAndCheck:
    """Tests for optimized download_and_check_failures (no re-zipping)."""

    @patch("heisenberg.discovery.analysis.extract_failure_count_from_dir")
    @patch("heisenberg.discovery.analysis.download_artifact_to_dir")
    def test_uses_direct_file_reading(self, mock_download, mock_extract):
        """Should use direct file reading, not re-zipping."""
        mock_download.return_value = True
        mock_extract.return_value = 5

        result = download_and_check_failures("owner/repo", "blob-report")

        assert result == 5
        mock_download.assert_called_once()
        mock_extract.assert_called_once()

    @patch("heisenberg.discovery.analysis.download_artifact_to_dir")
    def test_returns_none_on_download_failure(self, mock_download):
        """Should return None if download fails."""
        mock_download.return_value = False

        result = download_and_check_failures("owner/repo", "blob-report")

        assert result is None


class TestFindValidArtifactsReturnsRunCreatedAt:
    """Tests for find_valid_artifacts returning run_created_at for cache."""

    @patch("heisenberg.discovery.analysis.get_run_artifacts")
    @patch("heisenberg.discovery.analysis.get_failed_runs")
    def test_find_valid_artifacts_returns_run_created_at(self, mock_get_runs, mock_get_artifacts):
        """find_valid_artifacts should return run's created_at timestamp."""
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


class TestAnalyzeWithStatusUpdates:
    """Tests for analyze_source_with_status showing current operation."""

    def test_analyze_source_with_status_exists(self):
        """analyze_source_with_status function should exist."""
        from heisenberg.discovery.analysis import analyze_source_with_status

        assert callable(analyze_source_with_status)

    @patch("heisenberg.discovery.analysis.get_repo_stars")
    @patch("heisenberg.discovery.analysis.find_valid_artifacts")
    def test_calls_status_callback_with_stages(self, mock_artifacts, mock_stars):
        """Should call status_callback with different stages."""
        from heisenberg.discovery.analysis import analyze_source_with_status

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

        assert len(stages_seen) >= 1
        assert any("runs" in s.lower() or "info" in s.lower() for s in stages_seen)

    @patch("heisenberg.discovery.analysis.verify_has_failures")
    @patch("heisenberg.discovery.analysis.get_repo_stars")
    @patch("heisenberg.discovery.analysis.find_valid_artifacts")
    def test_shows_downloading_stage_when_verifying(self, mock_artifacts, mock_stars, mock_verify):
        """Should show 'Downloading...' stage when verify_failures=True."""
        from heisenberg.discovery.analysis import analyze_source_with_status

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
            "other/repo",
            verify_failures=True,
            on_status=on_status,
        )

        assert any("dl" in s.lower() or "download" in s.lower() for s in stages_seen)

    @patch("heisenberg.discovery.analysis._verify_artifact_failures")
    @patch("heisenberg.discovery.analysis.get_repo_stars")
    @patch("heisenberg.discovery.analysis.find_valid_artifacts")
    def test_returns_unsupported_format_on_html_report(
        self, mock_artifacts, mock_stars, mock_verify
    ):
        """Should return UNSUPPORTED_FORMAT when HtmlReportNotSupported is raised."""
        from heisenberg.core.exceptions import HtmlReportNotSupported
        from heisenberg.discovery.analysis import analyze_source_with_status

        mock_stars.return_value = 1000
        mock_artifacts.return_value = (
            "123",
            "https://github.com/owner/repo/actions/runs/123",
            ["playwright-report"],
            "2024-01-15T10:00:00Z",
            {"playwright-report": 50_000_000},
        )
        mock_verify.side_effect = HtmlReportNotSupported()

        result = analyze_source_with_status(
            "owner/repo",
            verify_failures=True,
        )

        assert result.status == SourceStatus.UNSUPPORTED_FORMAT
        assert result.repo == "owner/repo"
        assert result.stars == 1000
        assert result.playwright_artifacts == ["playwright-report"]
        assert result.run_id == "123"


# =============================================================================
# JSONL BLOB REPORT PARSING TESTS
# =============================================================================


class TestExtractFailureCountFromJsonl:
    """Tests for parsing JSONL blob report format (Playwright merge-reports)."""

    def test_extracts_failures_from_onend(self):
        """Should extract failure count from onEnd event with 'failed' status."""
        jsonl = "\n".join(
            [
                json.dumps({"method": "onTestEnd", "params": {"result": {"status": "failed"}}}),
                json.dumps({"method": "onTestEnd", "params": {"result": {"status": "passed"}}}),
                json.dumps({"method": "onEnd", "params": {"result": {"status": "failed"}}}),
            ]
        )

        result = _extract_failure_count_from_jsonl(jsonl)

        assert result == 1

    def test_returns_zero_when_all_pass(self):
        """Should return 0 when all tests pass."""
        jsonl = "\n".join(
            [
                json.dumps({"method": "onTestEnd", "params": {"result": {"status": "passed"}}}),
                json.dumps({"method": "onTestEnd", "params": {"result": {"status": "skipped"}}}),
                json.dumps({"method": "onEnd", "params": {"result": {"status": "passed"}}}),
            ]
        )

        result = _extract_failure_count_from_jsonl(jsonl)

        assert result == 0

    def test_counts_failed_and_timed_out(self):
        """Should count both 'failed' and 'timedOut' as failures."""
        jsonl = "\n".join(
            [
                json.dumps({"method": "onTestEnd", "params": {"result": {"status": "failed"}}}),
                json.dumps({"method": "onTestEnd", "params": {"result": {"status": "timedOut"}}}),
                json.dumps({"method": "onTestEnd", "params": {"result": {"status": "passed"}}}),
            ]
        )

        result = _extract_failure_count_from_jsonl(jsonl)

        assert result == 2

    def test_returns_none_for_empty(self):
        """Should return None for empty input."""
        result = _extract_failure_count_from_jsonl("")

        assert result is None

    def test_returns_none_for_no_test_events(self):
        """Should return None when no onTestEnd events found."""
        jsonl = json.dumps({"method": "onBegin", "params": {}})

        result = _extract_failure_count_from_jsonl(jsonl)

        assert result is None


# =============================================================================
# HTML REPORT PARSING TESTS
# =============================================================================


class TestExtractFailureCountFromHtml:
    """Tests for parsing Playwright HTML report with embedded base64 ZIP."""

    def _make_html_report(self, stats: dict) -> str:
        """Create a minimal Playwright HTML report with embedded stats."""
        import base64
        import io
        import zipfile

        report_json = json.dumps({"stats": stats})
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("report.json", report_json)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"<html><body><script>{b64}</script></body></html>"

    def test_extracts_failures_from_embedded_zip(self):
        """Should find stats in base64-encoded ZIP inside HTML."""
        html = self._make_html_report({"unexpected": 3, "flaky": 1, "expected": 10})

        result = _extract_failure_count_from_html(html)

        assert result == 4

    def test_returns_zero_when_no_failures(self):
        """Should return 0 when stats show no failures."""
        html = self._make_html_report({"unexpected": 0, "flaky": 0, "expected": 16})

        result = _extract_failure_count_from_html(html)

        assert result == 0

    def test_returns_none_for_non_report_html(self):
        """Should return None for HTML without embedded ZIP."""
        result = _extract_failure_count_from_html("<html><body>Hello</body></html>")

        assert result is None


# =============================================================================
# INTEGRATION: extract_failure_count_from_dir WITH NEW FORMATS
# =============================================================================


class TestExtractFromDirJsonl:
    """Tests for extract_failure_count_from_dir with JSONL blob reports."""

    def test_reads_jsonl_inside_nested_zip(self, tmp_path):
        """Should parse JSONL from nested ZIP files (blob report format)."""
        import zipfile

        jsonl = "\n".join(
            [
                json.dumps({"method": "onTestEnd", "params": {"result": {"status": "failed"}}}),
                json.dumps({"method": "onTestEnd", "params": {"result": {"status": "passed"}}}),
                json.dumps({"method": "onEnd", "params": {"result": {"status": "failed"}}}),
            ]
        )

        zip_path = tmp_path / "report.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("report.jsonl", jsonl)

        result = extract_failure_count_from_dir(tmp_path)

        assert result == 1

    def test_json_takes_precedence_over_jsonl_in_zip(self, tmp_path):
        """If a nested ZIP has both .json and .jsonl, JSON with stats wins."""
        import zipfile

        report_json = json.dumps({"stats": {"unexpected": 5, "flaky": 0}})
        jsonl = "\n".join(
            [
                json.dumps({"method": "onTestEnd", "params": {"result": {"status": "failed"}}}),
            ]
        )

        zip_path = tmp_path / "report.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("report.json", report_json)
            zf.writestr("report.jsonl", jsonl)

        result = extract_failure_count_from_dir(tmp_path)

        assert result == 5


class TestExtractFromDirHtml:
    """Tests for extract_failure_count_from_dir with HTML reports."""

    def test_reads_html_report_with_embedded_zip(self, tmp_path):
        """Should parse HTML report with embedded base64 ZIP."""
        import base64
        import io
        import zipfile

        stats = {"unexpected": 2, "flaky": 0, "expected": 10}
        report_json = json.dumps({"stats": stats})
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("report.json", report_json)
        b64 = base64.b64encode(buf.getvalue()).decode()
        html = f"<html><body><script>{b64}</script></body></html>"

        (tmp_path / "index.html").write_text(html)

        result = extract_failure_count_from_dir(tmp_path)

        assert result == 2


class TestHtmlReportDetectionInDir:
    """Tests for detecting unsupported HTML report format in extracted directories.

    Modern Playwright HTML reports have:
    - index.html (bundled JavaScript app)
    - data/ directory with trace ZIPs and snapshots
    - NO extractable JSON data

    These should raise HtmlReportNotSupported, not silently return None.
    """

    def _create_html_report_structure(self, tmp_path) -> None:
        """Create a directory structure mimicking Playwright HTML report."""
        # Modern HTML report structure
        (tmp_path / "index.html").write_text("<html><body>Playwright Report</body></html>")
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "trace-abc123.zip").write_bytes(b"fake trace data")
        (data_dir / "snapshot.md").write_text("# Page snapshot\n```yaml\n- button\n```")

    def test_raises_on_html_report_directory_structure(self, tmp_path):
        """Should raise HtmlReportNotSupported for modern HTML report."""
        from heisenberg.integrations.github_artifacts import HtmlReportNotSupported

        self._create_html_report_structure(tmp_path)

        import pytest

        with pytest.raises(HtmlReportNotSupported) as exc_info:
            extract_failure_count_from_dir(tmp_path)

        assert "HTML report" in str(exc_info.value)
        assert "JSON reporter" in str(exc_info.value)

    def test_html_report_with_json_still_works(self, tmp_path):
        """Directory with both HTML structure AND valid JSON should work."""
        self._create_html_report_structure(tmp_path)

        # Add valid JSON report
        report_data = {"stats": {"unexpected": 3, "flaky": 0}}
        (tmp_path / "report.json").write_text(json.dumps(report_data))

        # Should NOT raise - JSON takes precedence
        result = extract_failure_count_from_dir(tmp_path)

        assert result == 3

    def test_simple_html_file_without_data_dir_returns_none(self, tmp_path):
        """Single HTML file without data/ dir should return None (not error)."""
        (tmp_path / "index.html").write_text("<html>not a playwright report</html>")

        # Should return None - not a recognizable format
        result = extract_failure_count_from_dir(tmp_path)

        assert result is None
