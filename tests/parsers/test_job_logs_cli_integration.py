"""Tests for job logs CLI integration.

These tests verify that Heisenberg CLI can fetch and use job logs
to enhance failure analysis.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from heisenberg.parsers.job_logs import JobLogsProcessor


class TestJobLogsFetching:
    """Tests for fetching job logs from GitHub Actions."""

    @patch("subprocess.run")
    def test_fetch_job_logs_via_gh_cli(self, mock_run):
        """Fetch job logs using gh CLI."""
        from heisenberg.integrations.github_logs import GitHubLogsFetcher

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Log content here\n[error] Test failed\nMore logs",
        )

        fetcher = GitHubLogsFetcher()
        logs = fetcher.fetch_job_logs(
            repo="owner/repo",
            job_id="12345",
        )

        assert logs == "Log content here\n[error] Test failed\nMore logs"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_fetch_job_logs_handles_error(self, mock_run):
        """Handle errors when fetching job logs."""
        from heisenberg.integrations.github_logs import GitHubLogsFetcher

        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Not found",
        )

        fetcher = GitHubLogsFetcher()
        logs = fetcher.fetch_job_logs(
            repo="owner/repo",
            job_id="invalid",
        )

        assert logs is None

    @patch("subprocess.run")
    def test_fetch_failed_jobs_for_run(self, mock_run):
        """Get list of failed jobs for a workflow run."""
        from heisenberg.integrations.github_logs import GitHubLogsFetcher

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "jobs": [
                        {"id": 1, "name": "test", "conclusion": "failure"},
                        {"id": 2, "name": "build", "conclusion": "success"},
                        {"id": 3, "name": "e2e", "conclusion": "failure"},
                    ]
                }
            ),
        )

        fetcher = GitHubLogsFetcher()
        failed_jobs = fetcher.get_failed_jobs(
            repo="owner/repo",
            run_id="99999",
        )

        assert len(failed_jobs) == 2
        assert failed_jobs[0]["id"] == 1
        assert failed_jobs[1]["id"] == 3


class TestJobLogsIntegration:
    """Tests for integrating job logs with analysis."""

    def test_process_logs_and_add_to_prompt(self):
        """Process job logs and format for AI prompt."""
        log_content = """
Starting test run...
[error] Authentication failed: Invalid token
Stack trace follows...
""".strip()

        processor = JobLogsProcessor()
        snippets = processor.extract_snippets(log_content)
        formatted = processor.format_for_prompt(snippets)

        assert "### Relevant Job Log Snippets:" in formatted
        assert "Authentication failed" in formatted

    def test_combined_report_and_logs(self):
        """Combine test report failures with job log context."""
        # Simulate what the CLI would do
        from heisenberg.core.models import ErrorInfo, UnifiedFailure

        failure = UnifiedFailure(
            test_id="1",
            file_path="tests/auth.test.js",
            test_title="should reject invalid token",
            error=ErrorInfo(message="Expected 401 but got 500"),
        )

        log_content = """
[error] should reject invalid token: Expected 401 but got 500
    at tests/auth.test.js:42
Database connection error: timeout
""".strip()

        processor = JobLogsProcessor()
        snippets = processor.extract_snippets(
            log_content,
            filter_tests=[failure.test_title],
        )

        assert len(snippets) >= 1
        assert failure.test_title in snippets[0].content


class TestEnhancedPromptBuilder:
    """Tests for building prompts with log context."""

    def test_prompt_includes_log_snippets(self):
        """AI prompt should include relevant log snippets."""
        from heisenberg.core.models import (
            ErrorInfo,
            FailureMetadata,
            Framework,
            UnifiedFailure,
            UnifiedTestRun,
        )
        from heisenberg.llm.prompts import build_unified_prompt

        failure = UnifiedFailure(
            test_id="1",
            file_path="tests/api.test.js",
            test_title="API health check",
            error=ErrorInfo(message="Connection refused"),
            metadata=FailureMetadata(framework=Framework.PLAYWRIGHT),
        )

        test_run = UnifiedTestRun(
            run_id="test-123",
            total_tests=10,
            passed_tests=9,
            failed_tests=1,
            skipped_tests=0,
            failures=[failure],
        )

        log_snippets = """### Relevant Job Log Snippets:

[LINE 42] [error] Connection refused to localhost:3000
[LINE 43] Server not running"""

        system_prompt, user_prompt = build_unified_prompt(
            test_run,
            job_logs_context=log_snippets,
        )

        assert "Connection refused" in user_prompt
        assert "Job Log Snippets" in user_prompt
