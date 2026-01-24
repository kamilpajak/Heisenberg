"""Tests for CLI module - TDD."""

import argparse
import json
from pathlib import Path

import pytest

from heisenberg.cli import run_analyze


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
        assert data["has_failures"] is True
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
        monkeypatch.setattr("heisenberg.cli.analyze_with_ai", mock_analyze)
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


@pytest.fixture
def sample_report_path() -> Path:
    """Path to sample Playwright report fixture."""
    return Path(__file__).parent / "fixtures" / "playwright_report.json"
