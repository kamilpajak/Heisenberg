"""Tests for artifact analysis, verification, and status determination."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from heisenberg.playground.discover.analysis import (
    determine_status,
    download_and_check_failures,
    filter_by_min_stars,
    filter_expired_artifacts,
    find_valid_artifacts,
    is_playwright_artifact,
    sort_sources,
    verify_has_failures,
)
from heisenberg.playground.discover.models import (
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


class TestFilterByMinStars:
    """Tests for filter_by_min_stars function."""

    def test_filters_below_threshold(self):
        """Should filter out repos below min_stars threshold."""
        sources = [
            ProjectSource(repo="low/stars", stars=50, status=SourceStatus.COMPATIBLE),
            ProjectSource(repo="high/stars", stars=500, status=SourceStatus.COMPATIBLE),
        ]
        filtered = filter_by_min_stars(sources, min_stars=100)
        assert len(filtered) == 1
        assert filtered[0].repo == "high/stars"

    def test_keeps_at_threshold(self):
        """Should keep repos at exactly min_stars threshold."""
        sources = [
            ProjectSource(repo="exact/threshold", stars=100, status=SourceStatus.COMPATIBLE),
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

    @patch("heisenberg.playground.discover.analysis.get_run_artifacts")
    @patch("heisenberg.playground.discover.analysis.get_failed_runs")
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

    @patch("heisenberg.playground.discover.analysis.get_run_artifacts")
    @patch("heisenberg.playground.discover.analysis.get_failed_runs")
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

    @patch("heisenberg.playground.discover.analysis.find_valid_artifacts")
    @patch("heisenberg.playground.discover.analysis.get_repo_stars")
    def test_uses_provided_stars(self, mock_get_stars, mock_find_artifacts):
        """Should use stars provided as argument, not make API call."""
        from heisenberg.playground.discover.analysis import analyze_source

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

    @patch("heisenberg.playground.discover.analysis.find_valid_artifacts")
    @patch("heisenberg.playground.discover.analysis.get_repo_stars")
    def test_fetches_stars_when_not_provided(self, mock_get_stars, mock_find_artifacts):
        """Should fetch stars via API when not provided."""
        from heisenberg.playground.discover.analysis import analyze_source

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

    @patch("heisenberg.playground.discover.analysis.find_valid_artifacts")
    @patch("heisenberg.playground.discover.analysis.get_repo_stars")
    def test_sets_correct_status(self, mock_get_stars, mock_find_artifacts):
        """Should set correct status based on artifacts."""
        from heisenberg.playground.discover.analysis import analyze_source

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

    @patch("heisenberg.playground.discover.analysis.download_and_check_failures")
    def test_returns_true_when_failures_found(self, mock_download):
        """Should return True when artifact contains test failures."""
        mock_download.return_value = 5

        result = verify_has_failures("owner/repo", "123", "playwright-report")

        assert result is True

    @patch("heisenberg.playground.discover.analysis.download_and_check_failures")
    def test_returns_false_when_zero_failures(self, mock_download):
        """Should return False when artifact has zero failures."""
        mock_download.return_value = 0

        result = verify_has_failures("owner/repo", "123", "playwright-report")

        assert result is False

    @patch("heisenberg.playground.discover.analysis.download_and_check_failures")
    def test_returns_false_on_download_error(self, mock_download):
        """Should return False if artifact can't be downloaded/parsed."""
        mock_download.return_value = None

        result = verify_has_failures("owner/repo", "123", "playwright-report")

        assert result is False


class TestDownloadAndCheckFailures:
    """Tests for download_and_check_failures function (legacy tests updated)."""

    @patch("heisenberg.playground.discover.analysis.extract_failure_count_from_dir")
    @patch("heisenberg.playground.discover.analysis.download_artifact_to_dir")
    def test_extracts_failure_count_from_blob_report(self, mock_download, mock_extract):
        """Should extract failure count from blob report stats."""
        mock_download.return_value = True
        mock_extract.return_value = 3

        result = download_and_check_failures("owner/repo", "123", "blob-report")

        assert result == 3

    @patch("heisenberg.playground.discover.analysis.extract_failure_count_from_dir")
    @patch("heisenberg.playground.discover.analysis.download_artifact_to_dir")
    def test_extracts_failure_count_from_json_report(self, mock_download, mock_extract):
        """Should extract failure count from JSON report stats."""
        mock_download.return_value = True
        mock_extract.return_value = 2

        result = download_and_check_failures("owner/repo", "123", "playwright-report")

        assert result == 2

    @patch("heisenberg.playground.discover.analysis.download_artifact_to_dir")
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
        status = determine_status(
            run_id="123",
            artifact_names=["playwright-report"],
            playwright_artifacts=["playwright-report"],
            failure_count=None,
        )
        assert status == SourceStatus.COMPATIBLE


class TestAnalyzeSourceWithVerification:
    """Tests for analyze_source with failure verification."""

    @patch("heisenberg.playground.discover.analysis.verify_has_failures")
    @patch("heisenberg.playground.discover.analysis.find_valid_artifacts")
    @patch("heisenberg.playground.discover.analysis.get_repo_stars")
    def test_verifies_failures_when_enabled(self, mock_stars, mock_artifacts, mock_verify):
        """Should verify failures when verify_failures=True."""
        from heisenberg.playground.discover.analysis import analyze_source

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

    @patch("heisenberg.playground.discover.analysis.verify_has_failures")
    @patch("heisenberg.playground.discover.analysis.find_valid_artifacts")
    @patch("heisenberg.playground.discover.analysis.get_repo_stars")
    def test_sets_no_failures_when_verification_fails(
        self, mock_stars, mock_artifacts, mock_verify
    ):
        """Should set NO_FAILURES when verification finds no failures."""
        from heisenberg.playground.discover.analysis import analyze_source

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

    @patch("heisenberg.playground.discover.analysis.verify_has_failures")
    @patch("heisenberg.playground.discover.analysis.find_valid_artifacts")
    @patch("heisenberg.playground.discover.analysis.get_repo_stars")
    def test_skips_verification_when_disabled(self, mock_stars, mock_artifacts, mock_verify):
        """Should skip verification when verify_failures=False (default)."""
        from heisenberg.playground.discover.analysis import analyze_source

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

    @patch("heisenberg.playground.discover.analysis.get_run_artifacts")
    @patch("heisenberg.playground.discover.analysis.get_failed_runs")
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
        from heisenberg.playground.discover.client import download_artifact_to_dir

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

        from heisenberg.playground.discover.client import download_artifact_to_dir

        mock_run.side_effect = CalledProcessError(1, "gh")

        result = download_artifact_to_dir("owner/repo", "artifact-name", "/tmp/target")

        assert result is False


class TestExtractFailureCountFromDir:
    """Tests for extracting failure count directly from extracted files."""

    def test_extract_failure_count_from_dir_finds_json_stats(self, tmp_path):
        """Should find and parse JSON files with stats in extracted directory."""
        from heisenberg.playground.discover.analysis import extract_failure_count_from_dir

        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps({"stats": {"failed": 7, "passed": 100}}))

        result = extract_failure_count_from_dir(tmp_path)

        assert result == 7

    def test_extract_failure_count_from_dir_handles_nested_zips(self, tmp_path):
        """Should handle blob reports with nested zip files."""
        import io
        import zipfile

        from heisenberg.playground.discover.analysis import extract_failure_count_from_dir

        inner_zip = io.BytesIO()
        with zipfile.ZipFile(inner_zip, "w") as zf:
            zf.writestr("data.json", json.dumps({"stats": {"failed": 3, "passed": 50}}))

        (tmp_path / "report-shard1.zip").write_bytes(inner_zip.getvalue())

        result = extract_failure_count_from_dir(tmp_path)

        assert result == 3

    def test_extract_failure_count_from_dir_returns_none_if_no_stats(self, tmp_path):
        """Should return None if no stats found in any file."""
        from heisenberg.playground.discover.analysis import extract_failure_count_from_dir

        (tmp_path / "readme.txt").write_text("No stats here")

        result = extract_failure_count_from_dir(tmp_path)

        assert result is None


class TestOptimizedDownloadAndCheck:
    """Tests for optimized download_and_check_failures (no re-zipping)."""

    @patch("heisenberg.playground.discover.analysis.extract_failure_count_from_dir")
    @patch("heisenberg.playground.discover.analysis.download_artifact_to_dir")
    def test_uses_direct_file_reading(self, mock_download, mock_extract):
        """Should use direct file reading, not re-zipping."""
        mock_download.return_value = True
        mock_extract.return_value = 5

        result = download_and_check_failures("owner/repo", "123", "blob-report")

        assert result == 5
        mock_download.assert_called_once()
        mock_extract.assert_called_once()

    @patch("heisenberg.playground.discover.analysis.download_artifact_to_dir")
    def test_returns_none_on_download_failure(self, mock_download):
        """Should return None if download fails."""
        mock_download.return_value = False

        result = download_and_check_failures("owner/repo", "123", "blob-report")

        assert result is None


class TestFindValidArtifactsReturnsRunCreatedAt:
    """Tests for find_valid_artifacts returning run_created_at for cache."""

    @patch("heisenberg.playground.discover.analysis.get_run_artifacts")
    @patch("heisenberg.playground.discover.analysis.get_failed_runs")
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


class TestSkipVerificationForKnownGoodRepos:
    """Tests for skipping verification on KNOWN_GOOD_REPOS."""

    @patch("heisenberg.playground.discover.analysis.verify_has_failures")
    @patch("heisenberg.playground.discover.analysis.find_valid_artifacts")
    @patch("heisenberg.playground.discover.analysis.get_repo_stars")
    def test_skips_verification_for_known_good_repos(self, mock_stars, mock_artifacts, mock_verify):
        """Should NOT call verify_has_failures for repos in KNOWN_GOOD_REPOS."""
        from heisenberg.playground.discover.analysis import analyze_source
        from heisenberg.playground.discover.models import KNOWN_GOOD_REPOS

        mock_stars.return_value = 80000
        mock_artifacts.return_value = (
            "123",
            "url",
            ["blob-report-1"],
            "2024-01-15T10:00:00Z",
            {"blob-report-1": 200_000_000},
        )

        source = analyze_source(
            KNOWN_GOOD_REPOS[0],
            verify_failures=True,
        )

        mock_verify.assert_not_called()
        assert source.status == SourceStatus.COMPATIBLE

    @patch("heisenberg.playground.discover.analysis.verify_has_failures")
    @patch("heisenberg.playground.discover.analysis.find_valid_artifacts")
    @patch("heisenberg.playground.discover.analysis.get_repo_stars")
    def test_still_verifies_unknown_repos(self, mock_stars, mock_artifacts, mock_verify):
        """Should still verify repos NOT in KNOWN_GOOD_REPOS."""
        from heisenberg.playground.discover.analysis import analyze_source

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

        mock_verify.assert_called_once()
        assert source.status == SourceStatus.COMPATIBLE


class TestAnalyzeWithStatusUpdates:
    """Tests for analyze_source_with_status showing current operation."""

    def test_analyze_source_with_status_exists(self):
        """analyze_source_with_status function should exist."""
        from heisenberg.playground.discover.analysis import analyze_source_with_status

        assert callable(analyze_source_with_status)

    @patch("heisenberg.playground.discover.analysis.get_repo_stars")
    @patch("heisenberg.playground.discover.analysis.find_valid_artifacts")
    def test_calls_status_callback_with_stages(self, mock_artifacts, mock_stars):
        """Should call status_callback with different stages."""
        from heisenberg.playground.discover.analysis import analyze_source_with_status

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

    @patch("heisenberg.playground.discover.analysis.verify_has_failures")
    @patch("heisenberg.playground.discover.analysis.get_repo_stars")
    @patch("heisenberg.playground.discover.analysis.find_valid_artifacts")
    def test_shows_downloading_stage_when_verifying(self, mock_artifacts, mock_stars, mock_verify):
        """Should show 'Downloading...' stage when verify_failures=True."""
        from heisenberg.playground.discover.analysis import analyze_source_with_status

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
