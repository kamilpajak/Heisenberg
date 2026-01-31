"""Tests for automatic report type detection.

The CLI should automatically detect whether an artifact contains:
- Blob reports (report-*.zip with .jsonl inside) requiring merge
- Standard JSON reports (report.json) ready for direct parsing
"""

from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from heisenberg.utils.merging import ReportType, detect_report_type


def create_json_report_artifact() -> bytes:
    """Create a ZIP artifact containing a standard JSON report."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("report.json", b'{"suites": [], "stats": {}}')
    return buffer.getvalue()


def create_blob_report_artifact() -> bytes:
    """Create a ZIP artifact containing blob reports (report-*.zip)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as outer:
        # Create nested report-1.zip with .jsonl
        inner1 = io.BytesIO()
        with zipfile.ZipFile(inner1, "w") as inner:
            inner.writestr("data.jsonl", b'{"events": []}')
        outer.writestr("report-1.zip", inner1.getvalue())

        # Create nested report-2.zip with .jsonl
        inner2 = io.BytesIO()
        with zipfile.ZipFile(inner2, "w") as inner:
            inner.writestr("data.jsonl", b'{"events": []}')
        outer.writestr("report-2.zip", inner2.getvalue())
    return buffer.getvalue()


def create_empty_artifact() -> bytes:
    """Create an empty ZIP artifact."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w"):
        pass
    return buffer.getvalue()


def create_mixed_artifact() -> bytes:
    """Create artifact with both JSON report and blob reports."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as outer:
        # Standard JSON report
        outer.writestr("report.json", b'{"suites": []}')

        # Blob report zip
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as inner_zf:
            inner_zf.writestr("data.jsonl", b'{"events": []}')
        outer.writestr("report-1.zip", inner.getvalue())
    return buffer.getvalue()


class TestDetectReportType:
    """Tests for detect_report_type function."""

    def test_detects_json_report(self):
        """Should detect standard JSON report."""
        artifact = create_json_report_artifact()

        result = detect_report_type(artifact)

        assert result == ReportType.JSON

    def test_detects_blob_report(self):
        """Should detect blob reports requiring merge."""
        artifact = create_blob_report_artifact()

        result = detect_report_type(artifact)

        assert result == ReportType.BLOB

    def test_returns_unknown_for_empty_artifact(self):
        """Should return UNKNOWN for empty artifacts."""
        artifact = create_empty_artifact()

        result = detect_report_type(artifact)

        assert result == ReportType.UNKNOWN

    def test_prefers_json_in_mixed_artifact(self):
        """Should prefer JSON report when both types present."""
        artifact = create_mixed_artifact()

        result = detect_report_type(artifact)

        assert result == ReportType.JSON

    def test_handles_invalid_zip(self):
        """Should return UNKNOWN for invalid ZIP content."""
        invalid = b"not a zip file"

        result = detect_report_type(invalid)

        assert result == ReportType.UNKNOWN

    def test_detects_playwright_html_artifact(self):
        """Should detect HTML-only artifacts as unsupported."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("index.html", b"<html>Report</html>")
            zf.writestr("data/test-1.json", b"{}")
        artifact = buffer.getvalue()

        result = detect_report_type(artifact)

        assert result == ReportType.HTML

    def test_detects_json_with_different_names(self):
        """Should detect JSON reports with various naming patterns."""
        for filename in ["report.json", "playwright-report.json", "results.json"]:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as zf:
                zf.writestr(filename, b'{"suites": []}')
            artifact = buffer.getvalue()

            result = detect_report_type(artifact)

            assert result == ReportType.JSON, f"Failed for {filename}"


class TestReportTypeEnum:
    """Tests for ReportType enum."""

    def test_report_type_values(self):
        """ReportType should have expected values."""
        assert ReportType.JSON.value == "json"
        assert ReportType.BLOB.value == "blob"
        assert ReportType.HTML.value == "html"
        assert ReportType.UNKNOWN.value == "unknown"


class TestFetchReportAutoDetection:
    """Tests for fetch_report with auto-detection."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock GitHub client."""
        client = MagicMock()
        client.get_artifacts = AsyncMock()
        client.download_artifact = AsyncMock()
        client.get_jobs = AsyncMock(return_value=[])
        client.extract_playwright_report = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_fetches_json_report_directly(self, mock_client):
        """Should parse JSON report without merging."""
        from heisenberg.cli.github_fetch import fetch_report

        artifact = MagicMock()
        artifact.name = "playwright-report"
        artifact.id = 123
        mock_client.get_artifacts.return_value = [artifact]

        # JSON report artifact
        json_artifact = create_json_report_artifact()
        mock_client.download_artifact.return_value = json_artifact
        mock_client.extract_playwright_report.return_value = {"suites": []}

        result = await fetch_report(mock_client, "owner", "repo", run_id=456)

        assert result is not None
        mock_client.extract_playwright_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_merges_blob_report_automatically(self, mock_client, monkeypatch):
        """Should detect blob report and merge automatically."""
        from heisenberg.cli.github_fetch import fetch_report

        artifact = MagicMock()
        artifact.name = "blob-report"
        artifact.id = 123
        mock_client.get_artifacts.return_value = [artifact]

        # Blob report artifact
        blob_artifact = create_blob_report_artifact()
        mock_client.download_artifact.return_value = blob_artifact

        # Mock merge function
        mock_merge = AsyncMock(return_value={"suites": [], "stats": {}})
        monkeypatch.setattr("heisenberg.utils.merging.merge_blob_reports", mock_merge)

        result = await fetch_report(mock_client, "owner", "repo", run_id=456)

        assert result is not None
        mock_merge.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_for_html_only_artifact(self, mock_client):
        """Should return None for HTML-only artifacts."""
        from heisenberg.cli.github_fetch import fetch_report

        artifact = MagicMock()
        artifact.name = "playwright-report"
        artifact.id = 123
        mock_client.get_artifacts.return_value = [artifact]

        # HTML artifact
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("index.html", b"<html>Report</html>")
        mock_client.download_artifact.return_value = buffer.getvalue()

        result = await fetch_report(mock_client, "owner", "repo", run_id=456)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_artifacts(self, mock_client):
        """Should return None when no artifacts found."""
        from heisenberg.cli.github_fetch import fetch_report

        mock_client.get_artifacts.return_value = []

        result = await fetch_report(mock_client, "owner", "repo", run_id=456)

        assert result is None
