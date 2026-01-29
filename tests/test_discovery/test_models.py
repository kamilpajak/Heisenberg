"""Tests for discover models, enums, and configuration constants."""

from __future__ import annotations

from heisenberg.playground.discover.models import (
    DEFAULT_QUERIES,
    ProgressInfo,
    ProjectSource,
    SourceStatus,
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


class TestProgressInfo:
    """Tests for ProgressInfo dataclass."""

    def test_progress_info_exists(self):
        """ProgressInfo should be importable."""
        assert ProgressInfo is not None

    def test_progress_info_has_required_fields(self):
        """ProgressInfo should have completed, total, repo, status, elapsed_ms."""
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
        info = ProgressInfo(
            completed=1,
            total=10,
            repo="microsoft/playwright",
            status="compatible",
            elapsed_ms=50,
            message="skipped verify - known good",
        )

        assert info.message == "skipped verify - known good"


class TestImprovedQueries:
    """Tests for improved search queries."""

    def test_queries_include_blob_report_pattern(self):
        """DEFAULT_QUERIES should include a query for blob-report pattern."""
        blob_queries = [q for q in DEFAULT_QUERIES if "blob-report" in q.lower()]
        assert len(blob_queries) >= 1

    def test_queries_find_custom_upload_actions(self):
        """Should have query that finds repos with custom upload actions."""
        flexible_queries = [
            q
            for q in DEFAULT_QUERIES
            if "blob-report" in q.lower() and "upload-artifact" not in q.lower()
        ]
        assert len(flexible_queries) >= 1
