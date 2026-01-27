"""Data models for normalized test reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ReportType(Enum):
    """Type of test report format."""

    JSON = "json"
    HTML = "html"
    BLOB = "blob"  # Playwright blob reports (mergeable)


class TestStatus(Enum):
    """Status of a test case."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TestCase:
    """A single test case result."""

    name: str
    status: TestStatus
    duration_ms: int | None = None
    error_message: str | None = None
    error_stack: str | None = None
    file_path: str | None = None
    line_number: int | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "error_stack": self.error_stack,
            "file_path": self.file_path,
            "line_number": self.line_number,
        }


@dataclass
class TestSuite:
    """A collection of test cases, potentially nested."""

    name: str
    tests: list[TestCase] = field(default_factory=list)
    suites: list[TestSuite] = field(default_factory=list)
    file_path: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "tests": [t.to_dict() for t in self.tests],
            "suites": [s.to_dict() for s in self.suites],
            "file_path": self.file_path,
        }


@dataclass
class NormalizedReport:
    """Framework-agnostic normalized test report.

    This is the common format used by the AI analyzer,
    regardless of the original test framework.
    """

    framework: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    suites: list[TestSuite] = field(default_factory=list)
    framework_version: str | None = None
    duration_ms: int | None = None
    raw_report: dict | None = None  # Original report for reference

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "framework": self.framework,
            "framework_version": self.framework_version,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "skipped_tests": self.skipped_tests,
            "duration_ms": self.duration_ms,
            "suites": [s.to_dict() for s in self.suites],
        }


@dataclass
class ExtractedReport:
    """Result of extracting a report from a ZIP archive."""

    report_type: ReportType
    root_dir: Path
    data_file: Path  # Path to JSON data file (for AI analysis)
    entry_point: Path  # Path to main file (report.json or index.html)
    raw_data: dict | None = None  # Parsed JSON data if available
    visual_only: bool = False  # True if report can only be viewed, not analyzed
