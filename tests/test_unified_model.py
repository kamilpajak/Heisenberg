"""Tests for Unified Failure Model.

The UnifiedFailure model is a framework-agnostic representation of test failures.
It allows Heisenberg to analyze failures from any test framework (Playwright, Jest, Cypress, etc.)
through a common interface.
"""

from __future__ import annotations

from heisenberg.unified_model import (
    Attachments,
    ErrorInfo,
    FailureMetadata,
    Framework,
    UnifiedFailure,
    UnifiedTestRun,
)


class TestUnifiedFailureModel:
    """Tests for the UnifiedFailure dataclass."""

    def test_create_minimal_failure(self):
        """UnifiedFailure can be created with minimal required fields."""
        failure = UnifiedFailure(
            test_id="test-1",
            file_path="tests/login.spec.ts",
            test_title="should login successfully",
            error=ErrorInfo(message="Timeout waiting for selector"),
        )

        assert failure.test_id == "test-1"
        assert failure.file_path == "tests/login.spec.ts"
        assert failure.test_title == "should login successfully"
        assert failure.error.message == "Timeout waiting for selector"

    def test_create_full_failure(self):
        """UnifiedFailure can be created with all optional fields."""
        failure = UnifiedFailure(
            test_id="test-123",
            file_path="tests/checkout.spec.ts",
            test_title="should display error for invalid card",
            suite_path=["Billing", "Credit Card Flows"],
            error=ErrorInfo(
                message="Expected 'Error' but got 'Success'",
                stack_trace="at Object.<anonymous> (checkout.spec.ts:42:5)",
                location={"line": 42, "column": 5},
            ),
            attachments=Attachments(
                screenshot_url="https://storage.example.com/screenshot.png",
                trace_url="https://storage.example.com/trace.zip",
                video_url="https://storage.example.com/video.webm",
            ),
            metadata=FailureMetadata(
                framework=Framework.PLAYWRIGHT,
                browser="chromium",
                retry_count=2,
                duration_ms=5432,
            ),
        )

        assert failure.suite_path == ["Billing", "Credit Card Flows"]
        assert failure.error.location == {"line": 42, "column": 5}
        assert failure.attachments.screenshot_url == "https://storage.example.com/screenshot.png"
        assert failure.metadata.framework == Framework.PLAYWRIGHT
        assert failure.metadata.browser == "chromium"
        assert failure.metadata.retry_count == 2

    def test_error_info_minimal(self):
        """ErrorInfo requires only message."""
        error = ErrorInfo(message="Test failed")

        assert error.message == "Test failed"
        assert error.stack_trace is None
        assert error.location is None

    def test_error_info_full(self):
        """ErrorInfo can include stack trace and location."""
        error = ErrorInfo(
            message="Element not found",
            stack_trace="Error: Element not found\n    at findElement (test.ts:10)",
            location={"line": 10, "column": 1},
        )

        assert error.stack_trace is not None
        assert "findElement" in error.stack_trace
        assert error.location["line"] == 10

    def test_framework_enum(self):
        """Framework enum contains expected values."""
        assert Framework.PLAYWRIGHT.value == "playwright"
        assert Framework.JEST.value == "jest"
        assert Framework.CYPRESS.value == "cypress"
        assert Framework.VITEST.value == "vitest"


class TestUnifiedTestRun:
    """Tests for the UnifiedTestRun container."""

    def test_create_test_run(self):
        """UnifiedTestRun groups failures with run metadata."""
        run = UnifiedTestRun(
            run_id="github-run-12345",
            repository="owner/repo",
            branch="feature/login",
            commit_sha="abc123def",
            total_tests=100,
            passed_tests=95,
            failed_tests=3,
            skipped_tests=2,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="test.ts",
                    test_title="test 1",
                    error=ErrorInfo(message="Failed"),
                ),
                UnifiedFailure(
                    test_id="2",
                    file_path="test.ts",
                    test_title="test 2",
                    error=ErrorInfo(message="Timeout"),
                ),
            ],
        )

        assert run.run_id == "github-run-12345"
        assert run.total_tests == 100
        assert len(run.failures) == 2
        assert run.failures[0].test_title == "test 1"

    def test_test_run_summary(self):
        """UnifiedTestRun provides summary statistics."""
        run = UnifiedTestRun(
            run_id="run-1",
            total_tests=50,
            passed_tests=45,
            failed_tests=3,
            skipped_tests=2,
            failures=[],
        )

        summary = run.summary()

        assert summary["total"] == 50
        assert summary["passed"] == 45
        assert summary["failed"] == 3
        assert summary["skipped"] == 2
        assert summary["pass_rate"] == 0.9  # 45/50

    def test_test_run_to_dict(self):
        """UnifiedTestRun can be serialized to dict."""
        run = UnifiedTestRun(
            run_id="run-1",
            repository="owner/repo",
            total_tests=10,
            passed_tests=9,
            failed_tests=1,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="test.ts",
                    test_title="failing test",
                    error=ErrorInfo(message="Error"),
                ),
            ],
        )

        data = run.to_dict()

        assert data["run_id"] == "run-1"
        assert data["repository"] == "owner/repo"
        assert len(data["failures"]) == 1
        assert data["failures"][0]["test_title"] == "failing test"

    def test_test_run_from_dict(self):
        """UnifiedTestRun can be deserialized from dict."""
        data = {
            "run_id": "run-1",
            "repository": "owner/repo",
            "total_tests": 10,
            "passed_tests": 9,
            "failed_tests": 1,
            "skipped_tests": 0,
            "failures": [
                {
                    "test_id": "1",
                    "file_path": "test.ts",
                    "test_title": "failing test",
                    "error": {"message": "Error"},
                },
            ],
        }

        run = UnifiedTestRun.from_dict(data)

        assert run.run_id == "run-1"
        assert len(run.failures) == 1
        assert run.failures[0].error.message == "Error"


class TestPlaywrightToUnifiedTransformer:
    """Tests for transforming Playwright reports to UnifiedFailure."""

    def test_transform_single_failure(self):
        """Transform a single Playwright failure to UnifiedFailure."""
        from heisenberg.unified_model import PlaywrightTransformer

        playwright_failure = {
            "title": "login > should redirect to dashboard",
            "file": "tests/login.spec.ts",
            "line": 15,
            "column": 5,
            "status": "failed",
            "duration": 5000,
            "errors": [
                {
                    "message": "Timeout 30000ms exceeded.",
                    "stack": "Error: Timeout\n    at login.spec.ts:15:5",
                }
            ],
            "projectName": "chromium",
        }

        failure = PlaywrightTransformer.transform_failure(playwright_failure)

        assert failure.test_title == "login > should redirect to dashboard"
        assert failure.file_path == "tests/login.spec.ts"
        assert failure.error.message == "Timeout 30000ms exceeded."
        assert failure.error.location == {"line": 15, "column": 5}
        assert failure.metadata.framework == Framework.PLAYWRIGHT
        assert failure.metadata.browser == "chromium"
        assert failure.metadata.duration_ms == 5000

    def test_transform_full_report(self):
        """Transform a complete Playwright report to UnifiedTestRun."""
        from heisenberg.playwright_parser import ErrorDetail, FailedTest, PlaywrightReport
        from heisenberg.unified_model import PlaywrightTransformer

        # Create a PlaywrightReport with proper structure
        report = PlaywrightReport(
            total_passed=1,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="should show error",
                    file="login.spec.ts",
                    suite="Login",
                    project="chromium",
                    status="failed",
                    duration_ms=2000,
                    start_time=None,
                    errors=[ErrorDetail(message="Failed", stack="...")],
                )
            ],
        )

        run = PlaywrightTransformer.transform_report(report, run_id="test-run-1")

        assert run.run_id == "test-run-1"
        assert run.total_tests == 2
        assert run.passed_tests == 1
        assert run.failed_tests == 1
        assert len(run.failures) == 1
        assert run.failures[0].test_title == "should show error"

    def test_transform_handles_missing_fields(self):
        """Transformer handles missing optional fields gracefully."""
        from heisenberg.unified_model import PlaywrightTransformer

        minimal_failure = {
            "title": "basic test",
            "file": "test.ts",
            "status": "failed",
            "errors": [{"message": "Failed"}],
        }

        failure = PlaywrightTransformer.transform_failure(minimal_failure)

        assert failure.test_title == "basic test"
        assert failure.error.message == "Failed"
        assert failure.error.stack_trace is None
        assert failure.error.location is None
        assert failure.metadata.browser is None

    def test_transform_multiple_errors(self):
        """Transformer concatenates multiple errors."""
        from heisenberg.unified_model import PlaywrightTransformer

        failure_with_multiple_errors = {
            "title": "multi-error test",
            "file": "test.ts",
            "status": "failed",
            "errors": [
                {"message": "First error"},
                {"message": "Second error"},
            ],
        }

        failure = PlaywrightTransformer.transform_failure(failure_with_multiple_errors)

        assert "First error" in failure.error.message
        assert "Second error" in failure.error.message
