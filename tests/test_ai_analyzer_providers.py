"""Tests for AI analyzer provider-specific clients."""

from unittest.mock import MagicMock

import pytest

from heisenberg.core.analyzer import (
    AIAnalysisResult,
    _get_llm_client_for_provider,
    analyze_unified_run,
)
from heisenberg.core.diagnosis import ConfidenceLevel, Diagnosis
from heisenberg.llm.providers import GeminiProvider, OpenAIProvider


class TestOpenAIProvider:
    """Tests for OpenAI provider."""

    def test_init_default_model(self):
        """Should use gpt-5 as default model."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.model == "gpt-5"

    def test_init_custom_model(self):
        """Should accept custom model."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4-turbo")
        assert provider.model == "gpt-4-turbo"

    def test_analyze_calls_openai(self, mocker):
        """Should call OpenAI API correctly."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        # Patch at the import location inside the method
        mock_client_class = mocker.patch("openai.OpenAI")
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_class.return_value = mock_client

        provider = OpenAIProvider(api_key="test-key")
        result = provider.analyze("Test prompt", system_prompt="System prompt")

        assert result.content == "Test response"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.provider == "openai"

    def test_analyze_without_system_prompt(self, mocker):
        """Should work without system prompt."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 25

        mock_client_class = mocker.patch("openai.OpenAI")
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_class.return_value = mock_client

        provider = OpenAIProvider(api_key="test-key")
        result = provider.analyze("Test prompt")

        assert result.content == "Response"

    def test_analyze_handles_no_usage(self, mocker):
        """Should handle response without usage metadata."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage = None

        mock_client_class = mocker.patch("openai.OpenAI")
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_class.return_value = mock_client

        provider = OpenAIProvider(api_key="test-key")
        result = provider.analyze("Test prompt")

        assert result.input_tokens == 0
        assert result.output_tokens == 0


class TestGeminiProvider:
    """Tests for Gemini provider."""

    def test_init_default_model(self):
        """Should use gemini-3-pro-preview as default model."""
        provider = GeminiProvider(api_key="test-key")
        assert provider.model == "gemini-3-pro-preview"

    def test_init_custom_model(self):
        """Should accept custom model."""
        provider = GeminiProvider(api_key="test-key", model="gemini-2.0-flash")
        assert provider.model == "gemini-2.0-flash"

    def test_analyze_calls_gemini(self, mocker):
        """Should call Gemini API correctly."""
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50

        # Patch at the import location (google.genai)
        mock_client_class = mocker.patch("google.genai.Client")
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        provider = GeminiProvider(api_key="test-key")
        result = provider.analyze("Test prompt", system_prompt="System prompt")

        assert result.content == "Test response"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.provider == "google"

    def test_analyze_handles_no_usage_metadata(self, mocker):
        """Should handle response without usage metadata."""
        mock_response = MagicMock()
        mock_response.text = "Response"
        mock_response.usage_metadata = None

        mock_client_class = mocker.patch("google.genai.Client")
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        provider = GeminiProvider(api_key="test-key")
        result = provider.analyze("Test prompt")

        assert result.input_tokens == 0
        assert result.output_tokens == 0


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
        from heisenberg.core.models import (
            ErrorInfo,
            FailureMetadata,
            Framework,
            UnifiedFailure,
            UnifiedTestRun,
        )

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

        # Verify context was passed to prompt builder
        mock_build_prompt.assert_called_once()
        call_args = mock_build_prompt.call_args
        assert call_args[0][2] == "Job logs here"
        assert call_args[0][3] == "Screenshot analysis"
        assert call_args[0][4] == "Trace details"


class TestAIAnalysisResult:
    """Tests for AIAnalysisResult dataclass."""

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
