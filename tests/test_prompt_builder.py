"""Tests for prompt builder - TDD Red-Green-Refactor."""

from datetime import UTC, datetime

import pytest

from heisenberg.docker_logs import ContainerLogs, LogEntry
from heisenberg.playwright_parser import ErrorDetail, FailedTest, PlaywrightReport
from heisenberg.prompt_builder import (
    PromptBuilder,
    build_analysis_prompt,
    get_system_prompt,
)


class TestPromptBuilder:
    """Test suite for PromptBuilder class."""

    def test_builder_initializes_with_report(self, sample_report: PlaywrightReport):
        """Builder should accept PlaywrightReport."""
        # When
        builder = PromptBuilder(report=sample_report)

        # Then
        assert builder.report is sample_report

    def test_builder_accepts_container_logs(
        self, sample_report: PlaywrightReport, sample_logs: dict[str, ContainerLogs]
    ):
        """Builder should accept container logs."""
        # When
        builder = PromptBuilder(report=sample_report, container_logs=sample_logs)

        # Then
        assert builder.container_logs is sample_logs

    def test_builder_generates_prompt(self, sample_report: PlaywrightReport):
        """Builder should generate a prompt string."""
        # Given
        builder = PromptBuilder(report=sample_report)

        # When
        prompt = builder.build()

        # Then
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_contains_test_name(self, sample_report: PlaywrightReport):
        """Prompt should include failed test names."""
        # Given
        builder = PromptBuilder(report=sample_report)

        # When
        prompt = builder.build()

        # Then
        assert "Login test" in prompt

    def test_prompt_contains_error_message(self, sample_report: PlaywrightReport):
        """Prompt should include error messages."""
        # Given
        builder = PromptBuilder(report=sample_report)

        # When
        prompt = builder.build()

        # Then
        assert "TimeoutError" in prompt

    def test_prompt_contains_stack_trace(self, sample_report: PlaywrightReport):
        """Prompt should include stack traces."""
        # Given
        builder = PromptBuilder(report=sample_report)

        # When
        prompt = builder.build()

        # Then
        assert "login.spec.ts" in prompt

    def test_prompt_includes_container_logs(
        self, sample_report: PlaywrightReport, sample_logs: dict[str, ContainerLogs]
    ):
        """Prompt should include relevant container logs."""
        # Given
        builder = PromptBuilder(report=sample_report, container_logs=sample_logs)

        # When
        prompt = builder.build()

        # Then
        assert "api" in prompt.lower()
        assert "Database connection" in prompt

    def test_prompt_includes_test_file_path(self, sample_report: PlaywrightReport):
        """Prompt should include test file path for context."""
        # Given
        builder = PromptBuilder(report=sample_report)

        # When
        prompt = builder.build()

        # Then
        assert "tests/login.spec.ts" in prompt

    def test_prompt_includes_duration(self, sample_report: PlaywrightReport):
        """Prompt should include test duration."""
        # Given
        builder = PromptBuilder(report=sample_report)

        # When
        prompt = builder.build()

        # Then
        # Duration should be mentioned (in ms)
        assert "5000ms" in prompt or "Duration" in prompt

    def test_prompt_truncates_long_logs(
        self, sample_report: PlaywrightReport, verbose_logs: dict[str, ContainerLogs]
    ):
        """Prompt should truncate excessively long logs."""
        # Given
        builder = PromptBuilder(
            report=sample_report,
            container_logs=verbose_logs,
            max_log_lines=10,
        )

        # When
        prompt = builder.build()

        # Then
        # Should not contain all 100 log lines
        assert prompt.count("Log line") <= 15  # Some buffer for context


class TestSystemPrompt:
    """Test suite for system prompt generation."""

    def test_system_prompt_exists(self):
        """System prompt should be available."""
        # When
        prompt = get_system_prompt()

        # Then
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_system_prompt_mentions_role(self):
        """System prompt should define AI's role."""
        # When
        prompt = get_system_prompt()

        # Then
        assert "test" in prompt.lower()
        assert "analysis" in prompt.lower() or "analyze" in prompt.lower()

    def test_system_prompt_mentions_confidence(self):
        """System prompt should request confidence score."""
        # When
        prompt = get_system_prompt()

        # Then
        assert "confidence" in prompt.lower()


class TestConvenienceFunction:
    """Test suite for build_analysis_prompt helper."""

    def test_build_analysis_prompt_returns_tuple(self, sample_report: PlaywrightReport):
        """Helper should return (system_prompt, user_prompt) tuple."""
        # When
        result = build_analysis_prompt(sample_report)

        # Then
        assert isinstance(result, tuple)
        assert len(result) == 2
        system_prompt, user_prompt = result
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)

    def test_build_analysis_prompt_with_logs(
        self, sample_report: PlaywrightReport, sample_logs: dict[str, ContainerLogs]
    ):
        """Helper should accept container logs."""
        # When
        system_prompt, user_prompt = build_analysis_prompt(
            sample_report, container_logs=sample_logs
        )

        # Then
        assert "api" in user_prompt.lower()


# Fixtures


@pytest.fixture
def sample_report() -> PlaywrightReport:
    """Sample Playwright report with one failed test."""
    return PlaywrightReport(
        total_passed=4,
        total_failed=1,
        total_skipped=0,
        total_flaky=0,
        failed_tests=[
            FailedTest(
                title="Login test",
                file="tests/login.spec.ts",
                suite="Authentication",
                project="chromium",
                status="failed",
                duration_ms=5000,
                start_time=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                errors=[
                    ErrorDetail(
                        message="TimeoutError: locator.click: Timeout 30000ms exceeded",
                        stack="Error: TimeoutError\n    at login.spec.ts:15:10\n    at test.step",
                    )
                ],
                trace_path="trace.zip",
            )
        ],
    )


@pytest.fixture
def sample_logs() -> dict[str, ContainerLogs]:
    """Sample container logs."""
    return {
        "api": ContainerLogs(
            container_name="api",
            entries=[
                LogEntry(
                    timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                    message="Database connection established",
                    stream="stdout",
                ),
                LogEntry(
                    timestamp=datetime(2024, 1, 15, 10, 30, 5, tzinfo=UTC),
                    message="Request timeout on /api/login",
                    stream="stderr",
                ),
            ],
        )
    }


@pytest.fixture
def verbose_logs() -> dict[str, ContainerLogs]:
    """Very verbose container logs for truncation testing."""
    from datetime import timedelta

    base_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    entries = [
        LogEntry(
            timestamp=base_time + timedelta(seconds=i),
            message=f"Log line {i}: Some verbose debug output",
            stream="stdout",
        )
        for i in range(100)
    ]
    return {
        "api": ContainerLogs(container_name="api", entries=entries),
    }
