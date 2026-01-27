"""Tests for prompt_builder unified model functions."""

import pytest

from heisenberg.core.models import (
    ErrorInfo,
    FailureMetadata,
    Framework,
    UnifiedFailure,
    UnifiedTestRun,
)
from heisenberg.llm.prompts import _build_unified_user_prompt, build_unified_prompt


@pytest.fixture
def sample_unified_run():
    """Create a sample unified test run."""
    failure = UnifiedFailure(
        test_id="test-1",
        file_path="tests/example.spec.ts",
        test_title="should work correctly",
        suite_path=["Suite", "Subsuite"],
        error=ErrorInfo(
            message="Expected true but got false",
            stack_trace="at tests/example.spec.ts:15",
            location=None,
        ),
        metadata=FailureMetadata(
            framework=Framework.PLAYWRIGHT,
            browser="chromium",
            retry_count=1,
            duration_ms=5000,
            tags=["smoke"],
        ),
    )

    return UnifiedTestRun(
        run_id="run-123",
        repository="owner/repo",
        branch="main",
        commit_sha="abc123",
        workflow_name="CI",
        run_url="https://github.com/owner/repo/actions/runs/123",
        total_tests=10,
        passed_tests=8,
        failed_tests=2,
        skipped_tests=0,
        failures=[failure],
    )


class TestBuildUnifiedPrompt:
    """Tests for build_unified_prompt function."""

    def test_returns_tuple_of_prompts(self, sample_unified_run):
        """Should return system and user prompts."""
        system, user = build_unified_prompt(sample_unified_run)

        assert isinstance(system, str)
        assert isinstance(user, str)
        assert len(system) > 0
        assert len(user) > 0

    def test_system_prompt_has_role(self, sample_unified_run):
        """System prompt should define role."""
        system, _ = build_unified_prompt(sample_unified_run)

        assert "test failure" in system.lower() or "root cause" in system.lower()

    def test_user_prompt_includes_failure_details(self, sample_unified_run):
        """User prompt should include failure information."""
        _, user = build_unified_prompt(sample_unified_run)

        assert "should work correctly" in user
        assert "Expected true but got false" in user

    def test_user_prompt_includes_context(self, sample_unified_run):
        """User prompt should include context sections."""
        _, user = build_unified_prompt(
            sample_unified_run,
            job_logs_context="ERROR: Database connection failed",
            screenshot_context="Screenshot shows error dialog",
            trace_context="Network request timed out",
        )

        assert "Database connection failed" in user
        assert "error dialog" in user
        assert "timed out" in user

    def test_user_prompt_includes_run_metadata(self, sample_unified_run):
        """User prompt should include run metadata."""
        _, user = build_unified_prompt(sample_unified_run)

        assert "run-123" in user or "owner/repo" in user

    def test_handles_multiple_failures(self, sample_unified_run):
        """Should handle multiple failures."""
        # Add another failure
        failure2 = UnifiedFailure(
            test_id="test-2",
            file_path="tests/other.spec.ts",
            test_title="should not crash",
            suite_path=["Other Suite"],
            error=ErrorInfo(
                message="Timeout exceeded",
                stack_trace="at tests/other.spec.ts:42",
                location=None,
            ),
            metadata=FailureMetadata(
                framework=Framework.PLAYWRIGHT,
                browser="firefox",
                retry_count=0,
                duration_ms=30000,
                tags=[],
            ),
        )
        sample_unified_run.failures.append(failure2)

        _, user = build_unified_prompt(sample_unified_run)

        assert "should work correctly" in user
        assert "should not crash" in user
        assert "Timeout exceeded" in user


class TestBuildUnifiedUserPrompt:
    """Tests for _build_unified_user_prompt function."""

    def test_includes_summary(self, sample_unified_run):
        """Should include test summary."""
        prompt = _build_unified_user_prompt(sample_unified_run, None, None, None, None)

        # Should mention pass/fail counts
        assert "8" in prompt or "passed" in prompt.lower()
        assert "2" in prompt or "failed" in prompt.lower()

    def test_formats_failure_details(self, sample_unified_run):
        """Should format failure details correctly."""
        prompt = _build_unified_user_prompt(sample_unified_run, None, None, None, None)

        # Test ID may not be included, but test title should be
        assert "should work correctly" in prompt
        assert "chromium" in prompt.lower() or "browser" in prompt.lower()

    def test_includes_stack_trace(self, sample_unified_run):
        """Should include stack trace."""
        prompt = _build_unified_user_prompt(sample_unified_run, None, None, None, None)

        assert "tests/example.spec.ts" in prompt

    def test_includes_job_logs_section(self, sample_unified_run):
        """Should include job logs when provided."""
        job_logs = "2024-01-01 ERROR: Connection refused"
        prompt = _build_unified_user_prompt(sample_unified_run, None, job_logs, None, None)

        # The content should be included, section header may vary
        assert "Connection refused" in prompt

    def test_includes_screenshot_section(self, sample_unified_run):
        """Should include screenshot analysis when provided."""
        screenshots = "Screenshot 1: Shows login page with error message"
        prompt = _build_unified_user_prompt(sample_unified_run, None, None, screenshots, None)

        assert "login page" in prompt.lower()
        assert "Screenshot" in prompt or "screenshot" in prompt.lower()

    def test_includes_trace_section(self, sample_unified_run):
        """Should include trace analysis when provided."""
        trace = "Network: GET /api/users - 500 Internal Server Error"
        prompt = _build_unified_user_prompt(sample_unified_run, None, None, None, trace)

        assert "500" in prompt
        assert "Trace" in prompt or "trace" in prompt.lower()

    def test_handles_no_context(self, sample_unified_run):
        """Should work without optional context."""
        prompt = _build_unified_user_prompt(sample_unified_run, None, None, None, None)

        # Should not have empty sections
        assert prompt is not None
        assert len(prompt) > 100  # Has meaningful content
