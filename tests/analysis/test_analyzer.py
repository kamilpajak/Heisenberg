"""Tests for Analyzer - main orchestration module - TDD."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from heisenberg.analysis import AnalysisResult, Analyzer, run_analysis


class TestAnalyzer:
    """Test suite for Analyzer class."""

    def test_analyzer_initializes_with_report_path(self, sample_report_path: Path):
        """Analyzer should accept report path."""
        # When
        analyzer = Analyzer(report_path=sample_report_path)

        # Then
        assert analyzer.report_path == sample_report_path

    def test_analyzer_accepts_docker_services(self, sample_report_path: Path):
        """Analyzer should accept docker services config."""
        # When
        analyzer = Analyzer(
            report_path=sample_report_path,
            docker_services="api,db,redis",
        )

        # Then
        assert analyzer.docker_services == "api,db,redis"

    def test_analyzer_accepts_log_window(self, sample_report_path: Path):
        """Analyzer should accept log window config."""
        # When
        analyzer = Analyzer(
            report_path=sample_report_path,
            log_window_seconds=60,
        )

        # Then
        assert analyzer.log_window_seconds == 60

    def test_analyze_returns_result(self, sample_report_path: Path):
        """Analyzer.analyze() should return AnalysisResult."""
        # Given
        analyzer = Analyzer(report_path=sample_report_path)

        # When
        result = analyzer.analyze()

        # Then
        assert isinstance(result, AnalysisResult)

    def test_analyze_parses_playwright_report(self, sample_report_path: Path):
        """Analyzer should parse Playwright report."""
        # Given
        analyzer = Analyzer(report_path=sample_report_path)

        # When
        result = analyzer.analyze()

        # Then
        assert result.report is not None
        assert result.report.total_failed == 2

    @patch("heisenberg.analysis.pipeline.DockerLogsCollector")
    def test_analyze_collects_docker_logs_when_configured(
        self, mock_collector_class: MagicMock, sample_report_path: Path
    ):
        """Analyzer should collect Docker logs when services are configured."""
        # Given
        mock_collector = MagicMock()
        mock_collector.collect_all.return_value = {}
        mock_collector_class.from_string.return_value = mock_collector

        analyzer = Analyzer(
            report_path=sample_report_path,
            docker_services="api,db",
        )

        # When
        analyzer.analyze()

        # Then
        mock_collector_class.from_string.assert_called_with("api,db")
        mock_collector.collect_all.assert_called()

    def test_analyze_skips_docker_logs_when_not_configured(self, sample_report_path: Path):
        """Analyzer should skip Docker logs when no services configured."""
        # Given
        analyzer = Analyzer(report_path=sample_report_path, docker_services="")

        # When
        result = analyzer.analyze()

        # Then
        assert result.container_logs == {}


class TestAnalysisResult:
    """Test suite for AnalysisResult data model."""

    def test_result_has_report(self, sample_report_path: Path):
        """Result should contain parsed report."""
        # Given
        analyzer = Analyzer(report_path=sample_report_path)

        # When
        result = analyzer.analyze()

        # Then
        assert result.report.has_failures

    def test_result_has_container_logs(self, sample_report_path: Path):
        """Result should contain container logs dict."""
        # Given
        analyzer = Analyzer(report_path=sample_report_path)

        # When
        result = analyzer.analyze()

        # Then
        assert isinstance(result.container_logs, dict)

    def test_result_to_markdown(self, sample_report_path: Path):
        """Result should format as markdown."""
        # Given
        analyzer = Analyzer(report_path=sample_report_path)
        result = analyzer.analyze()

        # When
        md = result.to_markdown()

        # Then
        assert "## Heisenberg" in md
        assert "failed" in md.lower()

    def test_result_has_failures_property(self, sample_report_path: Path):
        """Result should expose has_failures from report."""
        # Given
        analyzer = Analyzer(report_path=sample_report_path)

        # When
        result = analyzer.analyze()

        # Then
        assert result.has_failures

    def test_result_summary_property(self, sample_report_path: Path):
        """Result should provide summary string."""
        # Given
        analyzer = Analyzer(report_path=sample_report_path)

        # When
        result = analyzer.analyze()

        # Then
        assert "2" in result.summary  # 2 failed tests
        assert "failed" in result.summary.lower()


class TestRunAnalysisHelper:
    """Test suite for run_analysis convenience function."""

    def test_run_analysis_creates_analyzer(self, sample_report_path: Path):
        """Should create analyzer with provided config."""
        # When
        result = run_analysis(
            report_path=sample_report_path,
            docker_services="",
            log_window_seconds=30,
        )

        # Then
        assert isinstance(result, AnalysisResult)

    def test_run_analysis_returns_result_with_failures(self, sample_report_path: Path):
        """Should return result indicating failures."""
        # When
        result = run_analysis(report_path=sample_report_path)

        # Then
        assert result.has_failures


class TestAnalyzerWithDockerLogs:
    """Test analyzer with Docker logs integration."""

    @patch("heisenberg.analysis.pipeline.DockerLogsCollector")
    def test_analyzer_filters_logs_by_failure_timestamp(
        self, mock_collector_class: MagicMock, sample_report_path: Path
    ):
        """Analyzer should filter logs around failure timestamps."""
        # Given
        from heisenberg.integrations.docker import ContainerLogs, LogEntry

        mock_logs = ContainerLogs(
            container_name="api",
            entries=[
                LogEntry(
                    datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                    "Log entry",
                    "stdout",
                )
            ],
        )
        mock_filtered = ContainerLogs(container_name="api", entries=[])
        mock_logs.filter_by_time_window = MagicMock(return_value=mock_filtered)

        mock_collector = MagicMock()
        mock_collector.collect_all.return_value = {"api": mock_logs}
        mock_collector_class.from_string.return_value = mock_collector

        analyzer = Analyzer(
            report_path=sample_report_path,
            docker_services="api",
            log_window_seconds=60,
        )

        # When
        analyzer.analyze()

        # Then
        # Should have called filter for each failed test
        assert mock_logs.filter_by_time_window.called


# sample_report_path fixture is provided by conftest.py
