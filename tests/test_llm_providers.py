"""Tests for unified LLM providers.

Consolidates provider tests from:
- test_llm_gemini.py
- test_backend_multi_llm.py (provider sections)
- test_ai_analyzer_providers.py (provider sections)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLLMProviderBase:
    """Test suite for LLM provider base class/protocol."""

    def test_llm_provider_base_exists(self):
        """LLMProvider base class should be importable."""
        from heisenberg.llm.providers.base import LLMProvider

        assert LLMProvider is not None

    def test_llm_provider_has_analyze_method(self):
        """LLMProvider should define analyze method."""
        from heisenberg.llm.providers.base import LLMProvider

        assert hasattr(LLMProvider, "analyze")

    def test_llm_provider_has_analyze_async_method(self):
        """LLMProvider should define analyze_async method."""
        from heisenberg.llm.providers.base import LLMProvider

        assert hasattr(LLMProvider, "analyze_async")

    def test_llm_provider_has_name_property(self):
        """LLMProvider should have name property."""
        from heisenberg.llm.providers.base import LLMProvider

        assert hasattr(LLMProvider, "name")


class TestAnthropicProvider:
    """Test suite for Anthropic/Claude provider."""

    def test_claude_provider_exists(self):
        """AnthropicProvider should be importable."""
        from heisenberg.llm.providers import AnthropicProvider

        assert AnthropicProvider is not None

    def test_claude_provider_is_llm_provider(self):
        """AnthropicProvider should implement LLMProvider protocol."""
        from heisenberg.llm.providers import AnthropicProvider
        from heisenberg.llm.providers.base import LLMProvider

        provider = AnthropicProvider(api_key="test-key")
        assert isinstance(provider, LLMProvider)

    def test_claude_provider_name(self):
        """AnthropicProvider should have correct name."""
        from heisenberg.llm.providers import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key")
        assert provider.name == "anthropic"

    def test_claude_provider_default_model(self):
        """AnthropicProvider should have default model."""
        from heisenberg.llm.providers import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key")
        assert provider.model is not None
        assert "claude" in provider.model.lower()

    def test_claude_provider_custom_model(self):
        """AnthropicProvider should accept custom model."""
        from heisenberg.llm.providers import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key", model="claude-3-opus-20240229")
        assert provider.model == "claude-3-opus-20240229"

    @pytest.mark.asyncio
    async def test_claude_provider_analyze_async(self):
        """AnthropicProvider.analyze_async should call Anthropic API."""
        from heisenberg.llm.providers import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key")

        with patch.object(provider, "_get_async_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"root_cause": "test"}')]
            mock_response.usage.input_tokens = 100
            mock_response.usage.output_tokens = 50
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await provider.analyze_async(
                system_prompt="You are a test analyzer",
                user_prompt="Analyze this test failure",
            )

            assert result is not None
            mock_client.messages.create.assert_called_once()


class TestOpenAIProvider:
    """Test suite for OpenAI provider."""

    def test_openai_provider_exists(self):
        """OpenAIProvider should be importable."""
        from heisenberg.llm.providers import OpenAIProvider

        assert OpenAIProvider is not None

    def test_openai_provider_is_llm_provider(self):
        """OpenAIProvider should implement LLMProvider protocol."""
        from heisenberg.llm.providers import OpenAIProvider
        from heisenberg.llm.providers.base import LLMProvider

        provider = OpenAIProvider(api_key="test-key")
        assert isinstance(provider, LLMProvider)

    def test_openai_provider_name(self):
        """OpenAIProvider should have correct name."""
        from heisenberg.llm.providers import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")
        assert provider.name == "openai"

    def test_openai_provider_default_model(self):
        """Should use gpt-5 as default model."""
        from heisenberg.llm.providers import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")
        assert provider.model == "gpt-5"

    def test_openai_provider_custom_model(self):
        """Should accept custom model."""
        from heisenberg.llm.providers import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key", model="gpt-4-turbo")
        assert provider.model == "gpt-4-turbo"

    def test_openai_analyze_sync(self, mocker):
        """Should call OpenAI API correctly (sync)."""
        from heisenberg.llm.providers import OpenAIProvider

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

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

    def test_openai_analyze_without_system_prompt(self, mocker):
        """Should work without system prompt."""
        from heisenberg.llm.providers import OpenAIProvider

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

    def test_openai_analyze_handles_no_usage(self, mocker):
        """Should handle response without usage metadata."""
        from heisenberg.llm.providers import OpenAIProvider

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
    """Test suite for Google Gemini provider."""

    def test_gemini_provider_importable(self):
        """GeminiProvider should be importable from llm module."""
        from heisenberg.llm.providers import GeminiProvider

        assert GeminiProvider is not None

    def test_gemini_provider_in_all(self):
        """GeminiProvider should be in __all__."""
        from heisenberg.backend import llm

        assert "GeminiProvider" in llm.__all__

    def test_gemini_provider_requires_api_key(self):
        """GeminiProvider should require api_key."""
        from heisenberg.llm.providers import GeminiProvider

        with pytest.raises(TypeError):
            GeminiProvider()  # type: ignore

    def test_gemini_provider_accepts_api_key(self):
        """GeminiProvider should accept api_key parameter."""
        from heisenberg.llm.providers import GeminiProvider

        provider = GeminiProvider(api_key="test-key")
        assert provider is not None

    def test_gemini_provider_name(self):
        """GeminiProvider should have name 'google'."""
        from heisenberg.llm.providers import GeminiProvider

        provider = GeminiProvider(api_key="test-key")
        assert provider.name == "google"

    def test_gemini_provider_default_model(self):
        """Should use gemini-3-pro-preview as default model."""
        from heisenberg.llm.providers import GeminiProvider

        provider = GeminiProvider(api_key="test-key")
        assert provider.model == "gemini-3-pro-preview"

    def test_gemini_provider_custom_model(self):
        """GeminiProvider should accept custom model."""
        from heisenberg.llm.providers import GeminiProvider

        provider = GeminiProvider(api_key="test-key", model="gemini-2.0-flash")
        assert provider.model == "gemini-2.0-flash"

    def test_gemini_is_llm_provider(self):
        """GeminiProvider should inherit from LLMProvider."""
        from heisenberg.llm.providers import GeminiProvider
        from heisenberg.llm.providers.base import LLMProvider

        provider = GeminiProvider(api_key="test-key")
        assert isinstance(provider, LLMProvider)

    def test_gemini_has_analyze_method(self):
        """GeminiProvider should have analyze method."""
        from heisenberg.llm.providers import GeminiProvider

        provider = GeminiProvider(api_key="test-key")
        assert hasattr(provider, "analyze")
        assert callable(provider.analyze)

    def test_gemini_has_is_available_method(self):
        """GeminiProvider should have is_available method."""
        from heisenberg.llm.providers import GeminiProvider

        provider = GeminiProvider(api_key="test-key")
        assert hasattr(provider, "is_available")

    @pytest.mark.asyncio
    async def test_gemini_analyze_async_returns_llm_analysis(self, mocker):
        """analyze() should return LLMAnalysis."""
        from heisenberg.llm.providers import GeminiProvider

        mock_response = mocker.MagicMock()
        mock_response.text = "Test analysis result"
        mock_response.usage_metadata = mocker.MagicMock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20

        mock_aio_models = mocker.MagicMock()
        mock_aio_models.generate_content = mocker.AsyncMock(return_value=mock_response)

        mock_aio = mocker.MagicMock()
        mock_aio.models = mock_aio_models

        mock_client = mocker.MagicMock()
        mock_client.aio = mock_aio

        mocker.patch("google.genai.Client", return_value=mock_client)

        provider = GeminiProvider(api_key="test-key")

        result = await provider.analyze_async(
            system_prompt="You are a test analyst.",
            user_prompt="Analyze this test failure.",
        )

        from heisenberg.llm.models import LLMAnalysis

        assert isinstance(result, LLMAnalysis)
        assert result.content is not None

    @pytest.mark.asyncio
    async def test_gemini_analyze_async_returns_token_counts(self, mocker):
        """analyze() should return token counts."""
        from heisenberg.llm.providers import GeminiProvider

        mock_response = mocker.MagicMock()
        mock_response.text = "Analysis"
        mock_response.usage_metadata = mocker.MagicMock()
        mock_response.usage_metadata.prompt_token_count = 50
        mock_response.usage_metadata.candidates_token_count = 100

        mock_aio_models = mocker.MagicMock()
        mock_aio_models.generate_content = mocker.AsyncMock(return_value=mock_response)

        mock_aio = mocker.MagicMock()
        mock_aio.models = mock_aio_models

        mock_client = mocker.MagicMock()
        mock_client.aio = mock_aio

        mocker.patch("google.genai.Client", return_value=mock_client)

        provider = GeminiProvider(api_key="test-key")

        result = await provider.analyze_async(
            system_prompt="System",
            user_prompt="User",
        )

        assert result.input_tokens is not None
        assert result.output_tokens is not None
        assert result.input_tokens >= 0
        assert result.output_tokens >= 0

    @pytest.mark.asyncio
    async def test_gemini_analyze_async_returns_model_info(self, mocker):
        """analyze() should return model information."""
        from heisenberg.llm.providers import GeminiProvider

        mock_response = mocker.MagicMock()
        mock_response.text = "Analysis"
        mock_response.usage_metadata = mocker.MagicMock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20

        mock_aio_models = mocker.MagicMock()
        mock_aio_models.generate_content = mocker.AsyncMock(return_value=mock_response)

        mock_aio = mocker.MagicMock()
        mock_aio.models = mock_aio_models

        mock_client = mocker.MagicMock()
        mock_client.aio = mock_aio

        mocker.patch("google.genai.Client", return_value=mock_client)

        provider = GeminiProvider(api_key="test-key")

        result = await provider.analyze_async(
            system_prompt="System",
            user_prompt="User",
        )

        assert result.model is not None

    def test_gemini_analyze_sync(self, mocker):
        """Should call Gemini API correctly (sync)."""
        from heisenberg.llm.providers import GeminiProvider

        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50

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

    def test_gemini_analyze_handles_no_usage_metadata(self, mocker):
        """Should handle response without usage metadata."""
        from heisenberg.llm.providers import GeminiProvider

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


class TestProviderFactory:
    """Test suite for LLM provider factory."""

    def test_factory_exists(self):
        """create_provider function should exist."""
        from heisenberg.llm.providers import create_provider

        assert create_provider is not None

    def test_factory_creates_anthropic(self):
        """Factory should create AnthropicProvider for 'anthropic'."""
        from heisenberg.llm.providers import AnthropicProvider, create_provider

        provider = create_provider("anthropic", api_key="test-key")

        assert isinstance(provider, AnthropicProvider)

    def test_factory_creates_openai(self):
        """Factory should create OpenAIProvider for 'openai'."""
        from heisenberg.llm.providers import OpenAIProvider, create_provider

        provider = create_provider("openai", api_key="test-key")

        assert isinstance(provider, OpenAIProvider)

    def test_factory_creates_gemini(self):
        """create_provider should support 'google'."""
        from heisenberg.llm.providers import GeminiProvider, create_provider

        provider = create_provider("google", "test-key")
        assert isinstance(provider, GeminiProvider)

    def test_factory_raises_for_unknown(self):
        """Factory should raise for unknown provider."""
        from heisenberg.llm.providers import create_provider

        with pytest.raises(ValueError, match="Unknown provider"):
            create_provider("unknown", api_key="test-key")

    def test_factory_gemini_has_correct_name(self):
        """Created Gemini provider should have correct name."""
        from heisenberg.llm.providers import create_provider

        provider = create_provider("google", "test-key")
        assert provider.name == "google"


class TestGeminiConfig:
    """Test Gemini configuration in settings."""

    def test_settings_has_google_api_key(self):
        """Settings should have google_api_key field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test",
            secret_key="test-secret",
            google_api_key="test-key",
        )
        assert settings.google_api_key == "test-key"

    def test_settings_google_api_key_optional(self):
        """google_api_key should be optional."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test",
            secret_key="test-secret",
        )
        assert settings.google_api_key is None or settings.google_api_key == ""


class TestGeminiCostCalculation:
    """Test cost calculation for Gemini models."""

    def test_cost_calculator_has_gemini_pricing(self):
        """CostCalculator should have Gemini model pricing."""
        from heisenberg.backend.cost_tracking import CostCalculator

        calculator = CostCalculator()
        gemini_models = [m for m in calculator.get_supported_models() if "gemini" in m.lower()]
        assert len(gemini_models) > 0

    def test_cost_calculator_calculates_gemini_cost(self):
        """CostCalculator should calculate cost for Gemini models."""
        from heisenberg.backend.cost_tracking import CostCalculator

        calculator = CostCalculator()
        cost = calculator.calculate_cost(
            model_name="gemini-2.0-flash",
            input_tokens=1000,
            output_tokens=500,
        )
        assert cost >= 0
