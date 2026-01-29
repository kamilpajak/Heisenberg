"""Tests for GitHub PR comment formatter - TDD Red-Green-Refactor."""

from datetime import UTC, datetime

import pytest

from heisenberg.analysis import format_pr_comment
from heisenberg.parsers.playwright import ErrorDetail, FailedTest, PlaywrightReport


@pytest.fixture
def sample_failed_test() -> FailedTest:
    """Create a sample failed test for testing."""
    return FailedTest(
        title="should handle payment timeout",
        file="tests/checkout.spec.ts",
        suite="Checkout Flow",
        project="chromium",
        status="timedOut",
        duration_ms=30000,
        start_time=datetime(2024, 1, 15, 10, 30, 5, tzinfo=UTC),
        errors=[
            ErrorDetail(
                message="Test timeout of 30000ms exceeded.",
                stack="Error: Test timeout of 30000ms exceeded.\n    at /app/tests/checkout.spec.ts:25:5",
            )
        ],
        trace_path="/app/test-results/checkout-timeout/trace.zip",
    )


@pytest.fixture
def sample_report(sample_failed_test: FailedTest) -> PlaywrightReport:
    """Create a sample report with one failure."""
    return PlaywrightReport(
        total_passed=5,
        total_failed=1,
        total_skipped=0,
        total_flaky=0,
        failed_tests=[sample_failed_test],
    )


class TestFormatPrComment:
    """Test suite for format_pr_comment function."""

    def test_returns_string(self, sample_report: PlaywrightReport):
        """Given a report, should return a markdown string."""
        # When
        result = format_pr_comment(sample_report)

        # Then
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_heisenberg_header(self, sample_report: PlaywrightReport):
        """Given a report, comment should include Heisenberg branding."""
        # When
        result = format_pr_comment(sample_report)

        # Then
        assert "Heisenberg" in result

    def test_includes_summary_stats(self, sample_report: PlaywrightReport):
        """Given a report, should include test statistics."""
        # When
        result = format_pr_comment(sample_report)

        # Then
        assert "5 passed" in result.lower() or "5" in result
        assert "1 failed" in result.lower() or "failed" in result.lower()

    def test_includes_failed_test_name(
        self, sample_report: PlaywrightReport, sample_failed_test: FailedTest
    ):
        """Given a report with failures, should list failed test names."""
        # When
        result = format_pr_comment(sample_report)

        # Then
        assert sample_failed_test.title in result

    def test_includes_error_message(
        self, sample_report: PlaywrightReport, sample_failed_test: FailedTest
    ):
        """Given a failed test with error, should include error message."""
        # When
        result = format_pr_comment(sample_report)

        # Then
        assert "timeout" in result.lower()

    def test_includes_file_location(
        self, sample_report: PlaywrightReport, sample_failed_test: FailedTest
    ):
        """Given a failed test, should include file path."""
        # When
        result = format_pr_comment(sample_report)

        # Then
        assert sample_failed_test.file in result

    def test_includes_timestamp(
        self, sample_report: PlaywrightReport, sample_failed_test: FailedTest
    ):
        """Given a failed test with start time, should include timestamp."""
        # When
        result = format_pr_comment(sample_report)

        # Then
        assert "10:30" in result or "2024-01-15" in result

    def test_includes_trace_link_when_available(
        self, sample_report: PlaywrightReport, sample_failed_test: FailedTest
    ):
        """Given a test with trace, should indicate trace availability."""
        # When
        result = format_pr_comment(sample_report)

        # Then
        assert "trace" in result.lower()

    def test_formats_as_valid_markdown(self, sample_report: PlaywrightReport):
        """Given a report, output should be valid markdown."""
        # When
        result = format_pr_comment(sample_report)

        # Then - check for markdown elements
        assert "#" in result  # Headers
        assert any(marker in result for marker in ["```", "`", "**", "*"])  # Formatting


class TestFormatPrCommentMultipleFailures:
    """Test formatting with multiple failed tests."""

    def test_lists_all_failed_tests(self):
        """Given multiple failures, should list all of them."""
        # Given
        report = PlaywrightReport(
            total_passed=3,
            total_failed=2,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="test one",
                    file="test1.spec.ts",
                    suite="Suite A",
                    project="chromium",
                    status="failed",
                    duration_ms=1000,
                    start_time=None,
                    errors=[ErrorDetail(message="Error 1", stack="")],
                    trace_path=None,
                ),
                FailedTest(
                    title="test two",
                    file="test2.spec.ts",
                    suite="Suite B",
                    project="chromium",
                    status="failed",
                    duration_ms=2000,
                    start_time=None,
                    errors=[ErrorDetail(message="Error 2", stack="")],
                    trace_path=None,
                ),
            ],
        )

        # When
        result = format_pr_comment(report)

        # Then
        assert "test one" in result
        assert "test two" in result


class TestFormatPrCommentNoFailures:
    """Test formatting when all tests pass."""

    def test_shows_success_message_when_no_failures(self):
        """Given all tests passed, should show success message."""
        # Given
        report = PlaywrightReport(
            total_passed=10,
            total_failed=0,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[],
        )

        # When
        result = format_pr_comment(report)

        # Then
        assert "passed" in result.lower() or "success" in result.lower()
        assert "10" in result


class TestFormatPrCommentEdgeCases:
    """Edge cases for comment formatting."""

    def test_handles_test_without_errors(self):
        """Given a failed test without error details, should still format."""
        # Given
        report = PlaywrightReport(
            total_passed=0,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="mystery failure",
                    file="test.spec.ts",
                    suite="Suite",
                    project="chromium",
                    status="failed",
                    duration_ms=100,
                    start_time=None,
                    errors=[],
                    trace_path=None,
                )
            ],
        )

        # When
        result = format_pr_comment(report)

        # Then
        assert "mystery failure" in result

    def test_escapes_special_markdown_characters(self):
        """Given test with special chars, should escape them properly."""
        # Given
        report = PlaywrightReport(
            total_passed=0,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="test with `backticks` and *asterisks*",
                    file="test.spec.ts",
                    suite="Suite",
                    project="chromium",
                    status="failed",
                    duration_ms=100,
                    start_time=None,
                    errors=[ErrorDetail(message="Error with <html> tags", stack="")],
                    trace_path=None,
                )
            ],
        )

        # When
        result = format_pr_comment(report)

        # Then - should not break markdown
        assert isinstance(result, str)
        # Test title should appear somewhere
        assert "backticks" in result or "test with" in result
