"""Parser for Playwright JSON test reports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ErrorDetail:
    """Represents an error from a failed test."""

    message: str
    stack: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ErrorDetail:
        """Create TestError from Playwright error dict."""
        return cls(
            message=data.get("message", ""),
            stack=data.get("stack", ""),
        )


@dataclass
class FailedTest:
    """Represents a failed test with all relevant details."""

    title: str
    file: str
    suite: str
    project: str
    status: str
    duration_ms: int
    start_time: datetime | None
    errors: list[ErrorDetail] = field(default_factory=list)
    trace_path: str | None = None

    @property
    def full_name(self) -> str:
        """Return full test name combining suite and title."""
        return f"{self.suite} > {self.title}"

    @property
    def error_summary(self) -> str:
        """Return first error message as summary."""
        if not self.errors:
            return "No error details available"
        return self.errors[0].message


@dataclass
class PlaywrightReport:
    """Parsed Playwright test report."""

    total_passed: int
    total_failed: int
    total_skipped: int
    total_flaky: int
    failed_tests: list[FailedTest] = field(default_factory=list)

    @property
    def has_failures(self) -> bool:
        """Check if report contains any failures."""
        return len(self.failed_tests) > 0

    @property
    def summary(self) -> str:
        """Return human-readable summary of test results."""
        parts = []
        if self.total_passed:
            parts.append(f"{self.total_passed} passed")
        if self.total_failed:
            parts.append(f"{self.total_failed} failed")
        if self.total_skipped:
            parts.append(f"{self.total_skipped} skipped")
        if self.total_flaky:
            parts.append(f"{self.total_flaky} flaky")
        return ", ".join(parts) if parts else "No tests run"


def parse_playwright_report(report_path: Path) -> PlaywrightReport:
    """
    Parse a Playwright JSON report file.

    Args:
        report_path: Path to the Playwright JSON report file.

    Returns:
        PlaywrightReport with parsed test results.

    Raises:
        FileNotFoundError: If report file doesn't exist.
        ValueError: If report contains invalid JSON.
    """
    if not report_path.exists():
        raise FileNotFoundError(f"Report file not found: {report_path}")

    try:
        data = json.loads(report_path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in report file: {e}") from e

    # Extract stats
    stats = data.get("stats", {})
    total_passed = stats.get("expected", 0)
    total_failed = stats.get("unexpected", 0)
    total_skipped = stats.get("skipped", 0)
    total_flaky = stats.get("flaky", 0)

    # Extract failed tests
    failed_tests = _extract_failed_tests(data.get("suites", []))

    return PlaywrightReport(
        total_passed=total_passed,
        total_failed=total_failed,
        total_skipped=total_skipped,
        total_flaky=total_flaky,
        failed_tests=failed_tests,
    )


def _extract_failed_specs(
    specs: list[dict[str, Any]], file: str, suite_title: str
) -> list[FailedTest]:
    """Extract failed tests from a list of specs."""
    failed_tests = []
    for spec in specs:
        if not spec.get("ok", True):
            failed_test = _parse_failed_spec(spec, file, suite_title)
            if failed_test:
                failed_tests.append(failed_test)
    return failed_tests


def _extract_failed_tests(suites: list[dict[str, Any]], parent_file: str = "") -> list[FailedTest]:
    """Recursively extract failed tests from suites."""
    failed_tests = []

    for suite in suites:
        file = suite.get("file", parent_file)
        suite_title = suite.get("title", "")

        # Process specs in this suite
        failed_tests.extend(_extract_failed_specs(suite.get("specs", []), file, suite_title))

        # Recursively process nested suites
        nested_suites = suite.get("suites", [])
        failed_tests.extend(_extract_failed_tests(nested_suites, file))

    return failed_tests


def _parse_failed_spec(spec: dict[str, Any], file: str, suite_title: str) -> FailedTest | None:
    """Parse a failed spec into a FailedTest object."""
    tests = spec.get("tests", [])
    if not tests:
        return None

    # Get the first test (usually there's only one per spec)
    test = tests[0]
    results = test.get("results", [])
    if not results:
        return None

    # Get the last result (in case of retries)
    result = results[-1]

    # Parse errors
    errors = [ErrorDetail.from_dict(e) for e in result.get("errors", [])]

    # Find trace attachment
    trace_path = None
    for attachment in result.get("attachments", []):
        if attachment.get("name") == "trace":
            trace_path = attachment.get("path")
            break

    # Parse start time
    start_time = None
    start_time_str = result.get("startTime")
    if start_time_str:
        try:
            # Handle ISO format with Z suffix
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except ValueError:
            pass

    return FailedTest(
        title=spec.get("title", "Unknown test"),
        file=file,
        suite=suite_title,
        project=test.get("projectName", "unknown"),
        status=result.get("status", "unknown"),
        duration_ms=result.get("duration", 0),
        start_time=start_time,
        errors=errors,
        trace_path=trace_path,
    )
