"""Tests for Gemini LLM provider - TDD."""

import pytest


class TestGeminiProviderExists:
    """Test that Gemini provider exists and can be imported."""

    def test_gemini_provider_importable(self):
        """GeminiProvider should be importable from llm module."""
        from heisenberg.backend.llm import GeminiProvider

        assert GeminiProvider is not None

    def test_gemini_provider_in_all(self):
        """GeminiProvider should be in __all__."""
        from heisenberg.backend import llm

        assert "GeminiProvider" in llm.__all__


class TestGeminiProviderInit:
    """Test Gemini provider initialization."""

    def test_gemini_provider_requires_api_key(self):
        """GeminiProvider should require api_key."""
        from heisenberg.backend.llm import GeminiProvider

        with pytest.raises(TypeError):
            GeminiProvider()  # type: ignore

    def test_gemini_provider_accepts_api_key(self):
        """GeminiProvider should accept api_key parameter."""
        from heisenberg.backend.llm import GeminiProvider

        provider = GeminiProvider(api_key="test-key")
        assert provider is not None

    def test_gemini_provider_has_name(self):
        """GeminiProvider should have name 'gemini'."""
        from heisenberg.backend.llm import GeminiProvider

        provider = GeminiProvider(api_key="test-key")
        assert provider.name == "gemini"

    def test_gemini_provider_accepts_model(self):
        """GeminiProvider should accept custom model."""
        from heisenberg.backend.llm import GeminiProvider

        provider = GeminiProvider(api_key="test-key", model="gemini-2.0-flash")
        assert provider.model == "gemini-2.0-flash"

    def test_gemini_provider_default_model(self):
        """GeminiProvider should have default model."""
        from heisenberg.backend.llm import GeminiProvider

        provider = GeminiProvider(api_key="test-key")
        assert provider.model is not None
        assert "gemini" in provider.model.lower()


class TestGeminiProviderInterface:
    """Test Gemini provider implements LLMProvider interface."""

    def test_gemini_is_llm_provider(self):
        """GeminiProvider should inherit from LLMProvider."""
        from heisenberg.backend.llm import GeminiProvider
        from heisenberg.backend.llm.base import LLMProvider

        provider = GeminiProvider(api_key="test-key")
        assert isinstance(provider, LLMProvider)

    def test_gemini_has_analyze_method(self):
        """GeminiProvider should have analyze method."""
        from heisenberg.backend.llm import GeminiProvider

        provider = GeminiProvider(api_key="test-key")
        assert hasattr(provider, "analyze")
        assert callable(provider.analyze)

    def test_gemini_has_is_available_method(self):
        """GeminiProvider should have is_available method."""
        from heisenberg.backend.llm import GeminiProvider

        provider = GeminiProvider(api_key="test-key")
        assert hasattr(provider, "is_available")


class TestGeminiProviderAnalyze:
    """Test Gemini provider analyze method (mocked)."""

    @pytest.mark.asyncio
    async def test_analyze_returns_dict(self, mocker):
        """analyze() should return a dict with response."""
        from heisenberg.backend.llm import GeminiProvider

        # Mock the genai.Client before creating provider
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

        mocker.patch("heisenberg.backend.llm.gemini.genai.Client", return_value=mock_client)

        provider = GeminiProvider(api_key="test-key")

        result = await provider.analyze(
            system_prompt="You are a test analyst.",
            user_prompt="Analyze this test failure.",
        )

        from heisenberg.llm.models import LLMAnalysis

        assert isinstance(result, LLMAnalysis)
        assert result.content is not None

    @pytest.mark.asyncio
    async def test_analyze_returns_token_counts(self, mocker):
        """analyze() should return token counts."""
        from heisenberg.backend.llm import GeminiProvider

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

        mocker.patch("heisenberg.backend.llm.gemini.genai.Client", return_value=mock_client)

        provider = GeminiProvider(api_key="test-key")

        result = await provider.analyze(
            system_prompt="System",
            user_prompt="User",
        )

        assert result.input_tokens is not None
        assert result.output_tokens is not None
        assert result.input_tokens >= 0
        assert result.output_tokens >= 0

    @pytest.mark.asyncio
    async def test_analyze_returns_model_info(self, mocker):
        """analyze() should return model information."""
        from heisenberg.backend.llm import GeminiProvider

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

        mocker.patch("heisenberg.backend.llm.gemini.genai.Client", return_value=mock_client)

        provider = GeminiProvider(api_key="test-key")

        result = await provider.analyze(
            system_prompt="System",
            user_prompt="User",
        )

        assert result.model is not None


class TestGeminiFactoryFunction:
    """Test that factory function supports Gemini."""

    def test_create_provider_supports_gemini(self):
        """create_provider should support 'gemini'."""
        from heisenberg.backend.llm import GeminiProvider, create_provider

        provider = create_provider("gemini", "test-key")
        assert isinstance(provider, GeminiProvider)

    def test_create_provider_gemini_has_correct_name(self):
        """Created Gemini provider should have correct name."""
        from heisenberg.backend.llm import create_provider

        provider = create_provider("gemini", "test-key")
        assert provider.name == "gemini"


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
        # Check that at least one Gemini model is in pricing
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
