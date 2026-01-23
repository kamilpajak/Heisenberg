"""Docker logs collector for correlating test failures with backend logs."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


@dataclass
class LogEntry:
    """Single log entry from a container."""

    timestamp: datetime
    message: str
    stream: str = "stdout"

    def __str__(self) -> str:
        """Format log entry as string."""
        time_str = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        stream_marker = "[ERR]" if self.stream == "stderr" else "[OUT]"
        return f"{time_str} {stream_marker} {self.message}"


@dataclass
class ContainerLogs:
    """Collection of log entries from a container."""

    container_name: str
    entries: list[LogEntry] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if any entries are from stderr."""
        return any(e.stream == "stderr" for e in self.entries)

    def filter_by_time_window(self, center: datetime, window_seconds: int = 30) -> ContainerLogs:
        """Filter entries within time window around center timestamp."""
        delta = timedelta(seconds=window_seconds)
        start = center - delta
        end = center + delta

        filtered = [e for e in self.entries if start <= e.timestamp <= end]

        return ContainerLogs(container_name=self.container_name, entries=filtered)

    def to_markdown(self) -> str:
        """Format logs as markdown."""
        lines = [
            f"#### Container: `{self.container_name}`",
            "",
        ]

        if not self.entries:
            lines.append("*No logs available*")
        else:
            lines.append("```")
            for entry in self.entries:
                lines.append(str(entry))
            lines.append("```")

        return "\n".join(lines)


class DockerLogsCollector:
    """Collects logs from Docker containers."""

    def __init__(self, services: list[str] | None = None):
        """
        Initialize collector with service names.

        Args:
            services: List of Docker container/service names to collect logs from.
        """
        self.services = services or []

    @classmethod
    def from_string(cls, services_string: str) -> DockerLogsCollector:
        """
        Create collector from comma-separated service string.

        Args:
            services_string: Comma-separated list of service names.

        Returns:
            DockerLogsCollector instance.
        """
        if not services_string or not services_string.strip():
            return cls(services=[])

        services = [s.strip() for s in services_string.split(",") if s.strip()]
        return cls(services=services)

    def collect_all(self) -> dict[str, ContainerLogs]:
        """
        Collect logs from all configured services.

        Returns:
            Dictionary mapping service name to ContainerLogs.
        """
        results: dict[str, ContainerLogs] = {}

        for service in self.services:
            try:
                logs = self._collect_from_container(service)
                if logs.entries:
                    results[service] = logs
            except Exception:
                # Skip containers that fail (not found, docker not available, etc.)
                continue

        return results

    def _collect_from_container(self, container_name: str) -> ContainerLogs:
        """Collect logs from a single container."""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "logs",
                    "--timestamps",
                    "--tail",
                    "1000",  # Limit to last 1000 lines
                    container_name,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            # Docker not installed
            raise
        except subprocess.TimeoutExpired:
            return ContainerLogs(container_name=container_name, entries=[])

        entries: list[LogEntry] = []

        # Parse stdout
        if result.stdout:
            entries.extend(self._parse_log_lines(result.stdout, "stdout"))

        # Parse stderr
        if result.stderr and result.returncode == 0:
            # Only include stderr as logs if command succeeded
            # (otherwise it's an error message from docker itself)
            entries.extend(self._parse_log_lines(result.stderr, "stderr"))

        # Sort by timestamp
        entries.sort(key=lambda e: e.timestamp)

        return ContainerLogs(container_name=container_name, entries=entries)

    def _parse_log_lines(self, output: str, stream: str) -> list[LogEntry]:
        """Parse docker logs output into LogEntry objects."""
        entries: list[LogEntry] = []

        for line in output.strip().split("\n"):
            if not line:
                continue

            entry = self._parse_log_line(line, stream)
            if entry:
                entries.append(entry)

        return entries

    def _parse_log_line(self, line: str, stream: str) -> LogEntry | None:
        """Parse a single log line with timestamp."""
        # Docker logs format with --timestamps:
        # 2024-01-15T10:30:00.123456789Z Message content
        # or
        # 2024-01-15T10:30:00.123456789+00:00 Message content

        if len(line) < 30:  # Too short to have timestamp
            return None

        # Try to find the timestamp (ISO format)
        space_idx = line.find(" ")
        if space_idx == -1:
            return None

        timestamp_str = line[:space_idx]
        message = line[space_idx + 1 :]

        try:
            # Handle various timestamp formats
            timestamp_str = timestamp_str.rstrip("Z")
            if "+" in timestamp_str:
                timestamp_str = timestamp_str.split("+")[0]

            # Truncate nanoseconds to microseconds (Python only supports microseconds)
            if "." in timestamp_str:
                parts = timestamp_str.split(".")
                if len(parts[1]) > 6:
                    parts[1] = parts[1][:6]
                timestamp_str = ".".join(parts)

            timestamp = datetime.fromisoformat(timestamp_str).replace(tzinfo=UTC)

            return LogEntry(timestamp=timestamp, message=message, stream=stream)
        except ValueError:
            # Couldn't parse timestamp, skip this line
            return None


def collect_logs_around_timestamp(
    services: str,
    timestamp: datetime,
    window_seconds: int = 30,
) -> dict[str, ContainerLogs]:
    """
    Convenience function to collect and filter logs around a timestamp.

    Args:
        services: Comma-separated list of service names.
        timestamp: Center timestamp to filter around.
        window_seconds: Time window in seconds (default: 30).

    Returns:
        Dictionary mapping service name to filtered ContainerLogs.
    """
    collector = DockerLogsCollector.from_string(services)
    all_logs = collector.collect_all()

    filtered: dict[str, ContainerLogs] = {}
    for name, logs in all_logs.items():
        filtered[name] = logs.filter_by_time_window(timestamp, window_seconds)

    return filtered
