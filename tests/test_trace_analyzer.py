"""Tests for Playwright trace analysis.

Playwright traces contain rich debugging data:
- Console logs (JS errors, warnings)
- Network requests/responses
- Action timeline (clicks, navigations, etc.)
- DOM snapshots
"""

from __future__ import annotations

import io
import json
import zipfile

from heisenberg.trace_analyzer import (
    ActionEntry,
    ConsoleEntry,
    NetworkEntry,
    TraceAnalyzer,
    TraceContext,
    extract_trace_from_artifact,
    format_trace_for_prompt,
)


class TestTraceExtraction:
    """Tests for extracting traces from Playwright artifacts."""

    def test_extract_trace_from_artifact_zip(self):
        """Extract trace.zip files from artifact."""
        # Create a mock artifact with trace files
        artifact_buffer = io.BytesIO()
        with zipfile.ZipFile(artifact_buffer, "w") as outer_zip:
            # Create inner trace.zip
            trace_buffer = io.BytesIO()
            with zipfile.ZipFile(trace_buffer, "w") as trace_zip:
                trace_zip.writestr("trace.trace", b"binary-trace-data")
            outer_zip.writestr(
                "test-results/login-test/trace.zip",
                trace_buffer.getvalue(),
            )

        traces = extract_trace_from_artifact(artifact_buffer.getvalue())

        assert len(traces) == 1
        assert "login" in traces[0].test_name.lower()

    def test_extract_multiple_traces(self):
        """Extract multiple trace files from artifact."""
        artifact_buffer = io.BytesIO()
        with zipfile.ZipFile(artifact_buffer, "w") as outer_zip:
            for test_name in ["login-test", "checkout-test", "profile-test"]:
                trace_buffer = io.BytesIO()
                with zipfile.ZipFile(trace_buffer, "w") as trace_zip:
                    trace_zip.writestr("trace.trace", b"data")
                outer_zip.writestr(
                    f"test-results/{test_name}/trace.zip",
                    trace_buffer.getvalue(),
                )

        traces = extract_trace_from_artifact(artifact_buffer.getvalue())

        assert len(traces) == 3

    def test_extract_no_traces_returns_empty(self):
        """Return empty list when no traces in artifact."""
        artifact_buffer = io.BytesIO()
        with zipfile.ZipFile(artifact_buffer, "w") as zf:
            zf.writestr("report.json", b"{}")
            zf.writestr("screenshot.png", b"png-data")

        traces = extract_trace_from_artifact(artifact_buffer.getvalue())

        assert len(traces) == 0


class TestConsoleEntry:
    """Tests for console log entries."""

    def test_console_entry_properties(self):
        """ConsoleEntry should have required properties."""
        entry = ConsoleEntry(
            level="error",
            message="Uncaught TypeError: Cannot read property 'x' of undefined",
            timestamp=1234567890,
            location="app.js:42",
        )

        assert entry.level == "error"
        assert "TypeError" in entry.message
        assert entry.timestamp == 1234567890
        assert entry.location == "app.js:42"

    def test_console_entry_format(self):
        """Format console entry for display."""
        entry = ConsoleEntry(
            level="error",
            message="Failed to load resource",
            timestamp=1234567890,
            location=None,
        )

        formatted = entry.format()

        assert "[ERROR]" in formatted
        assert "Failed to load resource" in formatted


class TestNetworkEntry:
    """Tests for network request entries."""

    def test_network_entry_properties(self):
        """NetworkEntry should have required properties."""
        entry = NetworkEntry(
            method="POST",
            url="https://api.example.com/login",
            status=401,
            duration_ms=150,
            failure_reason=None,
        )

        assert entry.method == "POST"
        assert entry.url == "https://api.example.com/login"
        assert entry.status == 401
        assert entry.duration_ms == 150

    def test_network_entry_is_failure(self):
        """Detect failed network requests."""
        success = NetworkEntry("GET", "https://api.com/data", 200, 100, None)
        client_error = NetworkEntry("POST", "https://api.com/login", 401, 50, None)
        server_error = NetworkEntry("GET", "https://api.com/data", 500, 200, None)
        network_failure = NetworkEntry(
            "GET", "https://api.com/data", 0, 0, "net::ERR_CONNECTION_REFUSED"
        )

        assert not success.is_failure
        assert client_error.is_failure
        assert server_error.is_failure
        assert network_failure.is_failure

    def test_network_entry_format(self):
        """Format network entry for display."""
        entry = NetworkEntry(
            method="POST",
            url="https://api.example.com/auth/login",
            status=500,
            duration_ms=1234,
            failure_reason=None,
        )

        formatted = entry.format()

        assert "POST" in formatted
        assert "500" in formatted
        assert "login" in formatted


class TestActionEntry:
    """Tests for action timeline entries."""

    def test_action_entry_properties(self):
        """ActionEntry should have required properties."""
        entry = ActionEntry(
            action="click",
            selector="button[data-testid='submit']",
            timestamp=1234567890,
            duration_ms=50,
            error=None,
        )

        assert entry.action == "click"
        assert "submit" in entry.selector
        assert entry.duration_ms == 50
        assert entry.error is None

    def test_action_entry_with_error(self):
        """ActionEntry can have error information."""
        entry = ActionEntry(
            action="click",
            selector="button.submit",
            timestamp=1234567890,
            duration_ms=30000,
            error="Timeout 30000ms exceeded",
        )

        assert entry.error is not None
        assert "Timeout" in entry.error

    def test_action_entry_format(self):
        """Format action entry for display."""
        entry = ActionEntry(
            action="fill",
            selector="input[name='email']",
            timestamp=1234567890,
            duration_ms=25,
            error=None,
        )

        formatted = entry.format()

        assert "fill" in formatted
        assert "email" in formatted


class TestTraceContext:
    """Tests for TraceContext dataclass."""

    def test_trace_context_properties(self):
        """TraceContext should have required properties."""
        ctx = TraceContext(
            test_name="login-test",
            file_path="tests/auth.spec.ts",
            console_logs=[],
            network_requests=[],
            actions=[],
        )

        assert ctx.test_name == "login-test"
        assert ctx.file_path == "tests/auth.spec.ts"
        assert ctx.console_logs == []
        assert ctx.network_requests == []
        assert ctx.actions == []

    def test_trace_context_filter_errors(self):
        """Filter only error-level console logs."""
        ctx = TraceContext(
            test_name="test",
            file_path="test.ts",
            console_logs=[
                ConsoleEntry("info", "App loaded", 1, None),
                ConsoleEntry("error", "Failed to fetch", 2, None),
                ConsoleEntry("warning", "Deprecated API", 3, None),
                ConsoleEntry("error", "Uncaught exception", 4, None),
            ],
            network_requests=[],
            actions=[],
        )

        errors = ctx.get_console_errors()

        assert len(errors) == 2
        assert all(e.level == "error" for e in errors)

    def test_trace_context_filter_failed_requests(self):
        """Filter only failed network requests."""
        ctx = TraceContext(
            test_name="test",
            file_path="test.ts",
            console_logs=[],
            network_requests=[
                NetworkEntry("GET", "https://api.com/data", 200, 100, None),
                NetworkEntry("POST", "https://api.com/login", 401, 50, None),
                NetworkEntry("GET", "https://api.com/config", 200, 30, None),
                NetworkEntry("GET", "https://api.com/fail", 500, 200, None),
            ],
            actions=[],
        )

        failures = ctx.get_failed_requests()

        assert len(failures) == 2
        assert all(r.is_failure for r in failures)

    def test_trace_context_format_for_prompt(self):
        """Format trace context for AI prompt."""
        ctx = TraceContext(
            test_name="login-test",
            file_path="auth.spec.ts",
            console_logs=[
                ConsoleEntry("error", "Auth failed: invalid token", 1, "auth.js:50"),
            ],
            network_requests=[
                NetworkEntry("POST", "https://api.com/auth", 401, 100, None),
            ],
            actions=[
                ActionEntry("click", "button.login", 1, 50, None),
            ],
        )

        formatted = ctx.format_for_prompt()

        assert "login-test" in formatted
        assert "Auth failed" in formatted or "401" in formatted


class TestTraceAnalyzer:
    """Tests for analyzing Playwright traces."""

    def test_analyzer_parses_trace_events(self):
        """Analyzer should parse trace event data."""
        # Create a minimal trace with events
        trace_data = _create_mock_trace_zip(
            console_events=[
                {"type": "console", "messageType": "error", "text": "Test error", "time": 1000},
            ],
            network_events=[
                {
                    "type": "resource",
                    "method": "GET",
                    "url": "https://api.test.com/data",
                    "status": 500,
                    "timing": {"responseEnd": 100},
                },
            ],
            action_events=[
                {
                    "type": "action",
                    "action": "click",
                    "selector": "button",
                    "time": 500,
                    "duration": 50,
                },
            ],
        )

        analyzer = TraceAnalyzer()
        ctx = analyzer.analyze(trace_data, test_name="test", file_path="test.ts")

        assert len(ctx.console_logs) >= 1
        assert len(ctx.network_requests) >= 1
        assert len(ctx.actions) >= 1

    def test_analyzer_handles_empty_trace(self):
        """Handle trace with no relevant events."""
        trace_data = _create_mock_trace_zip()

        analyzer = TraceAnalyzer()
        ctx = analyzer.analyze(trace_data, test_name="test", file_path="test.ts")

        assert ctx.console_logs == []
        assert ctx.network_requests == []
        assert ctx.actions == []

    def test_analyzer_handles_corrupt_trace(self):
        """Handle corrupt or invalid trace data gracefully."""
        analyzer = TraceAnalyzer()
        ctx = analyzer.analyze(b"not-a-zip", test_name="test", file_path="test.ts")

        assert ctx.test_name == "test"
        assert ctx.console_logs == []

    def test_analyzer_limits_entries(self):
        """Limit number of entries to prevent prompt bloat."""
        # Create trace with many events
        trace_data = _create_mock_trace_zip(
            console_events=[
                {"type": "console", "messageType": "info", "text": f"Log {i}", "time": i}
                for i in range(100)
            ],
        )

        analyzer = TraceAnalyzer(max_console_entries=10)
        ctx = analyzer.analyze(trace_data, test_name="test", file_path="test.ts")

        assert len(ctx.console_logs) <= 10


class TestTracePromptIntegration:
    """Tests for integrating traces into analysis prompts."""

    def test_format_traces_for_prompt(self):
        """Format multiple trace contexts for AI prompt."""
        traces = [
            TraceContext(
                "login-test",
                "auth.spec.ts",
                console_logs=[ConsoleEntry("error", "Auth error", 1, None)],
                network_requests=[NetworkEntry("POST", "https://api.com/auth", 401, 100, None)],
                actions=[],
            ),
            TraceContext(
                "checkout-test",
                "cart.spec.ts",
                console_logs=[],
                network_requests=[NetworkEntry("GET", "https://api.com/cart", 500, 200, None)],
                actions=[],
            ),
        ]

        formatted = format_trace_for_prompt(traces)

        assert "### Trace Analysis:" in formatted
        assert "login-test" in formatted
        assert "checkout-test" in formatted

    def test_format_empty_traces(self):
        """Return empty string when no traces."""
        formatted = format_trace_for_prompt([])

        assert formatted == ""

    def test_format_trace_with_no_issues(self):
        """Handle trace with no errors or failures."""
        traces = [
            TraceContext(
                "success-test",
                "test.ts",
                console_logs=[ConsoleEntry("info", "All good", 1, None)],
                network_requests=[NetworkEntry("GET", "https://api.com/data", 200, 50, None)],
                actions=[ActionEntry("click", "button", 1, 10, None)],
            ),
        ]

        formatted = format_trace_for_prompt(traces)

        # Should still include the trace, just without error highlighting
        assert "success-test" in formatted


# Helper functions for creating mock trace data


def _create_mock_trace_zip(
    console_events: list[dict] | None = None,
    network_events: list[dict] | None = None,
    action_events: list[dict] | None = None,
) -> bytes:
    """Create a mock Playwright trace ZIP for testing."""
    events = []

    if console_events:
        events.extend(console_events)
    if network_events:
        events.extend(network_events)
    if action_events:
        events.extend(action_events)

    # Create trace.trace file with NDJSON events
    trace_content = "\n".join(json.dumps(e) for e in events)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("trace.trace", trace_content.encode())

    return buffer.getvalue()
