"""Tests for CLI module - TDD."""

import argparse
import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from heisenberg.cli.commands import (
    _analyze_report_data,
    _load_container_logs,
    _run_ai_analysis,
    run_analyze,
)
from heisenberg.cli.commands import (
    run_fetch_github as run_fetch_github_async,
)
from heisenberg.cli.formatters import (
    format_ai_diagnosis_section,
    format_container_logs_section,
    format_failed_tests_section,
)
from heisenberg.cli.github_fetch import fetch_report_from_run


# Sync wrapper for tests
def run_fetch_github(args):
    """Sync wrapper for run_fetch_github."""
    return asyncio.run(run_fetch_github_async(args))


class TestFormatHelpers:
    """Test suite for CLI format helper functions."""

    def testformat_failed_tests_section_includes_header(self):
        """Should include 'Failed Tests:' header."""
        mock_test = MagicMock()
        mock_test.full_name = "Test Suite > test case"
        mock_test.file = "tests/example.spec.ts"
        mock_test.status = "failed"
        mock_test.errors = []

        result = format_failed_tests_section([mock_test])
        result_str = "\n".join(result)

        assert "Failed Tests:" in result_str
        assert "Test Suite > test case" in result_str

    def testformat_failed_tests_section_truncates_long_errors(self):
        """Should truncate error messages longer than 100 chars."""
        mock_error = MagicMock()
        mock_error.message = "A" * 150

        mock_test = MagicMock()
        mock_test.full_name = "test"
        mock_test.file = "test.ts"
        mock_test.status = "failed"
        mock_test.errors = [mock_error]

        result = format_failed_tests_section([mock_test])

        assert "..." in "\n".join(result)

    def testformat_container_logs_section_includes_header(self):
        """Should include 'Backend Logs:' header."""
        mock_logs = MagicMock()
        mock_logs.entries = ["log entry 1", "log entry 2"]

        result = format_container_logs_section({"api": mock_logs})
        result_str = "\n".join(result)

        assert "Backend Logs:" in result_str
        assert "[api]" in result_str

    def testformat_container_logs_section_limits_entries(self):
        """Should limit to 10 entries per container."""
        mock_logs = MagicMock()
        mock_logs.entries = [f"entry {i}" for i in range(20)]

        result = format_container_logs_section({"api": mock_logs})

        assert "... and 10 more entries" in "\n".join(result)

    def testformat_ai_diagnosis_section_includes_all_fields(self):
        """Should include root cause, evidence, fix, and confidence."""
        mock_diagnosis = MagicMock()
        mock_diagnosis.root_cause = "Database timeout"
        mock_diagnosis.evidence = ["Error in logs", "Slow query"]
        mock_diagnosis.suggested_fix = "Increase timeout"
        mock_diagnosis.confidence.value = "HIGH"
        mock_diagnosis.confidence_explanation = "Clear pattern"

        mock_ai_result = MagicMock()
        mock_ai_result.diagnosis = mock_diagnosis
        mock_ai_result.total_tokens = 1000
        mock_ai_result.estimated_cost = 0.05

        result = format_ai_diagnosis_section(mock_ai_result)
        result_str = "\n".join(result)

        assert "AI Diagnosis:" in result_str
        assert "Database timeout" in result_str
        assert "Error in logs" in result_str
        assert "Increase timeout" in result_str
        assert "HIGH" in result_str

    def testformat_ai_diagnosis_section_handles_no_evidence(self):
        """Should handle empty evidence list."""
        mock_diagnosis = MagicMock()
        mock_diagnosis.root_cause = "Unknown"
        mock_diagnosis.evidence = []
        mock_diagnosis.suggested_fix = "Investigate"
        mock_diagnosis.confidence.value = "LOW"
        mock_diagnosis.confidence_explanation = None

        mock_ai_result = MagicMock()
        mock_ai_result.diagnosis = mock_diagnosis
        mock_ai_result.total_tokens = 500
        mock_ai_result.estimated_cost = 0.02

        result = format_ai_diagnosis_section(mock_ai_result)
        result_str = "\n".join(result)

        assert "Evidence:" not in result_str


class TestCliAnalyze:
    """Test suite for analyze command."""

    def test_analyze_returns_zero_for_passing_tests(self, tmp_path: Path):
        """Given all tests pass, should return exit code 0."""
        # Given
        report_file = tmp_path / "report.json"
        report_file.write_text(
            json.dumps(
                {
                    "suites": [],
                    "stats": {"expected": 5, "unexpected": 0, "flaky": 0, "skipped": 0},
                }
            )
        )

        args = argparse.Namespace(
            report=report_file,
            output_format="text",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=False,
        )

        # When
        result = run_analyze(args)

        # Then
        assert result == 0

    def test_analyze_returns_one_for_failing_tests(self, sample_report_path: Path):
        """Given tests fail, should return exit code 1."""
        # Given
        args = argparse.Namespace(
            report=sample_report_path,
            output_format="text",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=False,
        )

        # When
        result = run_analyze(args)

        # Then
        assert result == 1

    def test_analyze_returns_one_for_missing_file(self, tmp_path: Path):
        """Given report file doesn't exist, should return exit code 1."""
        # Given
        args = argparse.Namespace(
            report=tmp_path / "nonexistent.json",
            output_format="text",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=False,
        )

        # When
        result = run_analyze(args)

        # Then
        assert result == 1

    def test_analyze_github_comment_format(self, sample_report_path: Path, capsys):
        """Given github-comment format, should output markdown."""
        # Given
        args = argparse.Namespace(
            report=sample_report_path,
            output_format="github-comment",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=False,
        )

        # When
        run_analyze(args)
        captured = capsys.readouterr()

        # Then
        assert "## Heisenberg" in captured.out
        assert "**" in captured.out  # Markdown formatting

    def test_analyze_text_format(self, sample_report_path: Path, capsys):
        """Given text format, should output plain text."""
        # Given
        args = argparse.Namespace(
            report=sample_report_path,
            output_format="text",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=False,
        )

        # When
        run_analyze(args)
        captured = capsys.readouterr()

        # Then
        assert "Heisenberg Test Analysis" in captured.out
        assert "Failed Tests:" in captured.out

    def test_analyze_json_format(self, sample_report_path: Path, capsys):
        """Given json format, should output valid JSON."""
        # Given
        args = argparse.Namespace(
            report=sample_report_path,
            output_format="json",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=False,
        )

        # When
        run_analyze(args)
        captured = capsys.readouterr()

        # Then
        data = json.loads(captured.out)
        assert data["has_failures"]
        assert data["failed_tests_count"] == 2
        assert len(data["failed_tests"]) == 2


class TestCliAIAnalysis:
    """Test suite for AI-powered analysis in CLI."""

    @pytest.fixture
    def mock_ai_analyzer(self, monkeypatch):
        """Mock the AI analyzer for testing."""
        from unittest.mock import MagicMock

        from heisenberg.ai_analyzer import AIAnalysisResult
        from heisenberg.diagnosis import ConfidenceLevel, Diagnosis

        mock_result = AIAnalysisResult(
            diagnosis=Diagnosis(
                root_cause="Database timeout",
                evidence=["Error in logs"],
                suggested_fix="Increase timeout",
                confidence=ConfidenceLevel.HIGH,
                confidence_explanation="Clear evidence",
                raw_response="AI response",
            ),
            input_tokens=500,
            output_tokens=200,
        )

        mock_analyze = MagicMock(return_value=mock_result)
        monkeypatch.setattr("heisenberg.cli.commands.analyze_with_ai", mock_analyze)
        return mock_analyze

    def test_analyze_with_ai_flag(
        self, sample_report_path: Path, capsys, mock_ai_analyzer, monkeypatch
    ):
        """Given --ai-analysis flag, should include AI diagnosis."""
        # Given
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        args = argparse.Namespace(
            report=sample_report_path,
            output_format="github-comment",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=True,
        )

        # When
        run_analyze(args)
        captured = capsys.readouterr()

        # Then
        mock_ai_analyzer.assert_called_once()
        assert "AI Analysis" in captured.out or "Root Cause" in captured.out

    def test_analyze_without_ai_flag(self, sample_report_path: Path, capsys, mock_ai_analyzer):
        """Given no --ai-analysis flag, should not call AI."""
        # Given
        args = argparse.Namespace(
            report=sample_report_path,
            output_format="text",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=False,
        )

        # When
        run_analyze(args)

        # Then
        mock_ai_analyzer.assert_not_called()

    def test_ai_analysis_text_output(
        self, sample_report_path: Path, capsys, mock_ai_analyzer, monkeypatch
    ):
        """AI analysis should work with text output format."""
        # Given
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        args = argparse.Namespace(
            report=sample_report_path,
            output_format="text",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=True,
        )

        # When
        run_analyze(args)
        captured = capsys.readouterr()

        # Then
        assert "AI Diagnosis" in captured.out or "Root Cause" in captured.out

    def test_ai_analysis_json_output(
        self, sample_report_path: Path, capsys, mock_ai_analyzer, monkeypatch
    ):
        """AI analysis should include diagnosis in JSON output."""
        # Given
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        args = argparse.Namespace(
            report=sample_report_path,
            output_format="json",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=True,
        )

        # When
        run_analyze(args)
        captured = capsys.readouterr()

        # Then
        data = json.loads(captured.out)
        assert "ai_diagnosis" in data
        assert data["ai_diagnosis"]["confidence"] == "HIGH"


class TestFetchGitHubHelpers:
    """Test suite for fetch-github helper functions."""

    @pytest.mark.asyncio
    async def testfetch_report_from_run_returns_none_for_no_matching_artifacts(self):
        """Should return None when no matching artifacts found."""
        mock_client = MagicMock()
        mock_client.get_artifacts = MagicMock(return_value=[])
        mock_client.get_artifacts.return_value = []

        # Make it awaitable
        async def mock_get_artifacts(*args, **kwargs):
            return []

        mock_client.get_artifacts = mock_get_artifacts

        result = await fetch_report_from_run(mock_client, "owner", "repo", 123, "playwright")

        assert result is None

    @pytest.mark.asyncio
    async def testfetch_report_from_run_downloads_matching_artifact(self):
        """Should download artifact when matching name found."""
        mock_artifact = MagicMock()
        mock_artifact.name = "playwright-report"
        mock_artifact.id = 456

        mock_client = MagicMock()

        async def mock_get_artifacts(*args, **kwargs):
            return [mock_artifact]

        async def mock_download(*args, **kwargs):
            return b"fake zip data"

        mock_client.get_artifacts = mock_get_artifacts
        mock_client.download_artifact = mock_download
        mock_client.extract_playwright_report = MagicMock(return_value={"suites": []})

        result = await fetch_report_from_run(mock_client, "owner", "repo", 123, "playwright")

        assert result == {"suites": []}

    def test_analyze_report_data_returns_exit_code(self, tmp_path):
        """Should return exit code based on test failures."""
        report_data = {
            "suites": [],
            "stats": {"expected": 5, "unexpected": 0, "flaky": 0, "skipped": 0},
        }
        args = MagicMock()
        args.ai_analysis = False

        result = _analyze_report_data(report_data, args)

        assert result == 0  # No failures

    def test_run_fetch_github_fails_without_token(self, monkeypatch):
        """Should fail when no token provided."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        args = MagicMock()
        args.token = None
        args.repo = "owner/repo"

        result = run_fetch_github(args)

        assert result == 1

    def test_run_fetch_github_fails_with_invalid_repo_format(self, monkeypatch):
        """Should fail when repo format is invalid."""
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        args = MagicMock()
        args.token = None
        args.repo = "invalid-format"

        result = run_fetch_github(args)

        assert result == 1


class TestLoadContainerLogs:
    """Test suite for _load_container_logs helper."""

    def test_returns_original_logs_when_no_path_provided(self):
        """Should return original logs when no container_logs path."""
        args = MagicMock()
        args.container_logs = None

        result_mock = MagicMock()
        result_mock.container_logs = {"api": "logs"}

        result = _load_container_logs(args, result_mock)

        assert result == {"api": "logs"}

    def test_adds_file_logs_when_path_exists(self, tmp_path):
        """Should add logs from file when path exists."""
        log_file = tmp_path / "logs.txt"
        log_file.write_text("file log content")

        args = MagicMock()
        args.container_logs = log_file

        result_mock = MagicMock()
        result_mock.container_logs = None

        result = _load_container_logs(args, result_mock)

        assert result["logs_file"] == "file log content"


class TestRunAIAnalysis:
    """Test suite for _run_ai_analysis helper."""

    def test_returns_none_when_ai_analysis_disabled(self):
        """Should return None when ai_analysis is False."""
        args = MagicMock()
        args.ai_analysis = False

        result_mock = MagicMock()
        result_mock.has_failures = True

        result = _run_ai_analysis(args, result_mock, None)

        assert result is None

    def test_returns_none_when_no_failures(self):
        """Should return None when no test failures."""
        args = MagicMock()
        args.ai_analysis = True

        result_mock = MagicMock()
        result_mock.has_failures = False

        result = _run_ai_analysis(args, result_mock, None)

        assert result is None


class TestValidateApiKeyForProvider:
    """Test suite for validate_api_key_for_provider function."""

    def test_returns_none_when_anthropic_key_is_set(self, monkeypatch):
        """Should return None (valid) when ANTHROPIC_API_KEY is set."""
        from heisenberg.cli.commands import validate_api_key_for_provider

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        result = validate_api_key_for_provider("anthropic")
        assert result is None

    def test_returns_none_when_openai_key_is_set(self, monkeypatch):
        """Should return None (valid) when OPENAI_API_KEY is set."""
        from heisenberg.cli.commands import validate_api_key_for_provider

        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        result = validate_api_key_for_provider("openai")
        assert result is None

    def test_returns_none_when_google_key_is_set(self, monkeypatch):
        """Should return None (valid) when GOOGLE_API_KEY is set."""
        from heisenberg.cli.commands import validate_api_key_for_provider

        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        result = validate_api_key_for_provider("google")
        assert result is None

    def test_returns_error_when_anthropic_key_missing(self, monkeypatch):
        """Should return error message when ANTHROPIC_API_KEY is not set."""
        from heisenberg.cli.commands import validate_api_key_for_provider

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = validate_api_key_for_provider("anthropic")
        assert result is not None
        assert "ANTHROPIC_API_KEY" in result

    def test_returns_error_when_openai_key_missing(self, monkeypatch):
        """Should return error message when OPENAI_API_KEY is not set."""
        from heisenberg.cli.commands import validate_api_key_for_provider

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = validate_api_key_for_provider("openai")
        assert result is not None
        assert "OPENAI_API_KEY" in result

    def test_returns_error_when_google_key_missing(self, monkeypatch):
        """Should return error message when GOOGLE_API_KEY is not set."""
        from heisenberg.cli.commands import validate_api_key_for_provider

        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        result = validate_api_key_for_provider("google")
        assert result is not None
        assert "GOOGLE_API_KEY" in result

    def test_returns_error_for_unknown_provider(self):
        """Should return error message for unknown provider."""
        from heisenberg.cli.commands import validate_api_key_for_provider

        result = validate_api_key_for_provider("unknown-provider")
        assert result is not None
        assert "Unknown provider" in result


class TestAIAnalysisAPIKeyValidation:
    """Test suite for API key validation when --ai-analysis is enabled.

    Requirements:
    1. When --ai-analysis is requested but API key is missing, CLI should:
       - Return exit code 1 immediately (fail fast)
       - Print clear "Error:" message to stderr (not "Warning:")
       - Mention the specific environment variable needed for the provider
       - NOT print the analysis summary (fail before processing)
    """

    def test_ai_analysis_fails_fast_when_anthropic_key_missing(
        self, sample_report_path: Path, capsys, monkeypatch
    ):
        """Given --ai-analysis with claude provider but no API key, should fail fast with error."""
        # Given
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        args = argparse.Namespace(
            report=sample_report_path,
            output_format="text",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=True,
            provider="anthropic",
            model=None,
        )

        # When
        result = run_analyze(args)
        captured = capsys.readouterr()

        # Then - should fail fast with clear error
        assert result == 1, "Should return exit code 1 when API key is missing"
        assert "ANTHROPIC_API_KEY" in captured.err, "Should mention the required env var"
        assert "Error:" in captured.err, "Should print 'Error:' not 'Warning:'"
        assert "Summary:" not in captured.out, "Should fail fast before printing analysis"

    def test_ai_analysis_fails_fast_when_openai_key_missing(
        self, sample_report_path: Path, capsys, monkeypatch
    ):
        """Given --ai-analysis with openai provider but no API key, should fail fast with error."""
        # Given
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        args = argparse.Namespace(
            report=sample_report_path,
            output_format="text",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=True,
            provider="openai",
            model=None,
        )

        # When
        result = run_analyze(args)
        captured = capsys.readouterr()

        # Then
        assert result == 1, "Should return exit code 1 when API key is missing"
        assert "OPENAI_API_KEY" in captured.err, "Should mention the required env var"
        assert "Error:" in captured.err, "Should print 'Error:' not 'Warning:'"
        assert "Summary:" not in captured.out, "Should fail fast before printing analysis"

    def test_ai_analysis_fails_fast_when_google_key_missing(
        self, sample_report_path: Path, capsys, monkeypatch
    ):
        """Given --ai-analysis with gemini provider but no API key, should fail fast with error."""
        # Given
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        args = argparse.Namespace(
            report=sample_report_path,
            output_format="text",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=True,
            provider="google",
            model=None,
        )

        # When
        result = run_analyze(args)
        captured = capsys.readouterr()

        # Then
        assert result == 1, "Should return exit code 1 when API key is missing"
        assert "GOOGLE_API_KEY" in captured.err, "Should mention the required env var"
        assert "Error:" in captured.err, "Should print 'Error:' not 'Warning:'"
        assert "Summary:" not in captured.out, "Should fail fast before printing analysis"

    def test_ai_analysis_succeeds_when_correct_key_is_set(
        self, sample_report_path: Path, capsys, monkeypatch, mock_ai_analyzer
    ):
        """Given correct API key for provider, should proceed with analysis."""
        # Given
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        args = argparse.Namespace(
            report=sample_report_path,
            output_format="text",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=True,
            provider="openai",
            model=None,
        )

        # When
        result = run_analyze(args)
        captured = capsys.readouterr()

        # Then
        assert result == 1  # Exit 1 because tests failed, but AI analysis ran
        mock_ai_analyzer.assert_called_once()
        assert "Summary:" in captured.out, "Should print analysis when key is valid"
        assert "Error:" not in captured.err, "Should not print error when key is valid"

    def test_without_ai_analysis_flag_does_not_require_key(
        self, sample_report_path: Path, capsys, monkeypatch
    ):
        """Without --ai-analysis flag, should not require any API key."""
        # Given - no API keys set
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        args = argparse.Namespace(
            report=sample_report_path,
            output_format="text",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=False,  # AI analysis disabled
            provider="anthropic",
            model=None,
        )

        # When
        result = run_analyze(args)
        captured = capsys.readouterr()

        # Then - should succeed (exit 1 only because tests failed, not missing key)
        assert "Summary:" in captured.out, "Should print analysis without AI"
        assert "API_KEY" not in captured.err, "Should not complain about API key"

    @pytest.fixture
    def mock_ai_analyzer(self, monkeypatch):
        """Mock the AI analyzer for testing."""
        from unittest.mock import MagicMock

        from heisenberg.ai_analyzer import AIAnalysisResult
        from heisenberg.diagnosis import ConfidenceLevel, Diagnosis

        mock_result = AIAnalysisResult(
            diagnosis=Diagnosis(
                root_cause="Test failure",
                evidence=["Evidence"],
                suggested_fix="Fix it",
                confidence=ConfidenceLevel.HIGH,
                confidence_explanation="Clear",
                raw_response="Response",
            ),
            input_tokens=100,
            output_tokens=50,
        )

        mock_analyze = MagicMock(return_value=mock_result)
        monkeypatch.setattr("heisenberg.cli.commands.analyze_with_ai", mock_analyze)
        return mock_analyze


@pytest.fixture
def sample_report_path() -> Path:
    """Path to sample Playwright report fixture."""
    return Path(__file__).parent / "fixtures" / "playwright_report.json"
