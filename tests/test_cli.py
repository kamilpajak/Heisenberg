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
        )

        # When
        run_analyze(args)
        captured = capsys.readouterr()

        # Then
        assert "Heisenberg Test Analysis" in captured.out
        assert "Failed Tests:" in captured.out


@pytest.fixture
def sample_report_path() -> Path:
    """Path to sample Playwright report fixture."""
    return Path(__file__).parent / "fixtures" / "playwright_report.json"
