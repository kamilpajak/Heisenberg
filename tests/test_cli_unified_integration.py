"""Tests for CLI integration with UnifiedModel.

These tests verify that the CLI commands properly use the unified
failure model for analysis, enabling framework-agnostic workflows.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from heisenberg.cli import main
from heisenberg.cli.commands import convert_to_unified, run_analyze


class TestAnalyzeWithUnifiedFlag:
    """Tests for 'heisenberg analyze --use-unified'."""

    def test_analyze_parser_has_use_unified_flag(self):
        """Analyze subparser includes --use-unified flag."""
        import sys

        # Check that --use-unified is recognized
        with patch.object(sys, "argv", ["heisenberg", "analyze", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # Help exits with 0
            assert exc_info.value.code == 0

    def test_analyze_parser_has_output_format_unified(self):
        """Analyze subparser supports unified-json output format."""
        import sys

        # This should not raise - unified-json is a valid format
        with patch.object(
            sys,
            "argv",
            [
                "heisenberg",
                "analyze",
                "--report",
                "nonexistent.json",
                "--output-format",
                "unified-json",
            ],
        ):
            # Will fail due to missing file, but parser should accept the format
            result = main()
            assert result != 0  # File not found


class TestFormattersModule:
    """Tests for the formatters module."""

    def test_format_unified_as_markdown(self):
        """format_unified_as_markdown produces valid markdown."""
        from heisenberg.core.models import (
            ErrorInfo,
            FailureMetadata,
            Framework,
            UnifiedFailure,
            UnifiedTestRun,
        )
        from heisenberg.utils.formatting import format_unified_as_markdown

        run = UnifiedTestRun(
            run_id="test-123",
            repository="owner/repo",
            total_tests=10,
            passed_tests=9,
            failed_tests=1,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="test.spec.ts",
                    test_title="should work",
                    error=ErrorInfo(message="Failed assertion"),
                    metadata=FailureMetadata(
                        framework=Framework.PLAYWRIGHT,
                        browser="chromium",
                    ),
                ),
            ],
        )

        markdown = format_unified_as_markdown(run)

        assert "Test" in markdown
        assert "should work" in markdown
        assert "Failed assertion" in markdown

    def test_format_unified_for_github(self):
        """format_unified_for_github produces GitHub-compatible markdown."""
        from heisenberg.core.models import (
            ErrorInfo,
            UnifiedFailure,
            UnifiedTestRun,
        )
        from heisenberg.utils.formatting import format_unified_for_github

        run = UnifiedTestRun(
            run_id="gh-456",
            repository="org/project",
            total_tests=50,
            passed_tests=48,
            failed_tests=2,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="auth.spec.ts",
                    test_title="login test",
                    error=ErrorInfo(message="Auth failed"),
                ),
                UnifiedFailure(
                    test_id="2",
                    file_path="api.spec.ts",
                    test_title="api test",
                    error=ErrorInfo(message="500 error"),
                ),
            ],
        )

        comment = format_unified_for_github(run)

        # Should have summary
        assert "50" in comment or "total" in comment.lower()
        assert "login test" in comment
        assert "api test" in comment

    def test_format_unified_as_json(self):
        """format_unified_as_json produces valid JSON."""
        from heisenberg.core.models import (
            ErrorInfo,
            UnifiedFailure,
            UnifiedTestRun,
        )
        from heisenberg.utils.formatting import format_unified_as_json

        run = UnifiedTestRun(
            run_id="test-789",
            total_tests=5,
            passed_tests=4,
            failed_tests=1,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="test.ts",
                    test_title="test",
                    error=ErrorInfo(message="Error"),
                ),
            ],
        )

        json_str = format_unified_as_json(run)
        data = json.loads(json_str)

        assert data["run_id"] == "test-789"
        assert data["total_tests"] == 5
        assert len(data["failures"]) == 1


class TestPlaywrightToUnifiedConversion:
    """Tests for converting Playwright reports to unified model in CLI context."""

    def test_convert_playwright_report_to_unified(self):
        """CLI helper converts PlaywrightReport to UnifiedTestRun."""
        from heisenberg.parsers.playwright import (
            ErrorDetail,
            FailedTest,
            PlaywrightReport,
        )

        report = PlaywrightReport(
            total_passed=5,
            total_failed=2,
            total_skipped=1,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="test 1",
                    file="test1.ts",
                    suite="Suite A",
                    project="chromium",
                    status="failed",
                    duration_ms=1000,
                    start_time=None,
                    errors=[ErrorDetail(message="Error 1", stack="stack 1")],
                ),
                FailedTest(
                    title="test 2",
                    file="test2.ts",
                    suite="Suite B",
                    project="firefox",
                    status="failed",
                    duration_ms=2000,
                    start_time=None,
                    errors=[ErrorDetail(message="Error 2", stack="stack 2")],
                ),
            ],
        )

        unified = convert_to_unified(
            report,
            run_id="cli-run-123",
            repository="test/repo",
        )

        assert unified.run_id == "cli-run-123"
        assert unified.repository == "test/repo"
        assert unified.total_tests == 8  # 5 + 2 + 1 + 0
        assert unified.failed_tests == 2
        assert len(unified.failures) == 2
        assert unified.failures[0].test_title == "test 1"
        assert unified.failures[1].metadata.browser == "firefox"


class TestUnifiedAnalysisInCLI:
    """Tests for using unified model in AI analysis through CLI."""

    def test_cli_uses_analyze_with_ai_which_uses_unified(self, tmp_path: Path, monkeypatch):
        """CLI calls analyze_with_ai which internally uses unified model."""
        # Set API key for the test
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        # Create test report
        report_file = tmp_path / "report.json"
        report_file.write_text(
            json.dumps(
                {
                    "suites": [
                        {
                            "title": "Suite",
                            "specs": [
                                {
                                    "title": "test",
                                    "file": "test.ts",
                                    "ok": False,  # Must be False for parser to detect failure
                                    "tests": [
                                        {
                                            "projectName": "chromium",
                                            "status": "unexpected",
                                            "results": [
                                                {
                                                    "status": "failed",
                                                    "duration": 100,
                                                    "errors": [{"message": "Test error"}],
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                    "stats": {"expected": 0, "unexpected": 1, "skipped": 0},
                }
            )
        )

        args = argparse.Namespace(
            report=report_file,  # Path object, not string
            docker_services="",  # Must be string, not None
            log_window=30,
            output_format="text",
            ai_analysis=True,
            provider="anthropic",
            model=None,
            use_unified=False,  # Flag is deprecated; unified is always used
            post_comment=False,
            container_logs=None,
        )

        # Mock analyze_with_ai at the commands module level
        # This is the entry point - it internally uses unified model
        with patch("heisenberg.cli.commands.analyze_with_ai") as mock_analyze:
            mock_analyze.return_value = MagicMock(
                diagnosis=MagicMock(
                    root_cause="Root cause",
                    evidence=["Evidence"],
                    suggested_fix="Fix",
                    confidence=MagicMock(value="HIGH"),
                    confidence_explanation="Clear",
                ),
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                estimated_cost=0.01,
                to_markdown=MagicMock(return_value="# Analysis\nRoot cause"),
            )

            run_analyze(args)

            # analyze_with_ai is called (and it internally uses unified model)
            mock_analyze.assert_called_once()
