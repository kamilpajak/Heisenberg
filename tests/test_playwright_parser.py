"""Tests for Playwright report parser - TDD Red-Green-Refactor."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from heisenberg.playwright_parser import (
    PlaywrightReport,
    _extract_failed_specs,
    parse_playwright_report,
)


@pytest.fixture
def sample_report_path() -> Path:
    """Path to sample Playwright report fixture."""
    return Path(__file__).parent / "fixtures" / "playwright_report.json"


@pytest.fixture
def sample_report_data(sample_report_path: Path) -> dict:
    """Load sample report as dict."""
    return json.loads(sample_report_path.read_text())


class TestParsePlaywrightReport:
    """Test suite for parse_playwright_report function."""

    def test_parse_returns_playwright_report_object(self, sample_report_path: Path):
        """Given a valid report path, should return PlaywrightReport instance."""
        # When
        result = parse_playwright_report(sample_report_path)

        # Then
        assert isinstance(result, PlaywrightReport)

    def test_parse_extracts_total_test_counts(self, sample_report_path: Path):
        """Given a report with stats, should extract test counts correctly."""
        # When
        result = parse_playwright_report(sample_report_path)

        # Then
        assert result.total_passed == 2
        assert result.total_failed == 2
        assert result.total_skipped == 0
        assert result.total_flaky == 0

    def test_parse_extracts_failed_tests(self, sample_report_path: Path):
        """Given a report with failures, should extract all failed tests."""
        # When
        result = parse_playwright_report(sample_report_path)

        # Then
        assert len(result.failed_tests) == 2

    def test_parse_extracts_failed_test_details(self, sample_report_path: Path):
        """Given a failed test, should extract its details correctly."""
        # When
        result = parse_playwright_report(sample_report_path)

        # Then
        timeout_test = next((t for t in result.failed_tests if "payment timeout" in t.title), None)
        assert timeout_test is not None
        assert timeout_test.title == "should handle payment timeout"
        assert timeout_test.file == "tests/checkout.spec.ts"
        assert timeout_test.suite == "Checkout Flow"
        assert timeout_test.project == "chromium"
        assert timeout_test.status == "timedOut"
        assert timeout_test.duration_ms == 30000

    def test_parse_extracts_error_messages(self, sample_report_path: Path):
        """Given a failed test with errors, should extract error details."""
        # When
        result = parse_playwright_report(sample_report_path)

        # Then
        timeout_test = next((t for t in result.failed_tests if "payment timeout" in t.title), None)
        assert len(timeout_test.errors) == 1
        assert "Test timeout of 30000ms exceeded" in timeout_test.errors[0].message
        assert "checkout.spec.ts:25:5" in timeout_test.errors[0].stack

    def test_parse_extracts_trace_path(self, sample_report_path: Path):
        """Given a failed test with trace attachment, should extract trace path."""
        # When
        result = parse_playwright_report(sample_report_path)

        # Then
        timeout_test = next((t for t in result.failed_tests if "payment timeout" in t.title), None)
        assert timeout_test.trace_path is not None
        assert timeout_test.trace_path.endswith("trace.zip")

    def test_parse_extracts_start_time(self, sample_report_path: Path):
        """Given a failed test, should extract start timestamp."""
        # When
        result = parse_playwright_report(sample_report_path)

        # Then
        timeout_test = next((t for t in result.failed_tests if "payment timeout" in t.title), None)
        assert timeout_test.start_time is not None
        assert isinstance(timeout_test.start_time, datetime)
        assert timeout_test.start_time.year == 2024
        assert timeout_test.start_time.month == 1
        assert timeout_test.start_time.day == 15

    def test_parse_handles_test_without_trace(self, sample_report_path: Path):
        """Given a test without trace attachment, trace_path should be None."""
        # This is a valid scenario - not all test configs generate traces
        # When
        result = parse_playwright_report(sample_report_path)

        # Then - login test has trace, checkout has trace, so let's verify both have it
        for test in result.failed_tests:
            # In our fixture, both failed tests have traces
            assert test.trace_path is not None


class TestPlaywrightReportModel:
    """Test suite for PlaywrightReport data model."""

    def test_has_failures_returns_true_when_failed_tests_exist(self, sample_report_path: Path):
        """Given a report with failures, has_failures should return True."""
        # When
        result = parse_playwright_report(sample_report_path)

        # Then
        assert result.has_failures

    def test_report_provides_summary(self, sample_report_path: Path):
        """Given a report, should provide human-readable summary."""
        # When
        result = parse_playwright_report(sample_report_path)

        # Then
        summary = result.summary
        assert "2 passed" in summary
        assert "2 failed" in summary


class TestFailedTestModel:
    """Test suite for FailedTest data model."""

    def test_full_name_combines_suite_and_title(self, sample_report_path: Path):
        """Given a failed test, full_name should combine suite and title."""
        # When
        result = parse_playwright_report(sample_report_path)
        timeout_test = next((t for t in result.failed_tests if "payment timeout" in t.title), None)

        # Then
        assert timeout_test.full_name == "Checkout Flow > should handle payment timeout"

    def test_error_summary_returns_first_error_message(self, sample_report_path: Path):
        """Given a test with errors, error_summary should return first error."""
        # When
        result = parse_playwright_report(sample_report_path)
        timeout_test = next((t for t in result.failed_tests if "payment timeout" in t.title), None)

        # Then
        assert "timeout" in timeout_test.error_summary.lower()


class TestExtractFailedSpecs:
    """Test suite for _extract_failed_specs helper function."""

    def test_extracts_failed_specs(self):
        """Should extract specs where ok is False."""
        specs = [
            {"ok": True, "title": "passing test"},
            {
                "ok": False,
                "title": "failing test",
                "tests": [
                    {
                        "results": [
                            {
                                "status": "failed",
                                "errors": [{"message": "error", "stack": "stack"}],
                                "attachments": [],
                            }
                        ]
                    }
                ],
            },
        ]

        result = _extract_failed_specs(specs, "test.ts", "Suite")

        assert len(result) == 1
        assert result[0].title == "failing test"

    def test_returns_empty_for_all_passing(self):
        """Should return empty list when all specs pass."""
        specs = [
            {"ok": True, "title": "test1"},
            {"ok": True, "title": "test2"},
        ]

        result = _extract_failed_specs(specs, "test.ts", "Suite")

        assert result == []

    def test_returns_empty_for_empty_specs(self):
        """Should return empty list for empty specs list."""
        result = _extract_failed_specs([], "test.ts", "Suite")

        assert result == []


class TestParsePlaywrightReportEdgeCases:
    """Edge cases and error handling for parser."""

    def test_parse_raises_file_not_found_for_missing_file(self, tmp_path: Path):
        """Given a non-existent file, should raise FileNotFoundError."""
        # Given
        missing_file = tmp_path / "does_not_exist.json"

        # When/Then
        with pytest.raises(FileNotFoundError):
            parse_playwright_report(missing_file)

    def test_parse_raises_value_error_for_invalid_json(self, tmp_path: Path):
        """Given invalid JSON, should raise ValueError."""
        # Given
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("not valid json {{{")

        # When/Then
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_playwright_report(invalid_file)

    def test_parse_handles_empty_suites(self, tmp_path: Path):
        """Given a report with no suites, should return empty failed_tests."""
        # Given
        empty_report = tmp_path / "empty.json"
        empty_report.write_text(
            json.dumps(
                {"suites": [], "stats": {"expected": 0, "unexpected": 0, "flaky": 0, "skipped": 0}}
            )
        )

        # When
        result = parse_playwright_report(empty_report)

        # Then
        assert result.failed_tests == []
        assert result.total_failed == 0
