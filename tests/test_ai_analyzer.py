"""Tests for AI-powered analyzer integration.

Consolidates tests from:
- test_ai_analyzer.py (original)
- test_ai_analyzer_providers.py
- test_unified_ai_integration.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from heisenberg.core.analyzer import (
    AIAnalysisResult,
    AIAnalyzer,
    _get_llm_client_for_provider,
    analyze_unified_run,
    analyze_with_ai,
)
from heisenberg.core.diagnosis import ConfidenceLevel, Diagnosis
from heisenberg.core.models import (
    ErrorInfo,
    FailureMetadata,
    Framework,
    UnifiedFailure,
    UnifiedTestRun,
)
from heisenberg.llm.models import LLMAnalysis
from heisenberg.llm.providers import GeminiProvider, OpenAIProvider
from tests.factories import SAMPLE_AI_RESPONSE

if TYPE_CHECKING:
    from heisenberg.integrations.docker import ContainerLogs
    from heisenberg.parsers.playwright import PlaywrightReport


class TestAIAnalyzer:
    """Test suite for AIAnalyzer class."""

    def test_analyzer_initializes_with_report(self, sample_report: PlaywrightReport):
        """Analyzer should accept PlaywrightReport."""
        analyzer = AIAnalyzer(report=sample_report)
        assert analyzer.report is sample_report

    def test_analyzer_accepts_container_logs(
        self, sample_report: PlaywrightReport, sample_logs: dict[str, ContainerLogs]
    ):
        """Analyzer should accept container logs."""
        analyzer = AIAnalyzer(report=sample_report, container_logs=sample_logs)
        assert analyzer.container_logs is sample_logs

    def test_analyzer_accepts_api_key(self, sample_report: PlaywrightReport):
        """Analyzer should accept API key."""
        analyzer = AIAnalyzer(report=sample_report, api_key="test-key")
        assert analyzer.api_key == "test-key"

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_analyzer_calls_llm(self, mock_get_client: MagicMock, sample_report: PlaywrightReport):
        """Analyzer should call LLM with prompt."""
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
        analyzer.analyze()

        mock_llm.analyze.assert_called_once()

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_analyzer_returns_ai_analysis_result(
        self, mock_get_client: MagicMock, sample_report: PlaywrightReport
    ):
        """Analyzer should return AIAnalysisResult."""
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
        result = analyzer.analyze()

        assert isinstance(result, AIAnalysisResult)

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_result_contains_diagnosis(
        self, mock_get_client: MagicMock, sample_report: PlaywrightReport
    ):
        """Result should contain parsed diagnosis."""
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
        result = analyzer.analyze()

        assert isinstance(result.diagnosis, Diagnosis)
        assert result.diagnosis.confidence == ConfidenceLevel.HIGH

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_result_contains_token_usage(
        self, mock_get_client: MagicMock, sample_report: PlaywrightReport
    ):
        """Result should track token usage."""
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
        result = analyzer.analyze()

        assert result.input_tokens == 500
        assert result.output_tokens == 200

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_analyzer_uses_system_prompt(
        self, mock_get_client: MagicMock, sample_report: PlaywrightReport
    ):
        """Analyzer should use system prompt for context."""
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
        analyzer.analyze()

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
        analyzer.analyze()

        call_args = mock_llm.analyze.call_args[0]
        prompt = call_args[0]
        assert "api" in prompt.lower()


class TestAIAnalysisResult:
    """Test suite for AIAnalysisResult data model."""

    def test_result_to_markdown(self, sample_result: AIAnalysisResult):
        """Result should format as markdown."""
        md = sample_result.to_markdown()

        assert "## Heisenberg" in md
        assert "AI Analysis" in md

    def test_markdown_includes_diagnosis(self, sample_result: AIAnalysisResult):
        """Markdown should include AI diagnosis."""
        md = sample_result.to_markdown()

        assert "Root Cause" in md
        assert "connection timeout" in md.lower()

    def test_markdown_includes_confidence(self, sample_result: AIAnalysisResult):
        """Markdown should show confidence level."""
        md = sample_result.to_markdown()

        assert "HIGH" in md or "Confidence" in md

    def test_markdown_includes_evidence(self, sample_result: AIAnalysisResult):
        """Markdown should show evidence."""
        md = sample_result.to_markdown()

        assert "Evidence" in md

    def test_markdown_includes_suggested_fix(self, sample_result: AIAnalysisResult):
        """Markdown should show suggested fix."""
        md = sample_result.to_markdown()

        assert "Fix" in md or "Suggested" in md

    def test_total_tokens(self):
        """Should calculate total tokens correctly."""
        result = AIAnalysisResult(
            diagnosis=MagicMock(),
            input_tokens=100,
            output_tokens=50,
        )

        assert result.total_tokens == 150

    def test_estimated_cost_default_anthropic(self):
        """Should calculate estimated cost with default Anthropic rates."""
        result = AIAnalysisResult(
            diagnosis=MagicMock(),
            input_tokens=1000,
            output_tokens=500,
        )

        # Anthropic (default): $3/M input, $15/M output
        expected_cost = (1000 * 3 / 1_000_000) + (500 * 15 / 1_000_000)
        assert result.estimated_cost == pytest.approx(expected_cost)

    def test_estimated_cost_openai_provider(self):
        """Should calculate estimated cost with OpenAI rates."""
        result = AIAnalysisResult(
            diagnosis=MagicMock(),
            input_tokens=1000,
            output_tokens=500,
            provider="openai",
        )

        # OpenAI: $5/M input, $15/M output
        expected_cost = (1000 * 5 / 1_000_000) + (500 * 15 / 1_000_000)
        assert result.estimated_cost == pytest.approx(expected_cost)

    def test_estimated_cost_google_provider(self):
        """Should calculate estimated cost with Google rates."""
        result = AIAnalysisResult(
            diagnosis=MagicMock(),
            input_tokens=1000,
            output_tokens=500,
            provider="google",
        )

        # Google: $2/M input, $12/M output
        expected_cost = (1000 * 2 / 1_000_000) + (500 * 12 / 1_000_000)
        assert result.estimated_cost == pytest.approx(expected_cost)

    def test_to_markdown_basic(self):
        """Should format as markdown correctly."""
        diagnosis = Diagnosis(
            root_cause="Database timeout",
            evidence=["Error in logs", "Slow query"],
            suggested_fix="Increase timeout",
            confidence=ConfidenceLevel.HIGH,
            confidence_explanation="Clear pattern",
            raw_response="raw",
        )

        result = AIAnalysisResult(
            diagnosis=diagnosis,
            input_tokens=500,
            output_tokens=200,
        )

        markdown = result.to_markdown()

        assert "## Heisenberg AI Analysis" in markdown
        assert "### Root Cause" in markdown
        assert "Database timeout" in markdown
        assert "### Evidence" in markdown
        assert "Error in logs" in markdown
        assert "### Suggested Fix" in markdown
        assert "Increase timeout" in markdown
        assert "**HIGH**" in markdown
        assert "Clear pattern" in markdown

    def test_to_markdown_no_evidence(self):
        """Should handle empty evidence list."""
        diagnosis = Diagnosis(
            root_cause="Unknown error",
            evidence=[],
            suggested_fix="Investigate",
            confidence=ConfidenceLevel.LOW,
            confidence_explanation=None,
            raw_response="raw",
        )

        result = AIAnalysisResult(
            diagnosis=diagnosis,
            input_tokens=100,
            output_tokens=50,
        )

        markdown = result.to_markdown()

        assert "### Evidence" not in markdown


class TestConvenienceFunction:
    """Test suite for analyze_with_ai helper."""

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_analyze_with_ai_returns_result(
        self, mock_get_client: MagicMock, sample_report: PlaywrightReport
    ):
        """Helper should return AIAnalysisResult."""
        mock_llm = MagicMock()
        mock_llm.analyze.return_value = LLMAnalysis(
            content=SAMPLE_AI_RESPONSE,
            input_tokens=500,
            output_tokens=200,
            model="claude-sonnet-4-20250514",
            provider="anthropic",
        )
        mock_get_client.return_value = mock_llm

        result = analyze_with_ai(sample_report, api_key="test-key")

        assert isinstance(result, AIAnalysisResult)

    @patch("heisenberg.core.analyzer._get_llm_client_for_provider")
    def test_analyze_with_ai_from_environment(
        self, mock_get_client: MagicMock, sample_report: PlaywrightReport, monkeypatch
    ):
        """Helper should read API key from environment."""
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

        result = analyze_with_ai(sample_report)

        assert isinstance(result, AIAnalysisResult)
        mock_get_client.assert_called_once()


class TestGetLLMClientForProvider:
    """Tests for _get_llm_client_for_provider function."""

    def test_claude_provider_with_api_key(self, mocker):
        """Should create Claude provider with API key."""
        mocker.patch("heisenberg.llm.providers.anthropic.AnthropicProvider")

        provider = _get_llm_client_for_provider("anthropic", api_key="test-key")

        from heisenberg.llm.providers import AnthropicProvider

        assert isinstance(provider, AnthropicProvider)

    def test_claude_provider_from_environment(self, mocker, monkeypatch):
        """Should create Claude provider from environment."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")

        provider = _get_llm_client_for_provider("anthropic")

        from heisenberg.llm.providers import AnthropicProvider

        assert isinstance(provider, AnthropicProvider)

    def test_openai_provider_with_api_key(self):
        """Should create OpenAI provider with API key."""
        provider = _get_llm_client_for_provider("openai", api_key="test-key")

        assert isinstance(provider, OpenAIProvider)

    def test_openai_provider_from_environment(self, monkeypatch):
        """Should create OpenAI provider from environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")

        provider = _get_llm_client_for_provider("openai")

        assert isinstance(provider, OpenAIProvider)

    def test_openai_provider_missing_key(self, monkeypatch):
        """Should raise error when OpenAI key is missing."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            _get_llm_client_for_provider("openai")

    def test_gemini_provider_with_api_key(self):
        """Should create Gemini provider with API key."""
        provider = _get_llm_client_for_provider("google", api_key="test-key")

        assert isinstance(provider, GeminiProvider)

    def test_gemini_provider_from_environment(self, monkeypatch):
        """Should create Gemini provider from environment."""
        monkeypatch.setenv("GOOGLE_API_KEY", "env-key")

        provider = _get_llm_client_for_provider("google")

        assert isinstance(provider, GeminiProvider)

    def test_gemini_provider_missing_key(self, monkeypatch):
        """Should raise error when Gemini key is missing."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
            _get_llm_client_for_provider("google")

    def test_unknown_provider(self):
        """Should raise error for unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            _get_llm_client_for_provider("unknown_provider")

    def test_custom_model_openai(self):
        """Should pass custom model to OpenAI provider."""
        provider = _get_llm_client_for_provider("openai", api_key="test-key", model="gpt-4-turbo")

        assert provider.model == "gpt-4-turbo"

    def test_custom_model_gemini(self):
        """Should pass custom model to Gemini provider."""
        provider = _get_llm_client_for_provider(
            "google", api_key="test-key", model="gemini-2.0-flash"
        )

        assert provider.model == "gemini-2.0-flash"


class TestAnalyzeUnifiedRun:
    """Tests for analyze_unified_run function."""

    @pytest.fixture
    def mock_unified_run(self):
        """Create a mock unified run with proper structure."""
        failure = UnifiedFailure(
            test_id="test-1",
            file_path="test.py",
            test_title="Test case",
            suite_path=["Suite"],
            error=ErrorInfo(
                message="Test failed",
                stack_trace="at line 10",
                location=None,
            ),
            metadata=FailureMetadata(
                framework=Framework.PLAYWRIGHT,
                browser=None,
                retry_count=0,
                duration_ms=100,
                tags=[],
            ),
        )

        return UnifiedTestRun(
            run_id="run-1",
            repository=None,
            branch=None,
            commit_sha=None,
            workflow_name=None,
            run_url=None,
            total_tests=1,
            passed_tests=0,
            failed_tests=1,
            skipped_tests=0,
            failures=[failure],
        )

    def test_analyze_unified_run_calls_llm(self, mock_unified_run, mocker, monkeypatch):
        """Should call LLM with built prompts."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.content = """
ROOT_CAUSE: Test assertion failed
EVIDENCE:
- Error message indicates assertion
SUGGESTED_FIX: Update test assertion
CONFIDENCE: HIGH
CONFIDENCE_EXPLANATION: Clear error pattern
"""
        mock_response.input_tokens = 100
        mock_response.output_tokens = 50

        mock_llm = MagicMock()
        mock_llm.analyze.return_value = mock_response

        mocker.patch(
            "heisenberg.core.analyzer._get_llm_client_for_provider",
            return_value=mock_llm,
        )

        result = analyze_unified_run(mock_unified_run)

        assert isinstance(result, AIAnalysisResult)
        assert result.input_tokens == 100
        assert result.output_tokens == 50

    def test_analyze_unified_run_with_context(self, mock_unified_run, mocker, monkeypatch):
        """Should pass additional context to prompt builder."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.content = """
ROOT_CAUSE: Database error
EVIDENCE:
- Connection timeout
SUGGESTED_FIX: Check DB connection
CONFIDENCE: MEDIUM
"""
        mock_response.input_tokens = 150
        mock_response.output_tokens = 75

        mock_llm = MagicMock()
        mock_llm.analyze.return_value = mock_response

        mocker.patch(
            "heisenberg.core.analyzer._get_llm_client_for_provider",
            return_value=mock_llm,
        )

        mock_build_prompt = mocker.patch(
            "heisenberg.llm.prompts.build_unified_prompt",
            return_value=("system", "user"),
        )

        analyze_unified_run(
            mock_unified_run,
            job_logs_context="Job logs here",
            screenshot_context="Screenshot analysis",
            trace_context="Trace details",
        )

        mock_build_prompt.assert_called_once()
        call_args = mock_build_prompt.call_args
        assert call_args[0][2] == "Job logs here"
        assert call_args[0][3] == "Screenshot analysis"
        assert call_args[0][4] == "Trace details"


class TestUnifiedPromptBuilder:
    """Tests for building AI prompts from UnifiedTestRun."""

    def test_build_prompt_from_unified_run(self):
        """Prompt builder creates valid prompt from UnifiedTestRun."""
        from heisenberg.llm.prompts import build_unified_prompt

        run = UnifiedTestRun(
            run_id="test-run-123",
            repository="owner/repo",
            branch="main",
            total_tests=10,
            passed_tests=8,
            failed_tests=2,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="tests/login.spec.ts",
                    test_title="should login successfully",
                    error=ErrorInfo(
                        message="Timeout waiting for selector '#submit'",
                        stack_trace="at login.spec.ts:15:5",
                    ),
                    metadata=FailureMetadata(
                        framework=Framework.PLAYWRIGHT,
                        browser="chromium",
                        duration_ms=30000,
                    ),
                ),
            ],
        )

        system_prompt, user_prompt = build_unified_prompt(run)

        assert "test failure" in system_prompt.lower()
        assert "diagnosis" in system_prompt.lower() or "analyze" in system_prompt.lower()

        assert "login.spec.ts" in user_prompt
        assert "should login successfully" in user_prompt
        assert "Timeout" in user_prompt
        assert "#submit" in user_prompt

    def test_build_prompt_includes_summary(self):
        """Prompt includes test run summary statistics."""
        from heisenberg.llm.prompts import build_unified_prompt

        run = UnifiedTestRun(
            run_id="run-1",
            total_tests=100,
            passed_tests=95,
            failed_tests=3,
            skipped_tests=2,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="test.ts",
                    test_title="test 1",
                    error=ErrorInfo(message="Error 1"),
                ),
            ],
        )

        _, user_prompt = build_unified_prompt(run)

        assert "100" in user_prompt
        assert "95" in user_prompt
        assert "3" in user_prompt

    def test_build_prompt_includes_metadata(self):
        """Prompt includes test metadata like browser and framework."""
        from heisenberg.llm.prompts import build_unified_prompt

        run = UnifiedTestRun(
            run_id="run-1",
            repository="microsoft/playwright",
            branch="feature/fix",
            total_tests=10,
            passed_tests=9,
            failed_tests=1,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="test.ts",
                    test_title="browser test",
                    error=ErrorInfo(message="Failed"),
                    metadata=FailureMetadata(
                        framework=Framework.PLAYWRIGHT,
                        browser="firefox",
                    ),
                ),
            ],
        )

        _, user_prompt = build_unified_prompt(run)

        assert "firefox" in user_prompt.lower()
        assert "playwright" in user_prompt.lower()

    def test_build_prompt_multiple_failures(self):
        """Prompt includes all failures when multiple exist."""
        from heisenberg.llm.prompts import build_unified_prompt

        run = UnifiedTestRun(
            run_id="run-1",
            total_tests=10,
            passed_tests=7,
            failed_tests=3,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="auth.spec.ts",
                    test_title="login test",
                    error=ErrorInfo(message="Login timeout"),
                ),
                UnifiedFailure(
                    test_id="2",
                    file_path="cart.spec.ts",
                    test_title="checkout test",
                    error=ErrorInfo(message="Cart empty error"),
                ),
                UnifiedFailure(
                    test_id="3",
                    file_path="profile.spec.ts",
                    test_title="profile test",
                    error=ErrorInfo(message="Profile not found"),
                ),
            ],
        )

        _, user_prompt = build_unified_prompt(run)

        assert "auth.spec.ts" in user_prompt
        assert "cart.spec.ts" in user_prompt
        assert "profile.spec.ts" in user_prompt
        assert "Login timeout" in user_prompt
        assert "Cart empty error" in user_prompt


class TestUnifiedAIAnalyzer:
    """Tests for AI analyzer with UnifiedTestRun input."""

    def test_analyze_unified_run(self):
        """AI analyzer accepts UnifiedTestRun and returns diagnosis."""
        run = UnifiedTestRun(
            run_id="test-123",
            total_tests=5,
            passed_tests=4,
            failed_tests=1,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="test.spec.ts",
                    test_title="should work",
                    error=ErrorInfo(message="Element not found"),
                    metadata=FailureMetadata(framework=Framework.PLAYWRIGHT),
                ),
            ],
        )

        with patch("heisenberg.core.analyzer._get_llm_client_for_provider") as mock_get_client:
            mock_client = MagicMock()
            mock_client.analyze.return_value = MagicMock(
                content="""
                ## Root Cause
                Element selector issue

                ## Evidence
                - Selector not found in DOM

                ## Suggested Fix
                Update selector

                ## Confidence
                HIGH
                """,
                input_tokens=100,
                output_tokens=50,
            )
            mock_get_client.return_value = mock_client

            result = analyze_unified_run(run)

            assert result.diagnosis.root_cause is not None
            assert result.input_tokens == 100
            assert result.output_tokens == 50

    def test_analyze_unified_with_provider(self):
        """AI analyzer respects provider parameter."""
        run = UnifiedTestRun(
            run_id="test-123",
            total_tests=1,
            passed_tests=0,
            failed_tests=1,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="test.ts",
                    test_title="test",
                    error=ErrorInfo(message="Error"),
                ),
            ],
        )

        with patch("heisenberg.core.analyzer._get_llm_client_for_provider") as mock_get_client:
            mock_client = MagicMock()
            mock_client.analyze.return_value = MagicMock(
                content="## Root Cause\nTest\n## Evidence\n- E\n## Suggested Fix\nF\n## Confidence\nHIGH",
                input_tokens=10,
                output_tokens=5,
            )
            mock_get_client.return_value = mock_client

            analyze_unified_run(run, provider="anthropic")

            mock_get_client.assert_called_with("anthropic", None, None)


class TestEndToEndUnifiedFlow:
    """End-to-end tests for unified model flow."""

    def test_playwright_to_unified_to_analysis(self):
        """Full flow: Playwright report -> UnifiedTestRun -> AI Analysis."""
        from heisenberg.core.models import PlaywrightTransformer
        from heisenberg.parsers.playwright import ErrorDetail, FailedTest, PlaywrightReport

        # 1. Create Playwright report
        report = PlaywrightReport(
            total_passed=9,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="checkout flow",
                    file="checkout.spec.ts",
                    suite="E2E",
                    project="chromium",
                    status="failed",
                    duration_ms=5000,
                    start_time=None,
                    errors=[
                        ErrorDetail(
                            message="Payment button not clickable",
                            stack="at checkout.spec.ts:42",
                        )
                    ],
                )
            ],
        )

        # 2. Transform to unified model
        unified_run = PlaywrightTransformer.transform_report(
            report,
            run_id="github-run-456",
            repository="shop/frontend",
        )

        assert unified_run.run_id == "github-run-456"
        assert len(unified_run.failures) == 1
        assert unified_run.failures[0].error.message == "Payment button not clickable"

        # 3. Analyze with AI (mocked)
        with patch("heisenberg.core.analyzer._get_llm_client_for_provider") as mock_get_client:
            mock_client = MagicMock()
            mock_client.analyze.return_value = MagicMock(
                content="""
                ## Root Cause
                Button disabled due to validation error

                ## Evidence
                - Payment form validation failing

                ## Suggested Fix
                Check form validation state before clicking

                ## Confidence
                MEDIUM
                """,
                input_tokens=200,
                output_tokens=100,
            )
            mock_get_client.return_value = mock_client

            result = analyze_unified_run(unified_run)

            assert "validation" in result.diagnosis.root_cause.lower()
