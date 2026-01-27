"""Tests for CLI unified output format and related paths."""

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from heisenberg.cli.commands import _load_container_logs, run_analyze


class TestCliUnifiedJsonOutput:
    """Tests for unified-json output format in CLI."""

    @pytest.fixture
    def sample_report_path(self) -> Path:
        """Path to sample Playwright report fixture."""
        return Path(__file__).parent / "fixtures" / "playwright_report.json"

    def test_unified_json_output_format(self, sample_report_path: Path, capsys):
        """Should output unified JSON format."""
        args = argparse.Namespace(
            report=sample_report_path,
            report_format="playwright",
            output_format="unified-json",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=False,
            use_unified=False,
            provider="anthropic",
            model=None,
        )

        run_analyze(args)
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        # Unified format has fields at root level
        assert "failures" in data
        assert "run_id" in data

    def test_unified_json_includes_failures(self, sample_report_path: Path, capsys):
        """Should include failure details in unified JSON."""
        args = argparse.Namespace(
            report=sample_report_path,
            report_format="playwright",
            output_format="unified-json",
            docker_services="",
            log_window=30,
            post_comment=False,
            ai_analysis=False,
            use_unified=False,
            provider="anthropic",
            model=None,
        )

        run_analyze(args)
        captured = capsys.readouterr()

        data = json.loads(captured.out)
        if data.get("failures"):
            failure = data["failures"][0]
            assert "test_id" in failure
            assert "error" in failure


class TestCliUseUnifiedFlag:
    """Tests for --use-unified flag behavior."""

    @pytest.fixture
    def sample_report_path(self) -> Path:
        """Path to sample Playwright report fixture."""
        return Path(__file__).parent / "fixtures" / "playwright_report.json"

    def test_use_unified_with_ai_analysis(self, sample_report_path: Path, capsys, monkeypatch):
        """Should use unified model for AI analysis when flag is set."""
        from heisenberg.core.analyzer import AIAnalysisResult
        from heisenberg.core.diagnosis import ConfidenceLevel, Diagnosis

        mock_result = AIAnalysisResult(
            diagnosis=Diagnosis(
                root_cause="Test error",
                evidence=["Evidence"],
                suggested_fix="Fix it",
                confidence=ConfidenceLevel.MEDIUM,
                confidence_explanation="Medium confidence",
                raw_response="raw",
            ),
            input_tokens=100,
            output_tokens=50,
        )

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch(
            "heisenberg.cli.commands.analyze_unified_run", return_value=mock_result
        ) as mock_analyze:
            args = argparse.Namespace(
                report=sample_report_path,
                report_format="playwright",
                output_format="text",
                docker_services="",
                log_window=30,
                post_comment=False,
                ai_analysis=True,
                use_unified=True,
                provider="anthropic",
                model=None,
            )

            run_analyze(args)

            # Verify analyze_unified_run was called
            mock_analyze.assert_called_once()

    def test_use_unified_false_uses_regular_ai(self, sample_report_path: Path, capsys, monkeypatch):
        """Should use regular AI analysis when use_unified is False."""
        from heisenberg.core.analyzer import AIAnalysisResult
        from heisenberg.core.diagnosis import ConfidenceLevel, Diagnosis

        mock_result = AIAnalysisResult(
            diagnosis=Diagnosis(
                root_cause="Test error",
                evidence=["Evidence"],
                suggested_fix="Fix it",
                confidence=ConfidenceLevel.MEDIUM,
                confidence_explanation="Medium confidence",
                raw_response="raw",
            ),
            input_tokens=100,
            output_tokens=50,
        )

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch(
            "heisenberg.cli.commands.analyze_with_ai", return_value=mock_result
        ) as mock_analyze:
            args = argparse.Namespace(
                report=sample_report_path,
                report_format="playwright",
                output_format="text",
                docker_services="",
                log_window=30,
                post_comment=False,
                ai_analysis=True,
                use_unified=False,
                provider="anthropic",
                model=None,
                container_logs=None,
            )

            run_analyze(args)

            # Verify analyze_with_ai was called (not analyze_unified_run)
            mock_analyze.assert_called_once()


class TestCliContainerLogs:
    """Tests for container logs handling in CLI."""

    @pytest.fixture
    def sample_report_path(self) -> Path:
        """Path to sample Playwright report fixture."""
        return Path(__file__).parent / "fixtures" / "playwright_report.json"

    def test_container_logs_from_file(self, sample_report_path: Path, tmp_path, capsys):
        """Should load container logs from file."""
        log_file = tmp_path / "container.log"
        log_file.write_text("2024-01-01 12:00:00 INFO Starting service\n")

        args = MagicMock()
        args.container_logs = log_file

        result_mock = MagicMock()
        result_mock.container_logs = None

        logs = _load_container_logs(args, result_mock)

        assert "logs_file" in logs
        assert "Starting service" in logs["logs_file"]

    def test_container_logs_from_result(self, sample_report_path: Path):
        """Should use logs from result when no file provided."""
        args = MagicMock()
        args.container_logs = None

        mock_logs = MagicMock()
        mock_logs.entries = ["log1", "log2"]

        result_mock = MagicMock()
        result_mock.container_logs = {"api": mock_logs}

        logs = _load_container_logs(args, result_mock)

        assert logs == {"api": mock_logs}
