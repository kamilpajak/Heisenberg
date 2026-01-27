"""Tests for AI-powered analyzer integration - TDD Red-Green-Refactor."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from heisenberg.core.analyzer import AIAnalysisResult, AIAnalyzer, analyze_with_ai
from heisenberg.core.diagnosis import ConfidenceLevel, Diagnosis
from heisenberg.llm.models import LLMAnalysis
from tests.factories import SAMPLE_AI_RESPONSE

if TYPE_CHECKING:
    from heisenberg.integrations.docker import ContainerLogs
    from heisenberg.parsers.playwright import PlaywrightReport


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

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_analyzer_calls_llm(self, mock_get_client: MagicMock, sample_report: PlaywrightReport):
        """Analyzer should call LLM with prompt."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMAnalysis(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
            model="claude-sonnet-4-20250514",
            provider="anthropic",
        )
        mock_get_client.return_value = mock_llm

        analyzer = AIAnalyzer(report=sample_report, api_key="test-key")

        # When
        analyzer.analyze()

        # Then
        mock_llm.analyze.assert_called_once()

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_analyzer_returns_ai_analysis_result(
        self, mock_get_client: MagicMock, sample_report: PlaywrightReport
    ):
        """Analyzer should return AIAnalysisResult."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMAnalysis(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
            model="claude-sonnet-4-20250514",
            provider="anthropic",
        )
        mock_get_client.return_value = mock_llm

        analyzer = AIAnalyzer(report=sample_report, api_key="test-key")

        # When
        result = analyzer.analyze()

        # Then
        assert isinstance(result, AIAnalysisResult)

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_result_contains_diagnosis(
        self, mock_get_client: MagicMock, sample_report: PlaywrightReport
    ):
        """Result should contain parsed diagnosis."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMAnalysis(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
            model="claude-sonnet-4-20250514",
            provider="anthropic",
        )
        mock_get_client.return_value = mock_llm

        analyzer = AIAnalyzer(report=sample_report, api_key="test-key")

        # When
        result = analyzer.analyze()

        # Then
        assert isinstance(result.diagnosis, Diagnosis)
        assert result.diagnosis.confidence == ConfidenceLevel.HIGH

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_result_contains_token_usage(
        self, mock_get_client: MagicMock, sample_report: PlaywrightReport
    ):
        """Result should track token usage."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMAnalysis(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
            model="claude-sonnet-4-20250514",
            provider="anthropic",
        )
        mock_get_client.return_value = mock_llm

        analyzer = AIAnalyzer(report=sample_report, api_key="test-key")

        # When
        result = analyzer.analyze()

        # Then
        assert result.input_tokens == 500
        assert result.output_tokens == 200

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_analyzer_uses_system_prompt(
        self, mock_get_client: MagicMock, sample_report: PlaywrightReport
    ):
        """Analyzer should use system prompt for context."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMAnalysis(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
            model="claude-sonnet-4-20250514",
            provider="anthropic",
        )
        mock_get_client.return_value = mock_llm

        analyzer = AIAnalyzer(report=sample_report, api_key="test-key")

        # When
        analyzer.analyze()

        # Then
        call_kwargs = mock_llm.analyze.call_args[1]
        assert "system_prompt" in call_kwargs
        assert call_kwargs["system_prompt"] is not None

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_analyzer_includes_logs_in_prompt(
        self,
        mock_get_client: MagicMock,
        sample_report: PlaywrightReport,
        sample_logs: dict[str, ContainerLogs],
    ):
        """Analyzer should include container logs in prompt."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMAnalysis(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
            model="claude-sonnet-4-20250514",
            provider="anthropic",
        )
        mock_get_client.return_value = mock_llm

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

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_analyze_with_ai_returns_result(
        self, mock_get_client: MagicMock, sample_report: PlaywrightReport
    ):
        """Helper should return AIAnalysisResult."""
        # Given
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMAnalysis(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
            model="claude-sonnet-4-20250514",
            provider="anthropic",
        )
        mock_get_client.return_value = mock_llm

        # When
        result = analyze_with_ai(sample_report, api_key="test-key")

        # Then
        assert isinstance(result, AIAnalysisResult)

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_analyze_with_ai_from_environment(
        self, mock_get_client: MagicMock, sample_report: PlaywrightReport, monkeypatch
    ):
        """Helper should read API key from environment."""
        # Given
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMAnalysis(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
            model="claude-sonnet-4-20250514",
            provider="anthropic",
        )
        mock_get_client.return_value = mock_llm

        # When
        result = analyze_with_ai(sample_report)

        # Then
        assert isinstance(result, AIAnalysisResult)
        mock_get_client.assert_called_once()


# Note: Fixtures (sample_report, sample_logs, sample_result) are now defined
# globally in tests/conftest.py using factories from tests/factories.py
