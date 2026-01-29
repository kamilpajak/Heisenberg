"""Tests for Docker logs collector - TDD Red-Green-Refactor."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from heisenberg.integrations.docker import (
    ContainerLogs,
    DockerLogsCollector,
    LogEntry,
    collect_logs_around_timestamp,
)


class TestLogEntry:
    """Test suite for LogEntry data model."""

    def test_log_entry_has_required_fields(self):
        """LogEntry should have timestamp, message, and stream fields."""
        # When
        entry = LogEntry(
            timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            message="Test log message",
            stream="stdout",
        )

        # Then
        assert entry.timestamp.year == 2024
        assert entry.message == "Test log message"
        assert entry.stream == "stdout"

    def test_log_entry_formats_as_string(self):
        """LogEntry should format nicely as string."""
        # Given
        entry = LogEntry(
            timestamp=datetime(2024, 1, 15, 10, 30, 5, tzinfo=UTC),
            message="Application started",
            stream="stdout",
        )

        # When
        result = str(entry)

        # Then
        assert "10:30:05" in result
        assert "Application started" in result


class TestContainerLogs:
    """Test suite for ContainerLogs data model."""

    def test_container_logs_stores_entries(self):
        """ContainerLogs should store list of log entries."""
        # Given
        entries = [
            LogEntry(datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC), "msg1", "stdout"),
            LogEntry(datetime(2024, 1, 15, 10, 30, 1, tzinfo=UTC), "msg2", "stderr"),
        ]

        # When
        logs = ContainerLogs(container_name="api-service", entries=entries)

        # Then
        assert logs.container_name == "api-service"
        assert len(logs.entries) == 2

    def test_container_logs_filters_by_time_window(self):
        """ContainerLogs should filter entries within time window."""
        # Given
        center_time = datetime(2024, 1, 15, 10, 30, 30, tzinfo=UTC)
        entries = [
            LogEntry(datetime(2024, 1, 15, 10, 29, 50, tzinfo=UTC), "before window", "stdout"),
            LogEntry(datetime(2024, 1, 15, 10, 30, 10, tzinfo=UTC), "in window 1", "stdout"),
            LogEntry(datetime(2024, 1, 15, 10, 30, 40, tzinfo=UTC), "in window 2", "stdout"),
            LogEntry(datetime(2024, 1, 15, 10, 31, 10, tzinfo=UTC), "after window", "stdout"),
        ]
        logs = ContainerLogs(container_name="api", entries=entries)

        # When
        filtered = logs.filter_by_time_window(center_time, window_seconds=30)

        # Then
        assert len(filtered.entries) == 2
        assert all("in window" in e.message for e in filtered.entries)

    def test_container_logs_has_errors_property(self):
        """ContainerLogs should detect stderr entries."""
        # Given
        entries = [
            LogEntry(datetime.now(UTC), "info message", "stdout"),
            LogEntry(datetime.now(UTC), "error message", "stderr"),
        ]
        logs = ContainerLogs(container_name="api", entries=entries)

        # Then
        assert logs.has_errors

    def test_container_logs_to_markdown(self):
        """ContainerLogs should format as markdown."""
        # Given
        entries = [
            LogEntry(datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC), "Starting server", "stdout"),
            LogEntry(datetime(2024, 1, 15, 10, 30, 1, tzinfo=UTC), "Error occurred", "stderr"),
        ]
        logs = ContainerLogs(container_name="api-service", entries=entries)

        # When
        md = logs.to_markdown()

        # Then
        assert "api-service" in md
        assert "Starting server" in md
        assert "Error occurred" in md
        assert "```" in md  # Code block


class TestDockerLogsCollector:
    """Test suite for DockerLogsCollector."""

    def test_collector_initializes_with_service_names(self):
        """Collector should accept list of service names."""
        # When
        collector = DockerLogsCollector(services=["api", "db", "redis"])

        # Then
        assert collector.services == ["api", "db", "redis"]

    def test_collector_parses_service_string(self):
        """Collector should parse comma-separated service string."""
        # When
        collector = DockerLogsCollector.from_string("api, db, redis")

        # Then
        assert collector.services == ["api", "db", "redis"]

    def test_collector_handles_empty_string(self):
        """Collector should handle empty service string."""
        # When
        collector = DockerLogsCollector.from_string("")

        # Then
        assert collector.services == []

    @patch("heisenberg.integrations.docker.subprocess.run")
    def test_collector_calls_docker_logs_command(self, mock_run: MagicMock):
        """Collector should call docker logs for each service."""
        # Given
        mock_run.return_value = MagicMock(
            stdout="2024-01-15T10:30:00.000Z stdout Test message\n",
            stderr="",
            returncode=0,
        )
        collector = DockerLogsCollector(services=["api-service"])

        # When
        collector.collect_all()

        # Then
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args
        assert "logs" in call_args
        assert "api-service" in call_args

    @patch("heisenberg.integrations.docker.subprocess.run")
    def test_collector_parses_docker_log_output(self, mock_run: MagicMock):
        """Collector should parse docker logs output into LogEntry objects."""
        # Given
        mock_run.return_value = MagicMock(
            stdout="2024-01-15T10:30:00.123456Z Test message line 1\n"
            "2024-01-15T10:30:01.456789Z Test message line 2\n",
            stderr="",
            returncode=0,
        )
        collector = DockerLogsCollector(services=["api"])

        # When
        results = collector.collect_all()

        # Then
        assert "api" in results
        assert len(results["api"].entries) == 2
        assert results["api"].entries[0].message == "Test message line 1"

    @patch("heisenberg.integrations.docker.subprocess.run")
    def test_collector_handles_docker_not_available(self, mock_run: MagicMock):
        """Collector should handle docker command not available."""
        # Given
        mock_run.side_effect = FileNotFoundError("docker not found")
        collector = DockerLogsCollector(services=["api"])

        # When
        results = collector.collect_all()

        # Then
        assert results == {}

    @patch("heisenberg.integrations.docker.subprocess.run")
    def test_collector_handles_container_not_found(self, mock_run: MagicMock):
        """Collector should handle non-existent container gracefully."""
        # Given
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="Error: No such container: nonexistent",
            returncode=1,
        )
        collector = DockerLogsCollector(services=["nonexistent"])

        # When
        results = collector.collect_all()

        # Then
        assert "nonexistent" not in results or results["nonexistent"].entries == []

    @patch("heisenberg.integrations.docker.subprocess.run")
    def test_collector_uses_timestamps_flag(self, mock_run: MagicMock):
        """Collector should use --timestamps flag for parsing."""
        # Given
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        collector = DockerLogsCollector(services=["api"])

        # When
        collector.collect_all()

        # Then
        call_args = mock_run.call_args[0][0]
        assert "--timestamps" in call_args or "-t" in call_args


class TestCollectLogsAroundTimestamp:
    """Test suite for collect_logs_around_timestamp helper."""

    @patch("heisenberg.integrations.docker.DockerLogsCollector")
    def test_collect_logs_creates_collector(self, mock_collector_class: MagicMock):
        """Should create collector with provided services."""
        # Given
        mock_collector = MagicMock()
        mock_collector.collect_all.return_value = {}
        mock_collector_class.from_string.return_value = mock_collector

        # When
        collect_logs_around_timestamp(
            services="api,db",
            timestamp=datetime.now(UTC),
            window_seconds=30,
        )

        # Then
        mock_collector_class.from_string.assert_called_with("api,db")

    @patch("heisenberg.integrations.docker.DockerLogsCollector")
    def test_collect_logs_filters_by_window(self, mock_collector_class: MagicMock):
        """Should filter logs by time window."""
        # Given
        center_time = datetime(2024, 1, 15, 10, 30, 30, tzinfo=UTC)
        mock_logs = MagicMock()
        mock_logs.filter_by_time_window.return_value = mock_logs
        mock_collector = MagicMock()
        mock_collector.collect_all.return_value = {"api": mock_logs}
        mock_collector_class.from_string.return_value = mock_collector

        # When
        collect_logs_around_timestamp(
            services="api",
            timestamp=center_time,
            window_seconds=60,
        )

        # Then
        mock_logs.filter_by_time_window.assert_called_with(center_time, 60)
