"""Tests for unified formatters."""

import json

import pytest

from heisenberg.formatters import (
    format_unified_as_json,
    format_unified_as_markdown,
)
from heisenberg.unified_model import (
    ErrorInfo,
    FailureMetadata,
    Framework,
    UnifiedFailure,
    UnifiedTestRun,
)


@pytest.fixture
def sample_unified_run():
    """Create a sample unified test run."""
    failure = UnifiedFailure(
        test_id="test-1",
        file_path="tests/example.spec.ts",
        test_title="should validate user input",
        suite_path=["Forms", "Validation"],
        error=ErrorInfo(
            message="Expected element to be visible",
            stack_trace="at tests/example.spec.ts:25\n  at run()",
            location={"file": "tests/example.spec.ts", "line": 25, "column": 10},
        ),
        metadata=FailureMetadata(
            framework=Framework.PLAYWRIGHT,
            browser="chromium",
            retry_count=2,
            duration_ms=3500,
            tags=["regression"],
        ),
    )

    return UnifiedTestRun(
        run_id="run-456",
        repository="user/project",
        branch="feature/forms",
        commit_sha="def456",
        workflow_name="CI Tests",
        run_url="https://github.com/user/project/actions/runs/456",
        total_tests=50,
        passed_tests=48,
        failed_tests=2,
        skipped_tests=0,
        failures=[failure],
    )


class TestFormatUnifiedAsJson:
    """Tests for format_unified_as_json function."""

    def test_returns_valid_json(self, sample_unified_run):
        """Should return valid JSON string."""
        result = format_unified_as_json(sample_unified_run)

        # Should be parseable
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_includes_run_metadata(self, sample_unified_run):
        """Should include run metadata."""
        result = format_unified_as_json(sample_unified_run)
        data = json.loads(result)

        assert data["run_id"] == "run-456"
        assert data["repository"] == "user/project"
        assert data["branch"] == "feature/forms"

    def test_includes_test_counts(self, sample_unified_run):
        """Should include test counts."""
        result = format_unified_as_json(sample_unified_run)
        data = json.loads(result)

        assert data["total_tests"] == 50
        assert data["passed_tests"] == 48
        assert data["failed_tests"] == 2

    def test_includes_failures(self, sample_unified_run):
        """Should include failure details."""
        result = format_unified_as_json(sample_unified_run)
        data = json.loads(result)

        assert "failures" in data
        assert len(data["failures"]) == 1

        failure = data["failures"][0]
        assert failure["test_id"] == "test-1"
        assert failure["test_title"] == "should validate user input"

    def test_includes_error_info(self, sample_unified_run):
        """Should include error information."""
        result = format_unified_as_json(sample_unified_run)
        data = json.loads(result)

        error = data["failures"][0]["error"]
        assert "Expected element to be visible" in error["message"]
        assert "tests/example.spec.ts:25" in error["stack_trace"]

    def test_includes_failure_metadata(self, sample_unified_run):
        """Should include failure metadata."""
        result = format_unified_as_json(sample_unified_run)
        data = json.loads(result)

        metadata = data["failures"][0]["metadata"]
        assert metadata["framework"] == "playwright"
        assert metadata["browser"] == "chromium"
        assert metadata["retry_count"] == 2
        assert metadata["duration_ms"] == 3500


class TestFormatUnifiedAsMarkdown:
    """Tests for format_unified_as_markdown function."""

    def test_returns_string(self, sample_unified_run):
        """Should return markdown string."""
        result = format_unified_as_markdown(sample_unified_run)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_header(self, sample_unified_run):
        """Should include a header."""
        result = format_unified_as_markdown(sample_unified_run)

        assert "##" in result or "**" in result

    def test_includes_summary(self, sample_unified_run):
        """Should include test summary."""
        result = format_unified_as_markdown(sample_unified_run)

        assert "50" in result or "total" in result.lower()
        assert "48" in result or "passed" in result.lower()

    def test_includes_failure_title(self, sample_unified_run):
        """Should include failure test title."""
        result = format_unified_as_markdown(sample_unified_run)

        assert "should validate user input" in result

    def test_includes_error_message(self, sample_unified_run):
        """Should include error message."""
        result = format_unified_as_markdown(sample_unified_run)

        assert "Expected element to be visible" in result

    def test_includes_file_path(self, sample_unified_run):
        """Should include file path."""
        result = format_unified_as_markdown(sample_unified_run)

        assert "tests/example.spec.ts" in result

    def test_includes_browser_info(self, sample_unified_run):
        """Should include browser information."""
        result = format_unified_as_markdown(sample_unified_run)

        assert "chromium" in result.lower()

    def test_handles_multiple_failures(self, sample_unified_run):
        """Should handle multiple failures."""
        failure2 = UnifiedFailure(
            test_id="test-2",
            file_path="tests/login.spec.ts",
            test_title="should redirect after login",
            suite_path=["Auth"],
            error=ErrorInfo(
                message="Navigation timeout",
                stack_trace="at tests/login.spec.ts:30",
                location=None,
            ),
            metadata=FailureMetadata(
                framework=Framework.PLAYWRIGHT,
                browser="webkit",
                retry_count=0,
                duration_ms=30000,
                tags=[],
            ),
        )
        sample_unified_run.failures.append(failure2)

        result = format_unified_as_markdown(sample_unified_run)

        assert "should validate user input" in result
        assert "should redirect after login" in result
        assert "Navigation timeout" in result

    def test_handles_empty_failures(self):
        """Should handle run with no failures."""
        run = UnifiedTestRun(
            run_id="run-789",
            repository=None,
            branch=None,
            commit_sha=None,
            workflow_name=None,
            run_url=None,
            total_tests=10,
            passed_tests=10,
            failed_tests=0,
            skipped_tests=0,
            failures=[],
        )

        result = format_unified_as_markdown(run)

        assert "10" in result or "passed" in result.lower()
