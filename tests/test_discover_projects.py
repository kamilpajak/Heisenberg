"""Tests for discover_projects.py script."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts to path for import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from discover_projects import (
    ProjectCandidate,
    analyze_candidate,
    check_artifacts,
    is_playwright_artifact,
    search_repos,
)


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


class TestCheckArtifacts:
    """Tests for check_artifacts function."""

    @patch("discover_projects.gh_api")
    @patch("subprocess.run")
    def test_checks_multiple_failed_runs(self, mock_run, mock_gh_api):
        """Should check multiple failed runs, not just the latest."""
        # Mock runs API to return 3 failed runs
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "workflow_runs": [
                        {"id": 100, "html_url": "url1"},
                        {"id": 200, "html_url": "url2"},
                        {"id": 300, "html_url": "url3"},
                    ]
                }
            ),
            returncode=0,
        )

        # First run has no artifacts, second has playwright-report
        def artifacts_side_effect(endpoint):
            if "100" in endpoint:
                return {"artifacts": []}
            elif "200" in endpoint:
                return {"artifacts": [{"name": "playwright-report", "expired": False}]}
            return {"artifacts": []}

        mock_gh_api.side_effect = artifacts_side_effect

        run_id, run_url, artifacts = check_artifacts("owner/repo")

        # Should find artifacts from second run (first valid one)
        assert run_id == "200"
        assert "playwright-report" in artifacts

    @patch("discover_projects.gh_api")
    @patch("subprocess.run")
    def test_skips_expired_artifacts(self, mock_run, mock_gh_api):
        """Should skip expired artifacts."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"workflow_runs": [{"id": 100, "html_url": "url1"}]}),
            returncode=0,
        )

        mock_gh_api.return_value = {
            "artifacts": [
                {"name": "playwright-report", "expired": True},
                {"name": "trace.zip", "expired": False},
            ]
        }

        run_id, run_url, artifacts = check_artifacts("owner/repo")

        # Should only include non-expired artifacts
        assert "playwright-report" not in artifacts
        assert "trace.zip" in artifacts

    @patch("discover_projects.gh_api")
    @patch("subprocess.run")
    def test_requests_multiple_runs(self, mock_run, mock_gh_api):
        """Should request per_page>=5 to get multiple runs."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"workflow_runs": []}),
            returncode=0,
        )
        mock_gh_api.return_value = {"artifacts": []}

        check_artifacts("owner/repo")

        # Verify we request multiple runs (at least 5)
        call_args = " ".join(mock_run.call_args[0][0])
        assert "per_page=5" in call_args or "per_page=10" in call_args


class TestSearchRepos:
    """Tests for search_repos function."""

    @patch("subprocess.run")
    def test_returns_repo_names(self, mock_run):
        """Should return list of repo names."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "items": [
                        {
                            "repository": {
                                "full_name": "owner/repo",
                            }
                        }
                    ]
                }
            ),
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

        assert len(results) == 1  # No duplicates


class TestAnalyzeCandidate:
    """Tests for analyze_candidate function."""

    @patch("discover_projects.check_artifacts")
    @patch("discover_projects.get_repo_stars")
    def test_uses_provided_stars_skips_api(self, mock_get_stars, mock_check):
        """Should use stars provided as argument, not make API call."""
        mock_check.return_value = ("123", "url", ["playwright-report"])
        mock_get_stars.return_value = 999  # Should not be used

        candidate = analyze_candidate("owner/repo", stars=5000)

        assert candidate.stars == 5000
        mock_get_stars.assert_not_called()

    @patch("discover_projects.check_artifacts")
    @patch("discover_projects.get_repo_stars")
    def test_fetches_stars_when_not_provided(self, mock_get_stars, mock_check):
        """Should fetch stars via API when not provided."""
        mock_check.return_value = ("123", "url", ["playwright-report"])
        mock_get_stars.return_value = 1234

        candidate = analyze_candidate("owner/repo")

        assert candidate.stars == 1234
        mock_get_stars.assert_called_once_with("owner/repo")


class TestMinStarsFiltering:
    """Tests for --min-stars filtering."""

    def test_filter_by_min_stars_exists(self):
        """filter_by_min_stars function should exist."""
        try:
            from discover_projects import filter_by_min_stars
        except ImportError:
            pytest.fail("filter_by_min_stars function should be implemented")

    def test_filters_below_threshold(self):
        """Should filter out repos below min_stars threshold."""
        from discover_projects import filter_by_min_stars

        candidates = [
            ProjectCandidate(
                repo="low/stars",
                stars=50,
                has_artifacts=True,
                artifact_names=[],
                run_id="1",
                run_url="",
                compatible=True,
                notes="",
            ),
            ProjectCandidate(
                repo="high/stars",
                stars=500,
                has_artifacts=True,
                artifact_names=[],
                run_id="2",
                run_url="",
                compatible=True,
                notes="",
            ),
        ]
        filtered = filter_by_min_stars(candidates, min_stars=100)
        assert len(filtered) == 1
        assert filtered[0].repo == "high/stars"

    def test_keeps_at_threshold(self):
        """Should keep repos at exactly min_stars threshold."""
        from discover_projects import filter_by_min_stars

        candidates = [
            ProjectCandidate(
                repo="exact/threshold",
                stars=100,
                has_artifacts=True,
                artifact_names=[],
                run_id="1",
                run_url="",
                compatible=True,
                notes="",
            ),
        ]
        filtered = filter_by_min_stars(candidates, min_stars=100)
        assert len(filtered) == 1


class TestRateLimitHandling:
    """Tests for rate limit handling."""

    @patch("subprocess.run")
    def test_handles_rate_limit_error_gracefully(self, mock_run):
        """Should handle 403/429 rate limit errors gracefully."""
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, "gh", stderr="API rate limit exceeded")

        from discover_projects import gh_api

        result = gh_api("/repos/owner/repo")

        # Should return None, not crash
        assert result is None


class TestGlobalLimit:
    """Tests for global limit across queries."""

    def test_discover_candidates_respects_global_limit(self):
        """discover_candidates should respect global limit across all queries."""
        try:
            from discover_projects import discover_candidates
        except ImportError:
            pytest.fail("discover_candidates function should be implemented")

        # Test will be implemented when function exists
