"""Tests for AI-powered analyzer integration - TDD Red-Green-Refactor."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from heisenberg.ai_analyzer import AIAnalysisResult, AIAnalyzer, analyze_with_ai
from heisenberg.diagnosis import ConfidenceLevel, Diagnosis
from heisenberg.docker_logs import ContainerLogs, LogEntry
from heisenberg.llm_client import LLMResponse
from heisenberg.playwright_parser import ErrorDetail, FailedTest, PlaywrightReport


class TestAIAnalyzer:
    """Test suite for AIAnalyzer class."""

    def test_analyzer_initializes_with_report(self, sample_report: PlaywrightReport):
        """Analyzer should accept PlaywrightReport."""
        # When
        analyzer = AIAnalyzer(report=sample_report)

        # Then
        assert analyzer.report is sample_report

    def test_analyzer_accepts_container_logs(
        self, sample_report: PlaywrightReport, sample_logs: dict[str, ContainerLogs]
    ):
        """Analyzer should accept container logs."""
        # When
        analyzer = AIAnalyzer(report=sample_report, container_logs=sample_logs)

        # Then
        assert analyzer.container_logs is sample_logs

    def test_analyzer_accepts_api_key(self, sample_report: PlaywrightReport):
        """Analyzer should accept API key."""
        # When
        analyzer = AIAnalyzer(report=sample_report, api_key="test-key")

        # Then
        assert analyzer.api_key == "test-key"

    @patch("heisenberg.ai_analyzer.LLMClient")
    def test_analyzer_calls_llm(self, mock_llm_class: MagicMock, sample_report: PlaywrightReport):
        """Analyzer should call LLM with prompt."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMResponse(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
        )
        mock_llm_class.return_value = mock_llm

        analyzer = AIAnalyzer(report=sample_report, api_key="test-key")

        # When
        analyzer.analyze()

        # Then
        mock_llm.analyze.assert_called_once()

    @patch("heisenberg.ai_analyzer.LLMClient")
    def test_analyzer_returns_ai_analysis_result(
        self, mock_llm_class: MagicMock, sample_report: PlaywrightReport
    ):
        """Analyzer should return AIAnalysisResult."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMResponse(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
        )
        mock_llm_class.return_value = mock_llm

        analyzer = AIAnalyzer(report=sample_report, api_key="test-key")

        # When
        result = analyzer.analyze()

        # Then
        assert isinstance(result, AIAnalysisResult)

    @patch("heisenberg.ai_analyzer.LLMClient")
    def test_result_contains_diagnosis(
        self, mock_llm_class: MagicMock, sample_report: PlaywrightReport
    ):
        """Result should contain parsed diagnosis."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMResponse(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
        )
        mock_llm_class.return_value = mock_llm

        analyzer = AIAnalyzer(report=sample_report, api_key="test-key")

        # When
        result = analyzer.analyze()

        # Then
        assert isinstance(result.diagnosis, Diagnosis)
        assert result.diagnosis.confidence == ConfidenceLevel.HIGH

    @patch("heisenberg.ai_analyzer.LLMClient")
    def test_result_contains_token_usage(
        self, mock_llm_class: MagicMock, sample_report: PlaywrightReport
    ):
        """Result should track token usage."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMResponse(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
        )
        mock_llm_class.return_value = mock_llm

        analyzer = AIAnalyzer(report=sample_report, api_key="test-key")

        # When
        result = analyzer.analyze()

        # Then
        assert result.input_tokens == 500
        assert result.output_tokens == 200

    @patch("heisenberg.ai_analyzer.LLMClient")
    def test_analyzer_uses_system_prompt(
        self, mock_llm_class: MagicMock, sample_report: PlaywrightReport
    ):
        """Analyzer should use system prompt for context."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMResponse(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
        )
        mock_llm_class.return_value = mock_llm

        analyzer = AIAnalyzer(report=sample_report, api_key="test-key")

        # When
        analyzer.analyze()

        # Then
        call_kwargs = mock_llm.analyze.call_args[1]
        assert "system_prompt" in call_kwargs
        assert call_kwargs["system_prompt"] is not None

    @patch("heisenberg.ai_analyzer.LLMClient")
    def test_analyzer_includes_logs_in_prompt(
        self,
        mock_llm_class: MagicMock,
        sample_report: PlaywrightReport,
        sample_logs: dict[str, ContainerLogs],
    ):
        """Analyzer should include container logs in prompt."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMResponse(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
        )
        mock_llm_class.return_value = mock_llm

        analyzer = AIAnalyzer(report=sample_report, container_logs=sample_logs, api_key="test-key")

        # When
        analyzer.analyze()

        # Then
        call_args = mock_llm.analyze.call_args[0]
        prompt = call_args[0]
        assert "api" in prompt.lower()


class TestAIAnalysisResult:
    """Test suite for AIAnalysisResult data model."""

    def test_result_to_markdown(self, sample_result: AIAnalysisResult):
        """Result should format as markdown."""
        # When
        md = sample_result.to_markdown()

        # Then
        assert "## Heisenberg" in md
        assert "AI Analysis" in md

    def test_markdown_includes_diagnosis(self, sample_result: AIAnalysisResult):
        """Markdown should include AI diagnosis."""
        # When
        md = sample_result.to_markdown()

        # Then
        assert "Root Cause" in md
        assert "connection timeout" in md.lower()

    def test_markdown_includes_confidence(self, sample_result: AIAnalysisResult):
        """Markdown should show confidence level."""
        # When
        md = sample_result.to_markdown()

        # Then
        assert "HIGH" in md or "Confidence" in md

    def test_markdown_includes_evidence(self, sample_result: AIAnalysisResult):
        """Markdown should show evidence."""
        # When
        md = sample_result.to_markdown()

        # Then
        assert "Evidence" in md

    def test_markdown_includes_suggested_fix(self, sample_result: AIAnalysisResult):
        """Markdown should show suggested fix."""
        # When
        md = sample_result.to_markdown()

        # Then
        assert "Fix" in md or "Suggested" in md


class TestConvenienceFunction:
    """Test suite for analyze_with_ai helper."""

    @patch("heisenberg.ai_analyzer.LLMClient")
    def test_analyze_with_ai_returns_result(
        self, mock_llm_class: MagicMock, sample_report: PlaywrightReport
    ):
        """Helper should return AIAnalysisResult."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMResponse(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
        )
        mock_llm_class.return_value = mock_llm

        # When
        result = analyze_with_ai(sample_report, api_key="test-key")

        # Then
        assert isinstance(result, AIAnalysisResult)

    @patch("heisenberg.ai_analyzer.LLMClient")
    def test_analyze_with_ai_from_environment(
        self, mock_llm_class: MagicMock, sample_report: PlaywrightReport, monkeypatch
    ):
        """Helper should read API key from environment."""
        # Given
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMResponse(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
        )
        mock_llm_class.from_environment.return_value = mock_llm

        # When
        result = analyze_with_ai(sample_report)

        # Then
        assert isinstance(result, AIAnalysisResult)
        mock_llm_class.from_environment.assert_called_once()


# Sample AI response for mocking
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
                        stack="Error: TimeoutError\n    at login.spec.ts:15:10",
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
                    message="Connection pool exhausted",
                    stream="stderr",
                ),
            ],
        )
    }


@pytest.fixture
def sample_result() -> AIAnalysisResult:
    """Sample AIAnalysisResult for testing."""
    from heisenberg.ai_analyzer import AIAnalysisResult
    from heisenberg.diagnosis import ConfidenceLevel, Diagnosis

    return AIAnalysisResult(
        diagnosis=Diagnosis(
            root_cause="Database connection timeout causing API failure",
            evidence=["TimeoutError in logs", "Connection pool exhausted"],
            suggested_fix="Increase connection pool size",
            confidence=ConfidenceLevel.HIGH,
            confidence_explanation="Clear correlation in logs",
            raw_response=SAMPLE_AI_RESPONSE,
        ),
        input_tokens=500,
        output_tokens=200,
    )
