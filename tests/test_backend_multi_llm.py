"""Tests for multi-LLM support with fallback - TDD for Phase 6."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from heisenberg.llm.models import LLMAnalysis
from tests.factories import make_llm_analysis


class TestLLMProvider:
    """Test suite for LLM provider abstraction."""

    def test_llm_provider_base_exists(self):
        """LLMProvider base class should be importable."""
        from heisenberg.backend.llm.base import LLMProvider

        assert LLMProvider is not None

    def test_llm_provider_has_analyze_method(self):
        """LLMProvider should define analyze method."""
        from heisenberg.backend.llm.base import LLMProvider

        assert hasattr(LLMProvider, "analyze")

    def test_llm_provider_has_name_property(self):
        """LLMProvider should have name property."""
        from heisenberg.backend.llm.base import LLMProvider

        assert hasattr(LLMProvider, "name")


class TestClaudeProvider:
    """Test suite for Claude provider."""

    def test_claude_provider_exists(self):
        """ClaudeProvider should be importable."""
        from heisenberg.backend.llm.claude import ClaudeProvider

        assert ClaudeProvider is not None

    def test_claude_provider_is_llm_provider(self):
        """ClaudeProvider should implement LLMProvider protocol."""
        from heisenberg.backend.llm.claude import ClaudeProvider
        from heisenberg.llm.providers.base import LLMProvider

        provider = ClaudeProvider(api_key="test-key")
        assert isinstance(provider, LLMProvider)

    def test_claude_provider_name(self):
        """ClaudeProvider should have correct name."""
        from heisenberg.backend.llm.claude import ClaudeProvider

        provider = ClaudeProvider(api_key="test-key")
        assert provider.name == "anthropic"

    @pytest.mark.asyncio
    async def test_claude_provider_analyze(self):
        """ClaudeProvider.analyze should call Anthropic API."""
        from heisenberg.backend.llm.claude import ClaudeProvider

        provider = ClaudeProvider(api_key="test-key")

        with patch.object(provider, "_get_async_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"root_cause": "test"}')]
            mock_response.usage.input_tokens = 100
            mock_response.usage.output_tokens = 50
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await provider.analyze(
                system_prompt="You are a test analyzer",
                user_prompt="Analyze this test failure",
            )

            assert result is not None
            mock_client.messages.create.assert_called_once()


class TestOpenAIProvider:
    """Test suite for OpenAI provider."""

    def test_openai_provider_exists(self):
        """OpenAIProvider should be importable."""
        from heisenberg.backend.llm.openai import OpenAIProvider

        assert OpenAIProvider is not None

    def test_openai_provider_is_llm_provider(self):
        """OpenAIProvider should implement LLMProvider protocol."""
        from heisenberg.backend.llm.openai import OpenAIProvider
        from heisenberg.llm.providers.base import LLMProvider

        provider = OpenAIProvider(api_key="test-key")
        assert isinstance(provider, LLMProvider)

    def test_openai_provider_name(self):
        """OpenAIProvider should have correct name."""
        from heisenberg.backend.llm.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")
        assert provider.name == "openai"


class TestLLMRouter:
    """Test suite for LLM router with fallback."""

    def test_llm_router_exists(self):
        """LLMRouter should be importable."""
        from heisenberg.backend.llm.router import LLMRouter

        assert LLMRouter is not None

    def test_llm_router_accepts_providers(self):
        """LLMRouter should accept multiple providers."""
        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_provider1 = MagicMock(spec=LLMProvider)
        mock_provider1.name = "provider1"
        mock_provider2 = MagicMock(spec=LLMProvider)
        mock_provider2.name = "provider2"

        router = LLMRouter(providers=[mock_provider1, mock_provider2])

        assert len(router.providers) == 2

    @pytest.mark.asyncio
    async def test_llm_router_uses_primary_provider(self):
        """LLMRouter should use primary provider first."""
        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_primary.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="test", provider="primary")
        )

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock()

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        result = await router.analyze(
            system_prompt="test",
            user_prompt="test",
        )

        assert result is not None
        assert isinstance(result, LLMAnalysis)
        mock_primary.analyze_async.assert_called_once()
        mock_fallback.analyze_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_router_falls_back_on_error(self):
        """LLMRouter should fall back to next provider on API error."""
        import httpx

        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        # Use a specific recoverable error (network error) instead of generic Exception
        mock_primary.analyze_async = AsyncMock(side_effect=httpx.ConnectError("API error"))

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        result = await router.analyze(
            system_prompt="test",
            user_prompt="test",
        )

        assert result is not None
        assert isinstance(result, LLMAnalysis)
        assert result.content == "fallback response"
        mock_primary.analyze_async.assert_called_once()
        mock_fallback.analyze_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_router_records_provider_used(self):
        """LLMRouter should record which provider was used."""
        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "anthropic"
        mock_primary.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="test", provider="anthropic")
        )

        router = LLMRouter(providers=[mock_primary])

        result = await router.analyze(
            system_prompt="test",
            user_prompt="test",
        )

        assert isinstance(result, LLMAnalysis)
        assert result.provider == "anthropic"


class TestLLMSettings:
    """Test suite for LLM configuration settings."""

    def test_settings_has_primary_provider(self):
        """Settings should have llm_primary_provider field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "llm_primary_provider")
        assert settings.llm_primary_provider == "anthropic"  # default

    def test_settings_has_fallback_provider(self):
        """Settings should have llm_fallback_provider field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "llm_fallback_provider")
        assert settings.llm_fallback_provider is None  # default

    def test_settings_has_openai_api_key(self):
        """Settings should have openai_api_key field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "openai_api_key")
        assert settings.openai_api_key is None  # default


class TestSettingsCaching:
    """Test suite for settings caching with @lru_cache."""

    @pytest.fixture
    def settings_env(self, monkeypatch):
        """Set required environment variables for Settings."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-testing")
        yield
        from heisenberg.backend.config import get_settings

        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()

    def test_get_settings_returns_same_instance(self, settings_env):
        """get_settings() should return the same cached instance."""
        from heisenberg.backend.config import get_settings

        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_get_settings_has_cache_clear(self):
        """get_settings() should have cache_clear method from lru_cache."""
        from heisenberg.backend.config import get_settings

        assert hasattr(get_settings, "cache_clear")
        assert callable(get_settings.cache_clear)

    def test_get_settings_has_cache_info(self):
        """get_settings() should have cache_info method from lru_cache."""
        from heisenberg.backend.config import get_settings

        assert hasattr(get_settings, "cache_info")
        assert callable(get_settings.cache_info)

    def test_cache_clear_creates_new_instance(self, settings_env):
        """cache_clear() should allow creating a new Settings instance."""
        from heisenberg.backend.config import get_settings

        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()

        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()

        assert settings1 is not settings2


class TestProviderFactory:
    """Test suite for LLM provider factory."""

    def test_factory_exists(self):
        """create_provider function should exist."""
        from heisenberg.backend.llm import create_provider

        assert create_provider is not None

    def test_factory_creates_claude(self):
        """Factory should create ClaudeProvider for 'claude'."""
        from heisenberg.backend.llm import create_provider
        from heisenberg.backend.llm.claude import ClaudeProvider

        provider = create_provider("anthropic", api_key="test-key")

        assert isinstance(provider, ClaudeProvider)

    def test_factory_creates_openai(self):
        """Factory should create OpenAIProvider for 'openai'."""
        from heisenberg.backend.llm import create_provider
        from heisenberg.backend.llm.openai import OpenAIProvider

        provider = create_provider("openai", api_key="test-key")

        assert isinstance(provider, OpenAIProvider)

    def test_factory_raises_for_unknown(self):
        """Factory should raise for unknown provider."""
        from heisenberg.backend.llm import create_provider

        with pytest.raises(ValueError, match="Unknown provider"):
            create_provider("unknown", api_key="test-key")


class TestLLMRouterExceptionHandling:
    """Test suite for narrowed exception handling in LLMRouter.

    Tests that the router correctly catches recoverable API errors (rate limits,
    network issues) and falls back, while propagating programming errors.
    """

    @pytest.mark.asyncio
    async def test_router_catches_anthropic_api_error(self):
        """LLMRouter should catch and handle Anthropic API errors."""
        from anthropic import APIError as AnthropicAPIError

        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_request = MagicMock()
        mock_primary.analyze_async = AsyncMock(
            side_effect=AnthropicAPIError(
                message="Rate limit exceeded",
                request=mock_request,
                body=None,
            )
        )

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])
        result = await router.analyze(system_prompt="test", user_prompt="test")

        assert result.content == "fallback response"
        mock_primary.analyze_async.assert_called_once()
        mock_fallback.analyze_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_router_catches_openai_api_error(self):
        """LLMRouter should catch and handle OpenAI API errors."""
        from openai import APIError as OpenAIAPIError

        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_request = MagicMock()
        mock_primary.analyze_async = AsyncMock(
            side_effect=OpenAIAPIError(
                message="Rate limit exceeded",
                request=mock_request,
                body=None,
            )
        )

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])
        result = await router.analyze(system_prompt="test", user_prompt="test")

        assert result.content == "fallback response"

    @pytest.mark.asyncio
    async def test_router_catches_httpx_errors(self):
        """LLMRouter should catch and handle httpx network errors."""
        import httpx

        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_primary.analyze_async = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])
        result = await router.analyze(system_prompt="test", user_prompt="test")

        assert result.content == "fallback response"

    @pytest.mark.asyncio
    async def test_router_catches_google_api_error(self):
        """LLMRouter should catch and handle Google API errors."""
        pytest.importorskip("google.api_core")
        from google.api_core.exceptions import GoogleAPIError

        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_primary.analyze_async = AsyncMock(side_effect=GoogleAPIError("Quota exceeded"))

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])
        result = await router.analyze(system_prompt="test", user_prompt="test")

        assert result.content == "fallback response"

    @pytest.mark.asyncio
    async def test_router_propagates_programming_errors(self):
        """LLMRouter should NOT catch programming errors like TypeError."""
        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_primary.analyze_async = AsyncMock(
            side_effect=TypeError("'NoneType' object is not subscriptable")
        )

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        with pytest.raises(TypeError, match="NoneType"):
            await router.analyze(system_prompt="test", user_prompt="test")

        mock_fallback.analyze_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_router_propagates_attribute_errors(self):
        """LLMRouter should NOT catch programming errors like AttributeError."""
        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_primary.analyze_async = AsyncMock(
            side_effect=AttributeError("'NoneType' object has no attribute 'text'")
        )

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        with pytest.raises(AttributeError, match="NoneType"):
            await router.analyze(system_prompt="test", user_prompt="test")

        mock_fallback.analyze_async.assert_not_called()
