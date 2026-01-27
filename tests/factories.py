"""Test data factories for Heisenberg tests.

This module provides factory functions for creating test data objects.
Use these instead of defining fixtures locally in each test file.

Usage:
    from tests.factories import make_llm_analysis, make_playwright_report

    def test_something():
        analysis = make_llm_analysis(content="custom content")
        report = make_playwright_report(total_failed=2)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from heisenberg.core.diagnosis import ConfidenceLevel, Diagnosis
from heisenberg.core.models import (
    ErrorInfo,
    FailureMetadata,
    Framework,
    UnifiedFailure,
    UnifiedTestRun,
)
from heisenberg.integrations.docker import ContainerLogs, LogEntry
from heisenberg.llm.models import LLMAnalysis
from heisenberg.parsers.playwright import ErrorDetail, FailedTest, PlaywrightReport

if TYPE_CHECKING:
    from heisenberg.core.analyzer import AIAnalysisResult


def make_llm_analysis(
    content: str = "test response",
    input_tokens: int = 100,
    output_tokens: int = 50,
    model: str = "test-model",
    provider: str = "test-provider",
) -> LLMAnalysis:
    """Create LLMAnalysis for testing.

    Args:
        content: Response content from LLM.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        model: Model name.
        provider: Provider name.

    Returns:
        LLMAnalysis instance.
    """
    return LLMAnalysis(
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
        provider=provider,
    )


def make_failed_test(
    title: str = "Login test",
    file: str = "tests/login.spec.ts",
    suite: str = "Authentication",
    project: str = "chromium",
    status: str = "failed",
    duration_ms: int = 5000,
    error_message: str = "TimeoutError: locator.click: Timeout 30000ms exceeded",
    error_stack: str = "Error: TimeoutError\n    at login.spec.ts:15:10",
    trace_path: str | None = "trace.zip",
    start_time: datetime | None = None,
) -> FailedTest:
    """Create FailedTest for testing.

    Args:
        title: Test title.
        file: Test file path.
        suite: Test suite name.
        project: Browser/project name.
        status: Test status.
        duration_ms: Test duration in milliseconds.
        error_message: Error message.
        error_stack: Error stack trace.
        trace_path: Path to trace file.
        start_time: Test start time.

    Returns:
        FailedTest instance.
    """
    if start_time is None:
        start_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    return FailedTest(
        title=title,
        file=file,
        suite=suite,
        project=project,
        status=status,
        duration_ms=duration_ms,
        start_time=start_time,
        errors=[ErrorDetail(message=error_message, stack=error_stack)],
        trace_path=trace_path,
    )


def make_playwright_report(
    total_passed: int = 4,
    total_failed: int = 1,
    total_skipped: int = 0,
    total_flaky: int = 0,
    failed_tests: list[FailedTest] | None = None,
) -> PlaywrightReport:
    """Create PlaywrightReport for testing.

    Args:
        total_passed: Number of passed tests.
        total_failed: Number of failed tests.
        total_skipped: Number of skipped tests.
        total_flaky: Number of flaky tests.
        failed_tests: List of failed tests. If None, creates one default failed test.

    Returns:
        PlaywrightReport instance.
    """
    if failed_tests is None:
        failed_tests = [make_failed_test()]
    return PlaywrightReport(
        total_passed=total_passed,
        total_failed=total_failed,
        total_skipped=total_skipped,
        total_flaky=total_flaky,
        failed_tests=failed_tests,
    )


def make_container_logs(
    container_name: str = "api",
    messages: list[str] | None = None,
    stream: str = "stderr",
    timestamp: datetime | None = None,
) -> ContainerLogs:
    """Create ContainerLogs for testing.

    Args:
        container_name: Name of the container.
        messages: List of log messages. If None, uses default message.
        stream: Log stream (stdout/stderr).
        timestamp: Timestamp for log entries.

    Returns:
        ContainerLogs instance.
    """
    if messages is None:
        messages = ["Connection pool exhausted"]
    if timestamp is None:
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    return ContainerLogs(
        container_name=container_name,
        entries=[
            LogEntry(
                timestamp=timestamp,
                message=msg,
                stream=stream,
            )
            for msg in messages
        ],
    )


def make_diagnosis(
    root_cause: str = "Database connection timeout causing API failure",
    evidence: list[str] | None = None,
    suggested_fix: str = "Increase connection pool size",
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    confidence_explanation: str = "Clear correlation in logs",
    raw_response: str = "Raw AI response",
) -> Diagnosis:
    """Create Diagnosis for testing.

    Args:
        root_cause: Root cause description.
        evidence: List of evidence items.
        suggested_fix: Suggested fix description.
        confidence: Confidence level.
        confidence_explanation: Explanation for confidence level.
        raw_response: Raw response from AI.

    Returns:
        Diagnosis instance.
    """
    if evidence is None:
        evidence = ["TimeoutError in logs", "Connection pool exhausted"]
    return Diagnosis(
        root_cause=root_cause,
        evidence=evidence,
        suggested_fix=suggested_fix,
        confidence=confidence,
        confidence_explanation=confidence_explanation,
        raw_response=raw_response,
    )


def make_ai_analysis_result(
    diagnosis: Diagnosis | None = None,
    input_tokens: int = 500,
    output_tokens: int = 200,
    provider: str | None = None,
) -> AIAnalysisResult:
    """Create AIAnalysisResult for testing.

    Args:
        diagnosis: Diagnosis instance. If None, creates default.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        provider: Provider name.

    Returns:
        AIAnalysisResult instance.
    """
    from heisenberg.core.analyzer import AIAnalysisResult

    if diagnosis is None:
        diagnosis = make_diagnosis()
    return AIAnalysisResult(
        diagnosis=diagnosis,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        provider=provider,
    )


def make_unified_failure(
    test_id: str = "test-1",
    file_path: str = "test.py",
    test_title: str = "Test case",
    error_message: str = "Test failed",
    stack_trace: str = "at line 10",
    framework: Framework = Framework.PLAYWRIGHT,
    duration_ms: int = 100,
) -> UnifiedFailure:
    """Create UnifiedFailure for testing.

    Args:
        test_id: Unique test identifier.
        file_path: Path to test file.
        test_title: Test title.
        error_message: Error message.
        stack_trace: Stack trace.
        framework: Test framework.
        duration_ms: Test duration in milliseconds.

    Returns:
        UnifiedFailure instance.
    """
    return UnifiedFailure(
        test_id=test_id,
        file_path=file_path,
        test_title=test_title,
        suite_path=["Suite"],
        error=ErrorInfo(
            message=error_message,
            stack_trace=stack_trace,
            location=None,
        ),
        metadata=FailureMetadata(
            framework=framework,
            browser=None,
            retry_count=0,
            duration_ms=duration_ms,
            tags=[],
        ),
    )


def make_unified_run(
    run_id: str = "run-1",
    total_tests: int = 1,
    passed_tests: int = 0,
    failed_tests: int = 1,
    skipped_tests: int = 0,
    failures: list[UnifiedFailure] | None = None,
    repository: str | None = None,
    branch: str | None = None,
    commit_sha: str | None = None,
) -> UnifiedTestRun:
    """Create UnifiedTestRun for testing.

    Args:
        run_id: Unique run identifier.
        total_tests: Total number of tests.
        passed_tests: Number of passed tests.
        failed_tests: Number of failed tests.
        skipped_tests: Number of skipped tests.
        failures: List of failures. If None, creates one default failure.
        repository: Repository name.
        branch: Branch name.
        commit_sha: Commit SHA.

    Returns:
        UnifiedTestRun instance.
    """
    if failures is None:
        failures = [make_unified_failure()]
    return UnifiedTestRun(
        run_id=run_id,
        repository=repository,
        branch=branch,
        commit_sha=commit_sha,
        workflow_name=None,
        run_url=None,
        total_tests=total_tests,
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        skipped_tests=skipped_tests,
        failures=failures,
    )


# Sample AI response for mocking LLM responses
SAMPLE_AI_RESPONSE = """## Root Cause Analysis
The test failure is caused by a database connection timeout. The backend API failed to establish a database connection within the expected time limit.

## Evidence
- Error message shows "TimeoutError: 30000ms exceeded"
- Backend logs indicate "Connection pool exhausted"
- High load on database server

## Suggested Fix
1. Increase the database connection pool size
2. Add retry logic for database connections
3. Consider using connection health checks

## Confidence Score
HIGH (>80%)
The stack trace and backend logs clearly correlate, showing the database timeout as the root cause."""
