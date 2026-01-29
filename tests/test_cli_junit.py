"""Tests for CLI JUnit analysis functionality."""

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from heisenberg.cli.commands import _run_junit_analyze, run_analyze
from heisenberg.cli.formatters import format_junit_json, format_junit_text


@pytest.fixture
def sample_junit_xml(tmp_path: Path) -> Path:
    """Create a sample JUnit XML file."""
    junit_xml = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites tests="5" failures="2" errors="0" skipped="1" time="10.5">
  <testsuite name="TestSuite1" tests="3" failures="1" errors="0" skipped="0" time="5.2">
    <testcase name="test_passing" classname="TestSuite1" time="1.0"/>
    <testcase name="test_failing" classname="TestSuite1" time="2.0">
      <failure message="AssertionError: expected True but got False">
AssertionError: expected True but got False
at TestSuite1.test_failing (test_example.py:15)
      </failure>
    </testcase>
    <testcase name="test_another" classname="TestSuite1" time="2.2"/>
  </testsuite>
  <testsuite name="TestSuite2" tests="2" failures="1" errors="0" skipped="1" time="5.3">
    <testcase name="test_skipped" classname="TestSuite2" time="0.0">
      <skipped message="Not implemented yet"/>
    </testcase>
    <testcase name="test_also_failing" classname="TestSuite2" time="3.0">
      <failure message="ValueError: invalid input">
ValueError: invalid input
at TestSuite2.test_also_failing (test_other.py:42)
      </failure>
    </testcase>
  </testsuite>
</testsuites>"""
    junit_path = tmp_path / "junit-report.xml"
    junit_path.write_text(junit_xml)
    return junit_path


@pytest.fixture
def passing_junit_xml(tmp_path: Path) -> Path:
    """Create a passing JUnit XML file."""
    junit_xml = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites tests="3" failures="0" errors="0" skipped="0" time="3.0">
  <testsuite name="PassingSuite" tests="3" failures="0" errors="0" skipped="0" time="3.0">
    <testcase name="test_one" classname="PassingSuite" time="1.0"/>
    <testcase name="test_two" classname="PassingSuite" time="1.0"/>
    <testcase name="test_three" classname="PassingSuite" time="1.0"/>
  </testsuite>
</testsuites>"""
    junit_path = tmp_path / "junit-passing.xml"
    junit_path.write_text(junit_xml)
    return junit_path


@pytest.fixture
def mock_junit_report():
    """Create a mock JUnit report object."""
    mock_tc1 = MagicMock()
    mock_tc1.name = "test_failing"
    mock_tc1.classname = "TestSuite1"
    mock_tc1.status = "failed"
    mock_tc1.failure_message = "AssertionError: expected True"

    mock_tc2 = MagicMock()
    mock_tc2.name = "test_also_failing"
    mock_tc2.classname = "TestSuite2"
    mock_tc2.status = "failed"
    mock_tc2.failure_message = "ValueError: invalid input"

    mock_report = MagicMock()
    mock_report.total_tests = 5
    mock_report.total_passed = 2
    mock_report.total_failed = 2
    mock_report.total_errors = 0
    mock_report.total_skipped = 1
    mock_report.failed_tests = [mock_tc1, mock_tc2]
    return mock_report


class TestRunJunitAnalyze:
    """Tests for _run_junit_analyze function."""

    def test_run_junit_analyze_returns_one_for_failures(self, sample_junit_xml: Path, capsys):
        """Should return exit code 1 when tests fail."""
        args = argparse.Namespace(
            report=sample_junit_xml,
            report_format="junit",
            output_format="text",
            ai_analysis=False,
            provider="anthropic",
            model=None,
        )

        result = _run_junit_analyze(args)
        captured = capsys.readouterr()

        assert result == 1
        assert "JUnit" in captured.out

    def test_run_junit_analyze_returns_zero_for_passing(self, passing_junit_xml: Path, capsys):
        """Should return exit code 0 when all tests pass."""
        args = argparse.Namespace(
            report=passing_junit_xml,
            report_format="junit",
            output_format="text",
            ai_analysis=False,
            provider="anthropic",
            model=None,
        )

        result = _run_junit_analyze(args)

        assert result == 0

    def test_run_junit_analyze_json_format(self, sample_junit_xml: Path, capsys):
        """Should output valid JSON with json format."""
        args = argparse.Namespace(
            report=sample_junit_xml,
            report_format="junit",
            output_format="json",
            ai_analysis=False,
            provider="anthropic",
            model=None,
        )

        _run_junit_analyze(args)
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        assert data["has_failures"] is True
        assert data["summary"]["failed"] == 2
        assert len(data["failed_tests"]) == 2

    def test_run_junit_analyze_unified_json_format(self, sample_junit_xml: Path, capsys):
        """Should output unified JSON format."""
        args = argparse.Namespace(
            report=sample_junit_xml,
            report_format="junit",
            output_format="unified-json",
            ai_analysis=False,
            provider="anthropic",
            model=None,
        )

        _run_junit_analyze(args)
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        # Unified format has fields at root level
        assert "failures" in data
        assert "run_id" in data

    def test_run_junit_analyze_github_comment_format(self, sample_junit_xml: Path, capsys):
        """Should output markdown with github-comment format."""
        args = argparse.Namespace(
            report=sample_junit_xml,
            report_format="junit",
            output_format="github-comment",
            ai_analysis=False,
            provider="anthropic",
            model=None,
        )

        _run_junit_analyze(args)
        captured = capsys.readouterr()

        assert "##" in captured.out or "**" in captured.out  # Markdown formatting

    def test_run_junit_analyze_invalid_file(self, tmp_path: Path, capsys):
        """Should return 1 for invalid XML file."""
        invalid_xml = tmp_path / "invalid.xml"
        invalid_xml.write_text("not valid xml content")

        args = argparse.Namespace(
            report=invalid_xml,
            report_format="junit",
            output_format="text",
            ai_analysis=False,
            provider="anthropic",
            model=None,
        )

        result = _run_junit_analyze(args)
        captured = capsys.readouterr()

        assert result == 1
        assert "Error" in captured.err

    def test_run_junit_analyze_with_ai_analysis(self, sample_junit_xml: Path, capsys, monkeypatch):
        """Should include AI analysis when flag is set."""
        from heisenberg.analysis import AIAnalysisResult
        from heisenberg.core.diagnosis import ConfidenceLevel, Diagnosis

        mock_result = AIAnalysisResult(
            diagnosis=Diagnosis(
                root_cause="Test assertion failed",
                evidence=["AssertionError in logs"],
                suggested_fix="Check expected values",
                confidence=ConfidenceLevel.HIGH,
                confidence_explanation="Clear assertion failure",
                raw_response="AI response",
            ),
            input_tokens=500,
            output_tokens=200,
        )

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("heisenberg.cli.commands.analyze_unified_run", return_value=mock_result):
            args = argparse.Namespace(
                report=sample_junit_xml,
                report_format="junit",
                output_format="text",
                ai_analysis=True,
                provider="anthropic",
                model=None,
            )

            _run_junit_analyze(args)
            captured = capsys.readouterr()

            assert "AI" in captured.out or "Root" in captured.out

    def test_run_junit_analyze_ai_failure_warning(
        self, sample_junit_xml: Path, capsys, monkeypatch
    ):
        """Should print warning when AI analysis fails."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch(
            "heisenberg.cli.commands.analyze_unified_run",
            side_effect=Exception("API error"),
        ):
            args = argparse.Namespace(
                report=sample_junit_xml,
                report_format="junit",
                output_format="text",
                ai_analysis=True,
                provider="anthropic",
                model=None,
            )

            exit_code = _run_junit_analyze(args)
            captured = capsys.readouterr()

            assert exit_code == 1  # Still returns 1 for failed tests
            assert "Warning" in captured.err


class TestRunAnalyzeJunitDispatch:
    """Tests for run_analyze dispatching to JUnit."""

    def test_run_analyze_dispatches_to_junit(self, sample_junit_xml: Path, capsys):
        """Should dispatch to _run_junit_analyze for junit format."""
        args = argparse.Namespace(
            report=sample_junit_xml,
            report_format="junit",
            output_format="text",
            ai_analysis=False,
            provider="anthropic",
            model=None,
            docker_services="",
            log_window=30,
            post_comment=False,
        )

        result = run_analyze(args)
        captured = capsys.readouterr()

        assert result == 1
        assert "JUnit" in captured.out


class TestFormatJunitJson:
    """Tests for format_junit_json function."""

    def testformat_junit_json_basic(self, mock_junit_report):
        """Should format report as JSON."""
        result = format_junit_json(mock_junit_report, None)
        data = json.loads(result)

        assert data["has_failures"] is True
        assert data["summary"]["total"] == 5
        assert data["summary"]["passed"] == 2
        assert data["summary"]["failed"] == 2
        assert len(data["failed_tests"]) == 2

    def testformat_junit_json_with_ai_result(self, mock_junit_report):
        """Should include AI diagnosis when present."""
        from heisenberg.core.diagnosis import ConfidenceLevel, Diagnosis

        mock_ai_result = MagicMock()
        mock_ai_result.diagnosis = Diagnosis(
            root_cause="Database connection issue",
            evidence=["Timeout in logs"],
            suggested_fix="Check database connection",
            confidence=ConfidenceLevel.MEDIUM,
            confidence_explanation="Some evidence found",
            raw_response="AI response",
        )

        result = format_junit_json(mock_junit_report, mock_ai_result)
        data = json.loads(result)

        assert "ai_diagnosis" in data
        assert data["ai_diagnosis"]["root_cause"] == "Database connection issue"
        assert data["ai_diagnosis"]["confidence"] == "MEDIUM"

    def testformat_junit_json_failed_test_details(self, mock_junit_report):
        """Should include failed test details."""
        result = format_junit_json(mock_junit_report, None)
        data = json.loads(result)

        assert data["failed_tests"][0]["name"] == "test_failing"
        assert data["failed_tests"][0]["classname"] == "TestSuite1"
        assert data["failed_tests"][0]["status"] == "failed"
        assert "AssertionError" in data["failed_tests"][0]["error"]


class TestFormatJunitText:
    """Tests for format_junit_text function."""

    def testformat_junit_text_header(self, mock_junit_report):
        """Should include header."""
        result = format_junit_text(mock_junit_report)

        assert "Heisenberg Test Analysis (JUnit)" in result
        assert "=" in result

    def testformat_junit_text_summary(self, mock_junit_report):
        """Should include summary line."""
        result = format_junit_text(mock_junit_report)

        assert "2 passed" in result
        assert "2 failed" in result
        assert "1 skipped" in result

    def testformat_junit_text_failed_tests(self, mock_junit_report):
        """Should list failed tests."""
        result = format_junit_text(mock_junit_report)

        assert "Failed Tests:" in result
        assert "TestSuite1" in result
        assert "test_failing" in result
        assert "AssertionError" in result

    def testformat_junit_text_truncates_long_messages(self):
        """Should truncate error messages longer than 100 chars."""
        mock_tc = MagicMock()
        mock_tc.name = "test_long_error"
        mock_tc.classname = "TestSuite"
        mock_tc.status = "failed"
        mock_tc.failure_message = "A" * 150

        mock_report = MagicMock()
        mock_report.total_tests = 1
        mock_report.total_passed = 0
        mock_report.total_failed = 1
        mock_report.total_errors = 0
        mock_report.total_skipped = 0
        mock_report.failed_tests = [mock_tc]

        result = format_junit_text(mock_report)

        assert "..." in result

    def testformat_junit_text_with_ai_result(self, mock_junit_report):
        """Should include AI diagnosis when present."""
        from heisenberg.core.diagnosis import ConfidenceLevel, Diagnosis

        mock_ai_result = MagicMock()
        mock_ai_result.diagnosis = Diagnosis(
            root_cause="Assertion failure",
            evidence=["Stack trace shows assert"],
            suggested_fix="Fix assertion",
            confidence=ConfidenceLevel.HIGH,
            confidence_explanation="Clear evidence",
            raw_response="AI response",
        )
        mock_ai_result.total_tokens = 500
        mock_ai_result.estimated_cost = 0.01

        result = format_junit_text(mock_junit_report, mock_ai_result)

        assert "AI" in result or "Root" in result

    def testformat_junit_text_no_failures(self):
        """Should handle report with no failures."""
        mock_report = MagicMock()
        mock_report.total_tests = 5
        mock_report.total_passed = 5
        mock_report.total_failed = 0
        mock_report.total_errors = 0
        mock_report.total_skipped = 0
        mock_report.failed_tests = []

        result = format_junit_text(mock_report)

        assert "5 passed" in result
        assert "0 failed" in result
        assert "Failed Tests:" not in result
