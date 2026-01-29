"""JUnit XML parser for test reports.

This module provides parsing of JUnit XML format, commonly used by:
- Jest (with jest-junit reporter)
- JUnit (Java)
- pytest (with pytest-junit)
- Many other test frameworks

The parser converts JUnit XML to the unified failure model.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heisenberg.core.models import UnifiedTestRun


@dataclass
class JUnitTestCase:
    """Represents a single test case from JUnit XML."""

    name: str
    classname: str
    time: float = 0.0
    status: str = "passed"  # passed, failed, error, skipped
    failure_message: str = ""
    failure_type: str = ""
    failure_content: str = ""  # Full stack trace
    skipped_message: str = ""

    @property
    def file_path(self) -> str:
        """Extract file path from classname (Java package notation)."""
        # Convert com.example.tests.LoginTest to com/example/tests/LoginTest
        return self.classname.replace(".", "/")


@dataclass
class JUnitReport:
    """Represents a parsed JUnit XML report."""

    name: str = ""
    total_tests: int = 0
    total_passed: int = 0
    total_failed: int = 0
    total_errors: int = 0
    total_skipped: int = 0
    time: float = 0.0
    test_cases: list[JUnitTestCase] = field(default_factory=list)

    @property
    def failed_tests(self) -> list[JUnitTestCase]:
        """Get all failed test cases (failures + errors)."""
        return [tc for tc in self.test_cases if tc.status in ("failed", "error")]


class JUnitParser:
    """Parser for JUnit XML reports."""

    @staticmethod
    def parse_string(xml_content: str) -> JUnitReport:
        """Parse JUnit XML from string.

        Args:
            xml_content: JUnit XML as string.

        Returns:
            JUnitReport with parsed data.
        """
        root = ET.fromstring(xml_content)  # noqa: S314 - trusted test report data
        return JUnitParser._parse_root(root)

    @staticmethod
    def parse_file(file_path: Path | str) -> JUnitReport:
        """Parse JUnit XML from file.

        Args:
            file_path: Path to JUnit XML file.

        Returns:
            JUnitReport with parsed data.
        """
        tree = ET.parse(file_path)  # noqa: S314 - trusted test report data
        return JUnitParser._parse_root(tree.getroot())

    @staticmethod
    def _parse_root(root: ET.Element) -> JUnitReport:
        """Parse the root element of JUnit XML."""
        report = JUnitReport()

        # Handle both <testsuites> and <testsuite> as root
        if root.tag == "testsuites":
            report.name = root.get("name", "")
            report.time = float(root.get("time", 0))

            # Parse each testsuite
            for testsuite in root.findall("testsuite"):
                JUnitParser._parse_testsuite(testsuite, report)

            # Update totals from root attributes if available
            if root.get("tests"):
                report.total_tests = int(root.get("tests", 0))
            if root.get("failures"):
                report.total_failed = int(root.get("failures", 0))
            if root.get("errors"):
                report.total_errors = int(root.get("errors", 0))
            if root.get("skipped"):
                report.total_skipped = int(root.get("skipped", 0))

        elif root.tag == "testsuite":
            report.name = root.get("name", "")
            report.time = float(root.get("time", 0))
            JUnitParser._parse_testsuite(root, report)

        # Calculate passed tests
        report.total_passed = (
            report.total_tests - report.total_failed - report.total_errors - report.total_skipped
        )

        return report

    @staticmethod
    def _parse_testsuite(testsuite: ET.Element, report: JUnitReport) -> None:
        """Parse a testsuite element."""
        # Update counts from testsuite attributes
        tests = int(testsuite.get("tests", 0))
        failures = int(testsuite.get("failures", 0))
        errors = int(testsuite.get("errors", 0))
        skipped = int(testsuite.get("skipped", 0))

        # If root didn't have counts, accumulate from testsuites
        if report.total_tests == 0:
            report.total_tests += tests
        if report.total_failed == 0:
            report.total_failed += failures
        if report.total_errors == 0:
            report.total_errors += errors
        if report.total_skipped == 0:
            report.total_skipped += skipped

        # Parse test cases
        for testcase in testsuite.findall("testcase"):
            tc = JUnitParser._parse_testcase(testcase)
            report.test_cases.append(tc)

    @staticmethod
    def _parse_testcase(testcase: ET.Element) -> JUnitTestCase:
        """Parse a testcase element."""
        tc = JUnitTestCase(
            name=testcase.get("name", ""),
            classname=testcase.get("classname", ""),
            time=float(testcase.get("time", 0)),
        )

        # Check for failure
        failure = testcase.find("failure")
        if failure is not None:
            tc.status = "failed"
            tc.failure_message = failure.get("message", "")
            tc.failure_type = failure.get("type", "")
            tc.failure_content = failure.text or ""

            # If no message attribute, use content
            if not tc.failure_message and tc.failure_content:
                tc.failure_message = tc.failure_content.strip().split("\n")[0]

        # Check for error
        error = testcase.find("error")
        if error is not None:
            tc.status = "error"
            tc.failure_message = error.get("message", "")
            tc.failure_type = error.get("type", "")
            tc.failure_content = error.text or ""

            if not tc.failure_message and tc.failure_content:
                tc.failure_message = tc.failure_content.strip().split("\n")[0]

        # Check for skipped
        skipped = testcase.find("skipped")
        if skipped is not None:
            tc.status = "skipped"
            tc.skipped_message = skipped.get("message", "")

        return tc

    @staticmethod
    def to_unified(
        report: JUnitReport,
        run_id: str | None = None,
        repository: str | None = None,
        branch: str | None = None,
    ) -> UnifiedTestRun:
        """Convert JUnitReport to UnifiedTestRun.

        Args:
            report: Parsed JUnit report.
            run_id: Optional run identifier.
            repository: Optional repository name.
            branch: Optional branch name.

        Returns:
            UnifiedTestRun with failures from JUnit report.
        """
        from heisenberg.core.models import (
            ErrorInfo,
            FailureMetadata,
            Framework,
            UnifiedFailure,
            UnifiedTestRun,
        )

        failures = []
        for i, tc in enumerate(report.failed_tests, 1):
            # Build error info
            error = ErrorInfo(
                message=tc.failure_message,
                stack_trace=tc.failure_content if tc.failure_content else None,
            )

            # Build metadata
            metadata = FailureMetadata(
                framework=Framework.JUNIT,
                duration_ms=int(tc.time * 1000) if tc.time else None,
            )

            # Create failure
            failure = UnifiedFailure(
                test_id=str(i),
                file_path=tc.file_path,
                test_title=tc.name,
                error=error,
                suite_path=[tc.classname] if tc.classname else [],
                metadata=metadata,
            )
            failures.append(failure)

        return UnifiedTestRun(
            run_id=run_id or "junit-run",
            repository=repository,
            branch=branch,
            total_tests=report.total_tests,
            passed_tests=report.total_passed,
            failed_tests=report.total_failed + report.total_errors,
            skipped_tests=report.total_skipped,
            failures=failures,
        )
