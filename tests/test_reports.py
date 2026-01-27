"""Tests for the reports module - framework-agnostic report handling."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from heisenberg.reports import ReportRegistry
from heisenberg.reports.base import ReportHandler
from heisenberg.reports.models import (
    ExtractedReport,
    NormalizedReport,
    ReportType,
    TestCase,
    TestStatus,
    TestSuite,
)

# =============================================================================
# MODEL TESTS
# =============================================================================


class TestReportType:
    """Tests for ReportType enum."""

    def test_json_type_exists(self):
        assert ReportType.JSON.value == "json"

    def test_html_type_exists(self):
        assert ReportType.HTML.value == "html"


class TestTestStatus:
    """Tests for TestStatus enum."""

    def test_passed_status(self):
        assert TestStatus.PASSED.value == "passed"

    def test_failed_status(self):
        assert TestStatus.FAILED.value == "failed"

    def test_skipped_status(self):
        assert TestStatus.SKIPPED.value == "skipped"


class TestTestCase:
    """Tests for TestCase dataclass."""

    def test_create_test_case(self):
        tc = TestCase(
            name="should login successfully",
            status=TestStatus.PASSED,
            duration_ms=1500,
        )
        assert tc.name == "should login successfully"
        assert tc.status == TestStatus.PASSED
        assert tc.duration_ms == 1500

    def test_test_case_with_error(self):
        tc = TestCase(
            name="should handle error",
            status=TestStatus.FAILED,
            duration_ms=500,
            error_message="Expected true but got false",
            error_stack="at test.js:42",
        )
        assert tc.error_message == "Expected true but got false"
        assert tc.error_stack == "at test.js:42"

    def test_test_case_defaults(self):
        tc = TestCase(name="test", status=TestStatus.PASSED)
        assert tc.duration_ms is None
        assert tc.error_message is None
        assert tc.error_stack is None


class TestTestSuite:
    """Tests for TestSuite dataclass."""

    def test_create_suite(self):
        suite = TestSuite(
            name="Login Tests",
            tests=[
                TestCase(name="test1", status=TestStatus.PASSED),
                TestCase(name="test2", status=TestStatus.FAILED),
            ],
        )
        assert suite.name == "Login Tests"
        assert len(suite.tests) == 2

    def test_suite_with_nested_suites(self):
        child = TestSuite(name="Child", tests=[])
        parent = TestSuite(name="Parent", tests=[], suites=[child])
        assert len(parent.suites) == 1
        assert parent.suites[0].name == "Child"

    def test_suite_defaults(self):
        suite = TestSuite(name="Empty")
        assert suite.tests == []
        assert suite.suites == []


class TestNormalizedReport:
    """Tests for NormalizedReport dataclass."""

    def test_create_normalized_report(self):
        report = NormalizedReport(
            framework="playwright",
            total_tests=10,
            passed_tests=8,
            failed_tests=2,
            skipped_tests=0,
            suites=[],
        )
        assert report.framework == "playwright"
        assert report.total_tests == 10
        assert report.failed_tests == 2

    def test_normalized_report_to_dict(self):
        report = NormalizedReport(
            framework="jest",
            total_tests=5,
            passed_tests=5,
            failed_tests=0,
            skipped_tests=0,
            suites=[],
        )
        d = report.to_dict()
        assert d["framework"] == "jest"
        assert d["total_tests"] == 5
        assert "suites" in d

    def test_normalized_report_with_version(self):
        report = NormalizedReport(
            framework="cypress",
            framework_version="12.0.0",
            total_tests=1,
            passed_tests=1,
            failed_tests=0,
            skipped_tests=0,
            suites=[],
        )
        assert report.framework_version == "12.0.0"


class TestExtractedReport:
    """Tests for ExtractedReport dataclass."""

    def test_create_extracted_report(self, tmp_path: Path):
        report = ExtractedReport(
            report_type=ReportType.JSON,
            root_dir=tmp_path,
            data_file=tmp_path / "report.json",
            entry_point=tmp_path / "report.json",
        )
        assert report.report_type == ReportType.JSON
        assert report.root_dir == tmp_path

    def test_html_report_different_entry_point(self, tmp_path: Path):
        report = ExtractedReport(
            report_type=ReportType.HTML,
            root_dir=tmp_path / "html_report",
            data_file=tmp_path / "normalized.json",
            entry_point=tmp_path / "html_report" / "index.html",
        )
        assert report.entry_point.name == "index.html"
        assert report.data_file.name == "normalized.json"


# =============================================================================
# REGISTRY TESTS
# =============================================================================


class TestReportRegistry:
    """Tests for ReportRegistry."""

    def test_registry_exists(self):
        registry = ReportRegistry()
        assert registry is not None

    def test_register_handler(self):
        registry = ReportRegistry()

        class DummyHandler(ReportHandler):
            @property
            def name(self):
                return "dummy"

            def can_handle(self, zip_file):
                return False

            def extract(self, zip_file, output_dir):
                pass

            def normalize(self, extracted):
                pass

        registry.register(DummyHandler())
        assert len(registry.handlers) == 1

    def test_identify_returns_none_for_unknown(self):
        registry = ReportRegistry()
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("unknown.txt", "data")
        zip_buffer.seek(0)

        handler = registry.identify(zip_buffer.read())
        assert handler is None

    def test_identify_returns_matching_handler(self):
        registry = ReportRegistry()

        class MatchingHandler(ReportHandler):
            @property
            def name(self):
                return "matching"

            def can_handle(self, zip_file):
                return "match.txt" in zip_file.namelist()

            def extract(self, zip_file, output_dir):
                pass

            def normalize(self, extracted):
                pass

        registry.register(MatchingHandler())

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("match.txt", "data")
        zip_buffer.seek(0)

        handler = registry.identify(zip_buffer.read())
        assert handler is not None
        assert isinstance(handler, MatchingHandler)

    def test_get_default_registry_has_playwright(self):
        from heisenberg.reports import get_default_registry

        registry = get_default_registry()
        assert len(registry.handlers) > 0


# =============================================================================
# PLAYWRIGHT HANDLER TESTS
# =============================================================================


class TestPlaywrightHandler:
    """Tests for Playwright report handler."""

    @pytest.fixture
    def playwright_json_zip(self) -> bytes:
        """Create a minimal Playwright JSON report ZIP."""
        report = {
            "config": {"rootDir": "/app"},
            "suites": [
                {
                    "title": "Login",
                    "specs": [
                        {
                            "title": "should login",
                            "tests": [
                                {
                                    "status": "expected",
                                    "results": [{"status": "passed", "duration": 1000}],
                                }
                            ],
                        }
                    ],
                }
            ],
            "stats": {
                "expected": 1,
                "unexpected": 0,
                "skipped": 0,
            },
        }
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("report.json", json.dumps(report))
        zip_buffer.seek(0)
        return zip_buffer.read()

    @pytest.fixture
    def playwright_html_zip(self) -> bytes:
        """Create a minimal Playwright HTML report ZIP."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("index.html", "<html>Playwright Report</html>")
            zf.writestr("data/test-1.zip", b"fake data")
        zip_buffer.seek(0)
        return zip_buffer.read()

    def test_can_handle_json_report(self, playwright_json_zip: bytes):
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        with zipfile.ZipFile(io.BytesIO(playwright_json_zip)) as zf:
            assert handler.can_handle(zf) is True

    def test_can_handle_html_report(self, playwright_html_zip: bytes):
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        with zipfile.ZipFile(io.BytesIO(playwright_html_zip)) as zf:
            assert handler.can_handle(zf) is True

    def test_cannot_handle_unknown_zip(self):
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("random.txt", "not a report")
        zip_buffer.seek(0)

        with zipfile.ZipFile(zip_buffer) as zf:
            assert handler.can_handle(zf) is False

    def test_extract_json_report(self, playwright_json_zip: bytes, tmp_path: Path):
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        with zipfile.ZipFile(io.BytesIO(playwright_json_zip)) as zf:
            result = handler.extract(zf, tmp_path)

        assert result.report_type == ReportType.JSON
        assert result.data_file.exists()
        assert result.data_file.name == "report.json"

    def test_extract_html_report(self, playwright_html_zip: bytes, tmp_path: Path):
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        with zipfile.ZipFile(io.BytesIO(playwright_html_zip)) as zf:
            result = handler.extract(zf, tmp_path)

        assert result.report_type == ReportType.HTML
        assert result.entry_point.name == "index.html"
        assert result.entry_point.exists()

    def test_normalize_json_report(self, playwright_json_zip: bytes, tmp_path: Path):
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        with zipfile.ZipFile(io.BytesIO(playwright_json_zip)) as zf:
            extracted = handler.extract(zf, tmp_path)

        normalized = handler.normalize(extracted)

        assert normalized.framework == "playwright"
        assert normalized.total_tests >= 1
        assert len(normalized.suites) >= 1

    def test_handler_name(self):
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        assert handler.name == "playwright"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestReportProcessingIntegration:
    """Integration tests for full report processing flow."""

    def test_full_flow_json_report(self, tmp_path: Path):
        """Test complete flow: identify -> extract -> normalize."""
        from heisenberg.reports import get_default_registry

        # Create a Playwright JSON report
        report = {
            "config": {},
            "suites": [
                {
                    "title": "Suite",
                    "specs": [
                        {
                            "title": "test",
                            "tests": [
                                {
                                    "status": "expected",
                                    "results": [{"status": "passed", "duration": 100}],
                                }
                            ],
                        }
                    ],
                }
            ],
            "stats": {"expected": 1, "unexpected": 0, "skipped": 0},
        }
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("report.json", json.dumps(report))
        zip_content = zip_buffer.getvalue()

        registry = get_default_registry()

        # Identify
        handler = registry.identify(zip_content)
        assert handler is not None

        # Extract
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
            extracted = handler.extract(zf, tmp_path)

        # Normalize
        normalized = handler.normalize(extracted)

        assert normalized.framework == "playwright"
        assert normalized.total_tests == 1
        assert normalized.passed_tests == 1


# =============================================================================
# BLOB REPORT TESTS
# =============================================================================


class TestPlaywrightBlobHandler:
    """Tests for Playwright blob report handling."""

    @pytest.fixture
    def playwright_blob_zip(self) -> bytes:
        """Create a minimal Playwright blob report ZIP.

        Blob reports contain .zip files with test data but NO index.html.
        They are created by `--reporter=blob` and meant for merging.
        """
        # Create inner zip with report data
        inner_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(inner_zip_buffer, "w") as inner_zf:
            report_data = {
                "suites": [
                    {
                        "title": "Auth Tests",
                        "specs": [
                            {
                                "title": "should authenticate",
                                "tests": [
                                    {"status": "expected", "results": [{"status": "passed"}]}
                                ],
                            }
                        ],
                    }
                ],
                "stats": {"expected": 1, "unexpected": 0, "skipped": 0},
            }
            inner_zf.writestr("report.json", json.dumps(report_data))
        inner_zip_data = inner_zip_buffer.getvalue()

        # Create outer blob report zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("report-chromium-abc123-1.zip", inner_zip_data)
        zip_buffer.seek(0)
        return zip_buffer.read()

    def test_can_handle_blob_report(self, playwright_blob_zip: bytes):
        """Blob reports should be recognized by PlaywrightHandler."""
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        with zipfile.ZipFile(io.BytesIO(playwright_blob_zip)) as zf:
            assert handler.can_handle(zf) is True

    def test_is_blob_report_detection(self, playwright_blob_zip: bytes):
        """Blob reports have .zip files but no index.html."""
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        with zipfile.ZipFile(io.BytesIO(playwright_blob_zip)) as zf:
            namelist = zf.namelist()
            assert handler._is_blob_report(namelist) is True
            assert handler._is_html_report(namelist) is False

    def test_blob_report_not_confused_with_html(self):
        """HTML reports with data/*.zip should not be detected as blob."""
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        # Create HTML report structure (has index.html + data/*.zip)
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("index.html", "<html>Report</html>")
            zf.writestr("data/test-1.zip", b"data")
        zip_buffer.seek(0)

        handler = PlaywrightHandler()
        with zipfile.ZipFile(zip_buffer) as zf:
            namelist = zf.namelist()
            assert handler._is_blob_report(namelist) is False
            assert handler._is_html_report(namelist) is True

    def test_extract_blob_report_type(self, playwright_blob_zip: bytes, tmp_path: Path):
        """Blob reports should be extracted with ReportType.BLOB."""
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        with zipfile.ZipFile(io.BytesIO(playwright_blob_zip)) as zf:
            result = handler.extract(zf, tmp_path)

        assert result.report_type == ReportType.BLOB

    def test_extract_blob_report_produces_json(self, playwright_blob_zip: bytes, tmp_path: Path):
        """Blob extraction should produce report.json with test data."""
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        with zipfile.ZipFile(io.BytesIO(playwright_blob_zip)) as zf:
            result = handler.extract(zf, tmp_path)

        assert result.data_file.exists()
        data = json.loads(result.data_file.read_text())
        assert "suites" in data
        assert len(data["suites"]) > 0

    def test_normalize_blob_report(self, playwright_blob_zip: bytes, tmp_path: Path):
        """Blob reports should normalize to standard format."""
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        with zipfile.ZipFile(io.BytesIO(playwright_blob_zip)) as zf:
            extracted = handler.extract(zf, tmp_path)

        normalized = handler.normalize(extracted)
        assert normalized.framework == "playwright"
        assert normalized.total_tests >= 1


# =============================================================================
# VISUAL-ONLY REPORT TESTS
# =============================================================================


class TestVisualOnlyReports:
    """Tests for HTML reports that cannot be parsed (visual-only)."""

    @pytest.fixture
    def html_only_report_zip(self) -> bytes:
        """Create an HTML report with non-parseable data/*.zip files."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("index.html", "<html>Playwright Report</html>")
            # data/*.zip contains binary trace data, not JSON
            zf.writestr("data/trace-abc123.zip", b"\x00\x01\x02\x03binary data")
        zip_buffer.seek(0)
        return zip_buffer.read()

    def test_html_report_with_unparseable_data_is_visual_only(
        self, html_only_report_zip: bytes, tmp_path: Path
    ):
        """HTML reports with binary data should be marked visual_only."""
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        with zipfile.ZipFile(io.BytesIO(html_only_report_zip)) as zf:
            result = handler.extract(zf, tmp_path)

        assert result.visual_only is True
        assert result.report_type == ReportType.HTML

    def test_visual_only_report_has_empty_data_file(
        self, html_only_report_zip: bytes, tmp_path: Path
    ):
        """Visual-only reports should have minimal report.json structure."""
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        with zipfile.ZipFile(io.BytesIO(html_only_report_zip)) as zf:
            result = handler.extract(zf, tmp_path)

        data = json.loads(result.data_file.read_text())
        # Should have empty structure, not crash
        assert "suites" in data
        assert data["suites"] == []

    def test_visual_only_report_entry_point_exists(
        self, html_only_report_zip: bytes, tmp_path: Path
    ):
        """Visual-only reports should still have viewable index.html."""
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        handler = PlaywrightHandler()
        with zipfile.ZipFile(io.BytesIO(html_only_report_zip)) as zf:
            result = handler.extract(zf, tmp_path)

        assert result.entry_point.exists()
        assert result.entry_point.name == "index.html"

    def test_extracted_report_visual_only_default_false(self, tmp_path: Path):
        """ExtractedReport.visual_only should default to False."""
        from heisenberg.reports.models import ExtractedReport, ReportType

        report = ExtractedReport(
            report_type=ReportType.JSON,
            root_dir=tmp_path,
            data_file=tmp_path / "report.json",
            entry_point=tmp_path / "report.json",
        )
        assert report.visual_only is False

    def test_json_report_not_visual_only(self, tmp_path: Path):
        """JSON reports should never be visual_only."""
        from heisenberg.reports.handlers.playwright import PlaywrightHandler

        report = {
            "config": {},
            "suites": [{"title": "Test", "specs": []}],
            "stats": {"expected": 0, "unexpected": 0, "skipped": 0},
        }
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("report.json", json.dumps(report))
        zip_buffer.seek(0)

        handler = PlaywrightHandler()
        with zipfile.ZipFile(zip_buffer) as zf:
            result = handler.extract(zf, tmp_path)

        assert result.visual_only is False
        assert result.report_type == ReportType.JSON


class TestReportTypeEnum:
    """Tests for ReportType enum additions."""

    def test_blob_type_exists(self):
        """ReportType.BLOB should exist for blob reports."""
        assert ReportType.BLOB.value == "blob"
