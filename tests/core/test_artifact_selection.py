"""Tests for artifact selection logic."""

from __future__ import annotations

from heisenberg.core.artifact_selection import (
    _normalize,
    is_playwright_artifact,
    select_best_artifact,
)


class TestNormalize:
    """Tests for _normalize helper function."""

    def test_removes_hyphens(self):
        """Should remove hyphens from string."""
        assert _normalize("e2e-web") == "e2eweb"

    def test_removes_underscores(self):
        """Should remove underscores from string."""
        assert _normalize("e2e_web") == "e2eweb"

    def test_removes_both_hyphens_and_underscores(self):
        """Should remove both hyphens and underscores."""
        assert _normalize("e2e-web_test") == "e2ewebtest"

    def test_returns_same_for_clean_string(self):
        """Should return same string if no separators."""
        assert _normalize("playwright") == "playwright"

    def test_empty_string(self):
        """Should handle empty string."""
        assert _normalize("") == ""


class TestIsPlaywrightArtifact:
    """Tests for is_playwright_artifact function."""

    def test_recognizes_playwright_report(self):
        """Should recognize playwright-report as Playwright artifact."""
        assert is_playwright_artifact("playwright-report")

    def test_recognizes_blob_report(self):
        """Should recognize blob-report as Playwright artifact."""
        assert is_playwright_artifact("blob-report")

    def test_recognizes_trace_zip(self):
        """Should recognize trace.zip as Playwright artifact."""
        assert is_playwright_artifact("trace.zip")

    def test_rejects_generic_report(self):
        """Should reject generic report names."""
        assert not is_playwright_artifact("test-report")

    def test_case_insensitive(self):
        """Should be case insensitive."""
        assert is_playwright_artifact("Playwright-Report")


class TestSelectBestArtifact:
    """Tests for select_best_artifact function."""

    def test_prefers_job_name_match(self):
        """Should prefer artifact matching failed job name."""
        artifacts = [
            {"name": "playwright-report"},
            {"name": "e2e-web-reports"},
        ]
        failed_jobs = ["e2e-web (ubuntu-latest)"]
        result = select_best_artifact(artifacts, failed_jobs)
        assert result["name"] == "e2e-web-reports"

    def test_returns_none_for_low_score(self):
        """Should return None if no artifact scores above threshold."""
        artifacts = [{"name": "coverage-reports"}]
        failed_jobs = ["lint"]
        result = select_best_artifact(artifacts, failed_jobs)
        assert result is None
