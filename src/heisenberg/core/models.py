"""Unified Failure Model for framework-agnostic test failure representation.

This module defines a canonical data model that represents test failures
from any testing framework (Playwright, Jest, Cypress, Vitest, etc.)
in a common format suitable for AI analysis.

The UnifiedFailure model is the core abstraction that allows Heisenberg
to analyze failures from multiple frameworks through a single interface.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Framework(Enum):
    """Supported test frameworks."""

    PLAYWRIGHT = "playwright"
    JEST = "jest"
    CYPRESS = "cypress"
    VITEST = "vitest"
    JUNIT = "junit"


@dataclass
class ErrorInfo:
    """Information about a test error."""

    message: str
    stack_trace: str | None = None
    location: dict[str, int] | None = None  # {"line": int, "column": int}


@dataclass
class Attachments:
    """Attachments associated with a test failure."""

    screenshot_url: str | None = None
    trace_url: str | None = None
    video_url: str | None = None


@dataclass
class FailureMetadata:
    """Metadata about the test execution environment."""

    framework: Framework = Framework.PLAYWRIGHT
    browser: str | None = None
    retry_count: int = 0
    duration_ms: int | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class UnifiedFailure:
    """Framework-agnostic representation of a test failure.

    This is the core data structure that Heisenberg uses to analyze
    test failures regardless of which framework produced them.
    """

    test_id: str
    file_path: str
    test_title: str
    error: ErrorInfo
    suite_path: list[str] = field(default_factory=list)
    attachments: Attachments | None = None
    metadata: FailureMetadata = field(default_factory=FailureMetadata)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        data = {
            "test_id": self.test_id,
            "file_path": self.file_path,
            "test_title": self.test_title,
            "suite_path": self.suite_path,
            "error": {
                "message": self.error.message,
                "stack_trace": self.error.stack_trace,
                "location": self.error.location,
            },
            "metadata": {
                "framework": self.metadata.framework.value,
                "browser": self.metadata.browser,
                "retry_count": self.metadata.retry_count,
                "duration_ms": self.metadata.duration_ms,
                "tags": self.metadata.tags,
            },
        }
        if self.attachments:
            data["attachments"] = {
                "screenshot_url": self.attachments.screenshot_url,
                "trace_url": self.attachments.trace_url,
                "video_url": self.attachments.video_url,
            }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnifiedFailure:
        """Deserialize from dictionary."""
        error_data = data.get("error", {})
        error = ErrorInfo(
            message=error_data.get("message", ""),
            stack_trace=error_data.get("stack_trace"),
            location=error_data.get("location"),
        )

        metadata_data = data.get("metadata", {})
        framework_str = metadata_data.get("framework", "playwright")
        try:
            framework = Framework(framework_str)
        except ValueError:
            framework = Framework.PLAYWRIGHT

        metadata = FailureMetadata(
            framework=framework,
            browser=metadata_data.get("browser"),
            retry_count=metadata_data.get("retry_count", 0),
            duration_ms=metadata_data.get("duration_ms"),
            tags=metadata_data.get("tags", []),
        )

        attachments = None
        if "attachments" in data:
            att_data = data["attachments"]
            attachments = Attachments(
                screenshot_url=att_data.get("screenshot_url"),
                trace_url=att_data.get("trace_url"),
                video_url=att_data.get("video_url"),
            )

        return cls(
            test_id=data.get("test_id", ""),
            file_path=data.get("file_path", ""),
            test_title=data.get("test_title", ""),
            suite_path=data.get("suite_path", []),
            error=error,
            attachments=attachments,
            metadata=metadata,
        )


@dataclass
class UnifiedTestRun:
    """Container for a complete test run with failures.

    Groups multiple UnifiedFailure instances with run-level metadata
    such as repository, branch, and aggregate statistics.
    """

    run_id: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    failures: list[UnifiedFailure] = field(default_factory=list)
    repository: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    workflow_name: str | None = None
    run_url: str | None = None

    def summary(self) -> dict[str, Any]:
        """Get summary statistics for the test run."""
        pass_rate = self.passed_tests / self.total_tests if self.total_tests > 0 else 0
        return {
            "total": self.total_tests,
            "passed": self.passed_tests,
            "failed": self.failed_tests,
            "skipped": self.skipped_tests,
            "pass_rate": pass_rate,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "run_id": self.run_id,
            "repository": self.repository,
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "workflow_name": self.workflow_name,
            "run_url": self.run_url,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "skipped_tests": self.skipped_tests,
            "failures": [f.to_dict() for f in self.failures],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnifiedTestRun:
        """Deserialize from dictionary."""
        failures = [UnifiedFailure.from_dict(f) for f in data.get("failures", [])]
        return cls(
            run_id=data.get("run_id", ""),
            repository=data.get("repository"),
            branch=data.get("branch"),
            commit_sha=data.get("commit_sha"),
            workflow_name=data.get("workflow_name"),
            run_url=data.get("run_url"),
            total_tests=data.get("total_tests", 0),
            passed_tests=data.get("passed_tests", 0),
            failed_tests=data.get("failed_tests", 0),
            skipped_tests=data.get("skipped_tests", 0),
            failures=failures,
        )


class PlaywrightTransformer:
    """Transforms Playwright reports to UnifiedFailure model."""

    @staticmethod
    def transform_failure(failure_data: dict[str, Any]) -> UnifiedFailure:
        """Transform a single Playwright failure to UnifiedFailure.

        Args:
            failure_data: Dictionary containing Playwright failure data.
                Expected keys: title, file, status, errors, projectName,
                line, column, duration

        Returns:
            UnifiedFailure instance
        """
        # Extract error information
        errors = failure_data.get("errors", [])
        if errors:
            # Concatenate multiple errors
            messages = [e.get("message", "") for e in errors]
            stacks = [e.get("stack", "") for e in errors if e.get("stack")]
            if len(messages) > 1:
                error_message = "\n---\n".join(messages)
            elif messages:
                error_message = messages[0]
            else:
                error_message = "Unknown error"
            stack_trace = "\n---\n".join(stacks) if stacks else None
        else:
            error_message = "Unknown error"
            stack_trace = None

        # Extract location
        location = None
        if "line" in failure_data and failure_data["line"] is not None:
            location = {
                "line": failure_data["line"],
                "column": failure_data.get("column", 0),
            }

        # Extract metadata
        browser = failure_data.get("projectName")
        duration = failure_data.get("duration")

        # Generate test ID (MD5 used for fingerprinting, not security)
        test_id = hashlib.md5(  # NOSONAR - MD5 used only for non-cryptographic fingerprinting
            f"{failure_data.get('file', '')}-{failure_data.get('title', '')}".encode()
        ).hexdigest()[:12]

        return UnifiedFailure(
            test_id=test_id,
            file_path=failure_data.get("file", ""),
            test_title=failure_data.get("title", ""),
            error=ErrorInfo(
                message=error_message,
                stack_trace=stack_trace,
                location=location,
            ),
            metadata=FailureMetadata(
                framework=Framework.PLAYWRIGHT,
                browser=browser,
                duration_ms=duration,
            ),
        )

    @staticmethod
    def transform_report(
        report: Any,  # PlaywrightReport
        run_id: str | None = None,
        repository: str | None = None,
        branch: str | None = None,
        commit_sha: str | None = None,
    ) -> UnifiedTestRun:
        """Transform a complete Playwright report to UnifiedTestRun.

        Args:
            report: PlaywrightReport instance (from playwright_parser)
            run_id: Optional run identifier
            repository: Optional repository name
            branch: Optional branch name
            commit_sha: Optional commit SHA

        Returns:
            UnifiedTestRun instance
        """
        # Transform each FailedTest to UnifiedFailure
        failures = []
        for failed_test in report.failed_tests:
            # Build failure data dict from FailedTest
            errors = [{"message": e.message, "stack": e.stack} for e in failed_test.errors]
            failure_data = {
                "title": failed_test.title,
                "file": failed_test.file,
                "status": failed_test.status,
                "duration": failed_test.duration_ms,
                "errors": errors,
                "projectName": failed_test.project,
            }
            failure = PlaywrightTransformer.transform_failure(failure_data)
            if failed_test.suite:
                failure.suite_path = [failed_test.suite]
            failures.append(failure)

        # Calculate total tests
        total_tests = (
            report.total_passed + report.total_failed + report.total_skipped + report.total_flaky
        )

        return UnifiedTestRun(
            run_id=run_id or "unknown",
            repository=repository,
            branch=branch,
            commit_sha=commit_sha,
            total_tests=total_tests,
            passed_tests=report.total_passed,
            failed_tests=report.total_failed,
            skipped_tests=report.total_skipped,
            failures=failures,
        )
