"""Playwright trace analysis for test failure diagnosis.

Playwright traces contain rich debugging data:
- Console logs (JS errors, warnings)
- Network requests/responses
- Action timeline (clicks, navigations, etc.)
- DOM snapshots

This module extracts and formats this data for AI analysis.
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from dataclasses import dataclass, field
from typing import TextIO

from heisenberg.artifact_utils import extract_spec_file_from_path, extract_test_name_from_path

# Default limits for trace entries
DEFAULT_MAX_CONSOLE_ENTRIES = 20
DEFAULT_MAX_NETWORK_ENTRIES = 20
DEFAULT_MAX_ACTION_ENTRIES = 20


@dataclass
class ConsoleEntry:
    """A console log entry from the trace."""

    level: str  # error, warning, info, log, debug
    message: str
    timestamp: int
    location: str | None

    def format(self) -> str:
        """Format entry for display."""
        level_str = f"[{self.level.upper()}]"
        location_str = f" ({self.location})" if self.location else ""
        return f"{level_str} {self.message}{location_str}"


@dataclass
class NetworkEntry:
    """A network request entry from the trace."""

    method: str
    url: str
    status: int
    duration_ms: int
    failure_reason: str | None

    @property
    def is_failure(self) -> bool:
        """Check if request failed (4xx, 5xx, or network error)."""
        if self.failure_reason:
            return True
        if self.status >= 400:
            return True
        if self.status == 0:  # Network error, no response
            return True
        return False

    def format(self) -> str:
        """Format entry for display."""
        status_str = str(self.status) if self.status else "ERR"
        # Truncate long URLs
        url = self.url
        if len(url) > 80:
            url = url[:77] + "..."
        result = f"{self.method} {status_str} {url}"
        if self.failure_reason:
            result += f" ({self.failure_reason})"
        return result


@dataclass
class ActionEntry:
    """An action entry from the trace timeline."""

    action: str  # click, fill, navigate, etc.
    selector: str
    timestamp: int
    duration_ms: int
    error: str | None

    def format(self) -> str:
        """Format entry for display."""
        # Truncate long selectors
        selector = self.selector
        if len(selector) > 60:
            selector = selector[:57] + "..."
        result = f"{self.action}: {selector}"
        if self.error:
            result += f" [FAILED: {self.error}]"
        return result


@dataclass
class TraceContext:
    """Context extracted from a Playwright trace."""

    test_name: str
    file_path: str
    console_logs: list[ConsoleEntry] = field(default_factory=list)
    network_requests: list[NetworkEntry] = field(default_factory=list)
    actions: list[ActionEntry] = field(default_factory=list)

    def get_console_errors(self) -> list[ConsoleEntry]:
        """Get only error-level console logs."""
        return [e for e in self.console_logs if e.level == "error"]

    def get_failed_requests(self) -> list[NetworkEntry]:
        """Get only failed network requests."""
        return [r for r in self.network_requests if r.is_failure]

    def format_for_prompt(self) -> str:
        """Format trace context for AI prompt."""
        lines = [f"**Test: {self.test_name}** ({self.file_path})"]

        # Console errors
        errors = self.get_console_errors()
        if errors:
            lines.append("\n**Console Errors:**")
            for entry in errors[:5]:  # Limit to 5
                lines.append(f"  - {entry.format()}")

        # Failed network requests
        failures = self.get_failed_requests()
        if failures:
            lines.append("\n**Failed Requests:**")
            for entry in failures[:5]:  # Limit to 5
                lines.append(f"  - {entry.format()}")

        # Recent actions (last 5 before failure)
        if self.actions:
            lines.append("\n**Recent Actions:**")
            for entry in self.actions[-5:]:
                lines.append(f"  - {entry.format()}")

        if len(lines) == 1:
            lines.append("*No significant issues found in trace*")

        return "\n".join(lines)


def extract_trace_from_artifact(artifact_data: bytes) -> list[TraceContext]:
    """Extract trace.zip files from Playwright artifact.

    Args:
        artifact_data: Raw bytes of the artifact ZIP file.

    Returns:
        List of TraceContext objects (one per trace file found).
    """
    traces = []

    try:
        with zipfile.ZipFile(io.BytesIO(artifact_data), "r") as outer_zip:
            for file_info in outer_zip.filelist:
                name = file_info.filename.lower()

                # Look for trace.zip files
                if not name.endswith("trace.zip"):
                    continue

                # Extract test name from path
                path_parts = file_info.filename.split("/")
                test_name = extract_test_name_from_path(path_parts, file_suffix="trace.zip")
                file_path = extract_spec_file_from_path(path_parts)

                # Create a placeholder context (actual parsing happens in TraceAnalyzer)
                traces.append(
                    TraceContext(
                        test_name=test_name,
                        file_path=file_path,
                        console_logs=[],
                        network_requests=[],
                        actions=[],
                    )
                )

    except zipfile.BadZipFile:
        pass

    return traces


class TraceAnalyzer:
    """Analyzes Playwright trace files."""

    def __init__(
        self,
        max_console_entries: int = DEFAULT_MAX_CONSOLE_ENTRIES,
        max_network_entries: int = DEFAULT_MAX_NETWORK_ENTRIES,
        max_action_entries: int = DEFAULT_MAX_ACTION_ENTRIES,
    ):
        """Initialize analyzer.

        Args:
            max_console_entries: Maximum console log entries to keep.
            max_network_entries: Maximum network request entries to keep.
            max_action_entries: Maximum action entries to keep.
        """
        self.max_console_entries = max_console_entries
        self.max_network_entries = max_network_entries
        self.max_action_entries = max_action_entries

    def analyze(
        self,
        trace_data: bytes,
        test_name: str,
        file_path: str,
    ) -> TraceContext:
        """Analyze a Playwright trace file.

        Args:
            trace_data: Raw bytes of trace.zip file.
            test_name: Name of the test.
            file_path: Path to the test file.

        Returns:
            TraceContext with extracted data.
        """
        console_logs: list[ConsoleEntry] = []
        network_requests: list[NetworkEntry] = []
        actions: list[ActionEntry] = []

        try:
            with zipfile.ZipFile(io.BytesIO(trace_data), "r") as zf:
                # Find and parse trace.trace file using streaming
                for name in zf.namelist():
                    if name.endswith("trace.trace") or name.endswith(".trace"):
                        with zf.open(name) as trace_file:
                            text_stream = io.TextIOWrapper(
                                trace_file, encoding="utf-8", errors="ignore"
                            )
                            self._parse_trace_events_stream(
                                text_stream,
                                console_logs,
                                network_requests,
                                actions,
                            )
                        break

        except zipfile.BadZipFile as e:
            print(f"Warning: Invalid trace ZIP file: {e}", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse trace JSON: {e}", file=sys.stderr)
        except OSError as e:
            print(f"Warning: IO error reading trace: {e}", file=sys.stderr)

        # Apply limits
        console_logs = console_logs[: self.max_console_entries]
        network_requests = network_requests[: self.max_network_entries]
        actions = actions[: self.max_action_entries]

        return TraceContext(
            test_name=test_name,
            file_path=file_path,
            console_logs=console_logs,
            network_requests=network_requests,
            actions=actions,
        )

    def _parse_trace_events_stream(
        self,
        trace_stream: TextIO,
        console_logs: list[ConsoleEntry],
        network_requests: list[NetworkEntry],
        actions: list[ActionEntry],
    ) -> None:
        """Parse NDJSON trace events from a stream.

        Uses streaming to avoid loading entire trace file into memory.
        """
        for line in trace_stream:
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
                self._process_event(event, console_logs, network_requests, actions)
            except json.JSONDecodeError:
                continue

    def _process_event(
        self,
        event: dict,
        console_logs: list[ConsoleEntry],
        network_requests: list[NetworkEntry],
        actions: list[ActionEntry],
    ) -> None:
        """Process a single trace event."""
        event_type = event.get("type", "")

        # Handle different Playwright trace event formats
        if event_type == "console":
            self._process_console_event(event, console_logs)
        elif event_type in ("stdout", "stderr"):
            self._process_stdout_event(event, console_logs)
        elif event_type == "error":
            self._process_error_event(event, console_logs)
        elif event_type == "resource":
            self._process_network_event(event, network_requests)
        elif event_type == "action":
            self._process_action_event(event, actions)
        elif event_type == "before":
            self._process_before_event(event, actions)

    def _process_console_event(
        self,
        event: dict,
        console_logs: list[ConsoleEntry],
    ) -> None:
        """Process a console event."""
        level = event.get("messageType", "log")
        message = event.get("text", "")
        timestamp = event.get("time", 0)
        location = event.get("location", None)

        if location and isinstance(location, dict):
            location = f"{location.get('file', '')}:{location.get('line', '')}"

        console_logs.append(
            ConsoleEntry(
                level=level,
                message=message,
                timestamp=timestamp,
                location=location,
            )
        )

    def _process_network_event(
        self,
        event: dict,
        network_requests: list[NetworkEntry],
    ) -> None:
        """Process a network/resource event."""
        method = event.get("method", "GET")
        url = event.get("url", "")
        status = event.get("status", 0)
        failure_reason = event.get("failure", None)

        # Calculate duration from timing
        timing = event.get("timing", {})
        duration_ms = int(timing.get("responseEnd", 0))

        network_requests.append(
            NetworkEntry(
                method=method,
                url=url,
                status=status,
                duration_ms=duration_ms,
                failure_reason=failure_reason,
            )
        )

    def _process_action_event(
        self,
        event: dict,
        actions: list[ActionEntry],
    ) -> None:
        """Process an action event."""
        action = event.get("action", "unknown")
        selector = event.get("selector", "")
        timestamp = event.get("time", 0)
        duration_ms = event.get("duration", 0)
        error = event.get("error", None)

        actions.append(
            ActionEntry(
                action=action,
                selector=selector,
                timestamp=timestamp,
                duration_ms=duration_ms,
                error=error,
            )
        )

    def _process_stdout_event(
        self,
        event: dict,
        console_logs: list[ConsoleEntry],
    ) -> None:
        """Process a stdout/stderr event from Playwright trace."""
        level = "info" if event.get("type") == "stdout" else "warning"
        message = event.get("text", "").strip()
        timestamp = int(event.get("timestamp", 0))

        if message:
            console_logs.append(
                ConsoleEntry(
                    level=level,
                    message=message,
                    timestamp=timestamp,
                    location=None,
                )
            )

    def _process_error_event(
        self,
        event: dict,
        console_logs: list[ConsoleEntry],
    ) -> None:
        """Process an error event from Playwright trace."""
        message = event.get("message", "")
        timestamp = int(event.get("timestamp", 0))

        if message:
            console_logs.append(
                ConsoleEntry(
                    level="error",
                    message=message,
                    timestamp=timestamp,
                    location=None,
                )
            )

    def _process_before_event(
        self,
        event: dict,
        actions: list[ActionEntry],
    ) -> None:
        """Process a 'before' action event from Playwright trace.

        Playwright traces use 'before'/'after' pairs for actions.
        We only process 'before' to capture the action start.
        """
        method = event.get("method", "")
        title = event.get("title", "")
        selector = event.get("params", {}).get("selector", "")
        timestamp = int(event.get("startTime", 0))

        # Skip test hooks, focus on actual page interactions
        if method in ("hook",):
            return

        # Use title or method as the action name
        action = title or method

        if action:
            actions.append(
                ActionEntry(
                    action=action,
                    selector=selector or "",
                    timestamp=timestamp,
                    duration_ms=0,  # Duration comes from 'after' event
                    error=None,
                )
            )


def format_trace_for_prompt(traces: list[TraceContext]) -> str:
    """Format trace contexts for inclusion in AI prompt.

    Args:
        traces: List of TraceContext objects.

    Returns:
        Formatted string for prompt, or empty string if no traces.
    """
    if not traces:
        return ""

    lines = ["### Trace Analysis:"]

    for trace in traces:
        lines.append("")
        lines.append(trace.format_for_prompt())

    return "\n".join(lines)
