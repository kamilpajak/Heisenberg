"""Tests for discover_projects.py script."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from heisenberg.playground.discover import (
    DEFAULT_QUERIES,
    CandidateStatus,
    ProjectCandidate,
    analyze_candidate,
    determine_status,
    filter_by_min_stars,
    filter_expired_artifacts,
    find_valid_artifacts,
    format_status_detail,
    format_status_icon,
    get_failed_runs,
    get_run_artifacts,
    is_playwright_artifact,
    search_repos,
    sort_candidates,
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


class TestCandidateStatus:
    """Tests for CandidateStatus enum."""

    def test_has_all_statuses(self):
        """Should have all expected status values."""
        assert CandidateStatus.COMPATIBLE.value == "compatible"
        assert CandidateStatus.HAS_ARTIFACTS.value == "has_artifacts"
        assert CandidateStatus.NO_ARTIFACTS.value == "no_artifacts"
        assert CandidateStatus.NO_FAILED_RUNS.value == "no_failed_runs"


class TestProjectCandidate:
    """Tests for ProjectCandidate dataclass."""

    def test_compatible_property_true_when_compatible(self):
        """compatible property should return True for COMPATIBLE status."""
        candidate = ProjectCandidate(
            repo="owner/repo",
            stars=100,
            status=CandidateStatus.COMPATIBLE,
        )
        assert candidate.compatible is True

    def test_compatible_property_false_for_other_statuses(self):
        """compatible property should return False for non-COMPATIBLE status."""
        for status in [
            CandidateStatus.HAS_ARTIFACTS,
            CandidateStatus.NO_ARTIFACTS,
            CandidateStatus.NO_FAILED_RUNS,
        ]:
            candidate = ProjectCandidate(repo="owner/repo", stars=100, status=status)
            assert candidate.compatible is False

    def test_has_artifacts_property(self):
        """has_artifacts property should check artifact_names list."""
        with_artifacts = ProjectCandidate(
            repo="owner/repo",
            stars=100,
            status=CandidateStatus.HAS_ARTIFACTS,
            artifact_names=["report"],
        )
        without_artifacts = ProjectCandidate(
            repo="owner/repo",
            stars=100,
            status=CandidateStatus.NO_ARTIFACTS,
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
        assert status == CandidateStatus.NO_FAILED_RUNS

    def test_no_artifacts(self):
        """Should return NO_ARTIFACTS when artifact list is empty."""
        status = determine_status("123", [], [])
        assert status == CandidateStatus.NO_ARTIFACTS

    def test_has_artifacts_but_no_playwright(self):
        """Should return HAS_ARTIFACTS when artifacts exist but none are Playwright."""
        status = determine_status("123", ["coverage-report"], [])
        assert status == CandidateStatus.HAS_ARTIFACTS

    def test_compatible(self):
        """Should return COMPATIBLE when Playwright artifacts exist."""
        status = determine_status("123", ["playwright-report"], ["playwright-report"])
        assert status == CandidateStatus.COMPATIBLE


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
        candidates = [
            ProjectCandidate(
                repo="low/stars",
                stars=50,
                status=CandidateStatus.COMPATIBLE,
            ),
            ProjectCandidate(
                repo="high/stars",
                stars=500,
                status=CandidateStatus.COMPATIBLE,
            ),
        ]
        filtered = filter_by_min_stars(candidates, min_stars=100)
        assert len(filtered) == 1
        assert filtered[0].repo == "high/stars"

    def test_keeps_at_threshold(self):
        """Should keep repos at exactly min_stars threshold."""
        candidates = [
            ProjectCandidate(
                repo="exact/threshold",
                stars=100,
                status=CandidateStatus.COMPATIBLE,
            ),
        ]
        filtered = filter_by_min_stars(candidates, min_stars=100)
        assert len(filtered) == 1


class TestSortCandidates:
    """Tests for sort_candidates function."""

    def test_sorts_compatible_first(self):
        """Compatible candidates should come before non-compatible."""
        candidates = [
            ProjectCandidate(repo="a", stars=1000, status=CandidateStatus.HAS_ARTIFACTS),
            ProjectCandidate(repo="b", stars=100, status=CandidateStatus.COMPATIBLE),
        ]
        sorted_list = sort_candidates(candidates)
        assert sorted_list[0].repo == "b"  # Compatible first

    def test_sorts_by_stars_within_same_status(self):
        """Higher stars should come first within same compatibility."""
        candidates = [
            ProjectCandidate(repo="a", stars=100, status=CandidateStatus.COMPATIBLE),
            ProjectCandidate(repo="b", stars=500, status=CandidateStatus.COMPATIBLE),
        ]
        sorted_list = sort_candidates(candidates)
        assert sorted_list[0].repo == "b"  # Higher stars first


# =============================================================================
# GITHUB CLIENT TESTS
# =============================================================================


class TestGetFailedRuns:
    """Tests for get_failed_runs function."""

    @patch("subprocess.run")
    def test_returns_workflow_runs(self, mock_run):
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

    @patch("subprocess.run")
    def test_requests_multiple_runs(self, mock_run):
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
            {"id": 100, "html_url": "url1"},
            {"id": 200, "html_url": "url2"},
        ]

        # First run has no artifacts, second has valid ones
        def artifacts_side_effect(repo, run_id):
            if run_id == "100":
                return []
            return [{"name": "playwright-report", "expired": False}]

        mock_get_artifacts.side_effect = artifacts_side_effect

        run_id, run_url, artifacts = find_valid_artifacts("owner/repo")

        assert run_id == "200"
        assert "playwright-report" in artifacts

    @patch("heisenberg.playground.discover.get_run_artifacts")
    @patch("heisenberg.playground.discover.get_failed_runs")
    def test_skips_expired_artifacts(self, mock_get_runs, mock_get_artifacts):
        """Should skip expired artifacts."""
        mock_get_runs.return_value = [{"id": 100, "html_url": "url1"}]
        mock_get_artifacts.return_value = [
            {"name": "playwright-report", "expired": True},
            {"name": "trace.zip", "expired": False},
        ]

        run_id, run_url, artifacts = find_valid_artifacts("owner/repo")

        assert "playwright-report" not in artifacts
        assert "trace.zip" in artifacts


class TestSearchRepos:
    """Tests for search_repos function."""

    @patch("subprocess.run")
    def test_returns_repo_names(self, mock_run):
        """Should return list of repo names."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"items": [{"repository": {"full_name": "owner/repo"}}]}),
            returncode=0,
        )

        results = search_repos("playwright", limit=10)

        assert len(results) == 1
        assert results[0] == "owner/repo"

    @patch("subprocess.run")
    def test_deduplicates_across_results(self, mock_run):
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
    """Tests for analyze_candidate function."""

    @patch("heisenberg.playground.discover.find_valid_artifacts")
    @patch("heisenberg.playground.discover.get_repo_stars")
    def test_uses_provided_stars(self, mock_get_stars, mock_find_artifacts):
        """Should use stars provided as argument, not make API call."""
        mock_find_artifacts.return_value = ("123", "url", ["playwright-report"])
        mock_get_stars.return_value = 999

        candidate = analyze_candidate("owner/repo", stars=5000)

        assert candidate.stars == 5000
        mock_get_stars.assert_not_called()

    @patch("heisenberg.playground.discover.find_valid_artifacts")
    @patch("heisenberg.playground.discover.get_repo_stars")
    def test_fetches_stars_when_not_provided(self, mock_get_stars, mock_find_artifacts):
        """Should fetch stars via API when not provided."""
        mock_find_artifacts.return_value = ("123", "url", ["playwright-report"])
        mock_get_stars.return_value = 1234

        candidate = analyze_candidate("owner/repo")

        assert candidate.stars == 1234
        mock_get_stars.assert_called_once_with("owner/repo")

    @patch("heisenberg.playground.discover.find_valid_artifacts")
    @patch("heisenberg.playground.discover.get_repo_stars")
    def test_sets_correct_status(self, mock_get_stars, mock_find_artifacts):
        """Should set correct status based on artifacts."""
        mock_find_artifacts.return_value = ("123", "url", ["playwright-report"])
        mock_get_stars.return_value = 100

        candidate = analyze_candidate("owner/repo")

        assert candidate.status == CandidateStatus.COMPATIBLE
        assert candidate.playwright_artifacts == ["playwright-report"]


# =============================================================================
# PRESENTER TESTS
# =============================================================================


class TestFormatStatusIcon:
    """Tests for format_status_icon function."""

    def test_compatible_icon(self):
        """COMPATIBLE status should show checkmark."""
        assert "✅" in format_status_icon(CandidateStatus.COMPATIBLE)

    def test_has_artifacts_icon(self):
        """HAS_ARTIFACTS status should show warning."""
        assert "⚠" in format_status_icon(CandidateStatus.HAS_ARTIFACTS)

    def test_no_artifacts_icon(self):
        """NO_ARTIFACTS status should show X."""
        assert "❌" in format_status_icon(CandidateStatus.NO_ARTIFACTS)

    def test_no_failed_runs_icon(self):
        """NO_FAILED_RUNS status should show skip icon."""
        assert "⏭" in format_status_icon(CandidateStatus.NO_FAILED_RUNS)


class TestFormatStatusDetail:
    """Tests for format_status_detail function."""

    def test_compatible_shows_artifacts(self):
        """COMPATIBLE status should show playwright artifacts."""
        candidate = ProjectCandidate(
            repo="owner/repo",
            stars=100,
            status=CandidateStatus.COMPATIBLE,
            playwright_artifacts=["playwright-report"],
        )
        detail = format_status_detail(candidate)
        assert "playwright-report" in detail
        assert "100" in detail  # Stars

    def test_has_artifacts_shows_artifact_names(self):
        """HAS_ARTIFACTS status should show artifact names."""
        candidate = ProjectCandidate(
            repo="owner/repo",
            stars=100,
            status=CandidateStatus.HAS_ARTIFACTS,
            artifact_names=["coverage-report"],
        )
        detail = format_status_detail(candidate)
        assert "coverage-report" in detail

    def test_no_artifacts_message(self):
        """NO_ARTIFACTS status should show appropriate message."""
        candidate = ProjectCandidate(
            repo="owner/repo",
            stars=100,
            status=CandidateStatus.NO_ARTIFACTS,
        )
        detail = format_status_detail(candidate)
        assert "No artifacts" in detail


# =============================================================================
# RATE LIMIT HANDLING
# =============================================================================


class TestRateLimitHandling:
    """Tests for rate limit handling."""

    @patch("subprocess.run")
    def test_handles_rate_limit_error_gracefully(self, mock_run):
        """Should handle 403/429 rate limit errors gracefully."""
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, "gh", stderr="API rate limit exceeded")

        from heisenberg.playground.discover import gh_api

        result = gh_api("/repos/owner/repo")

        assert result is None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestDiscoverCandidates:
    """Tests for discover_candidates function."""

    @patch("heisenberg.playground.discover.analyze_candidate")
    @patch("heisenberg.playground.discover.search_repos")
    def test_uses_default_queries(self, mock_search, mock_analyze):
        """Should use DEFAULT_QUERIES when queries not provided."""
        mock_search.return_value = []
        mock_analyze.return_value = ProjectCandidate(
            repo="owner/repo",
            stars=100,
            status=CandidateStatus.COMPATIBLE,
        )

        from heisenberg.playground.discover import discover_candidates

        discover_candidates(global_limit=10, min_stars=0)

        # Should have called search for each default query
        assert mock_search.call_count == len(DEFAULT_QUERIES)
