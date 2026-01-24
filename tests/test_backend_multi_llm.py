"""Tests for multi-LLM support with fallback - TDD for Phase 6."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
        """ClaudeProvider should extend LLMProvider."""
        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.claude import ClaudeProvider

        assert issubclass(ClaudeProvider, LLMProvider)

    def test_claude_provider_name(self):
        """ClaudeProvider should have correct name."""
        from heisenberg.backend.llm.claude import ClaudeProvider

        provider = ClaudeProvider(api_key="test-key")
        assert provider.name == "claude"

    @pytest.mark.asyncio
    async def test_claude_provider_analyze(self):
        """ClaudeProvider.analyze should call Anthropic API."""
        from heisenberg.backend.llm.claude import ClaudeProvider

        provider = ClaudeProvider(api_key="test-key")

        with patch.object(provider, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"root_cause": "test"}')]
            mock_response.usage.input_tokens = 100
            mock_response.usage.output_tokens = 50
            mock_client.messages.create = AsyncMock(return_value=mock_response)

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
        """OpenAIProvider should extend LLMProvider."""
        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.openai import OpenAIProvider

        assert issubclass(OpenAIProvider, LLMProvider)

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
        mock_primary.analyze = AsyncMock(
            return_value={
                "response": "test",
                "input_tokens": 100,
                "output_tokens": 50,
            }
        )

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze = AsyncMock()

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        result = await router.analyze(
            system_prompt="test",
            user_prompt="test",
        )

        assert result is not None
        mock_primary.analyze.assert_called_once()
        mock_fallback.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_router_falls_back_on_error(self):
        """LLMRouter should fall back to next provider on error."""
        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_primary.analyze = AsyncMock(side_effect=Exception("API error"))

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze = AsyncMock(
            return_value={
                "response": "fallback response",
                "input_tokens": 100,
                "output_tokens": 50,
            }
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        result = await router.analyze(
            system_prompt="test",
            user_prompt="test",
        )

        assert result is not None
        assert result["response"] == "fallback response"
        mock_primary.analyze.assert_called_once()
        mock_fallback.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_router_records_provider_used(self):
        """LLMRouter should record which provider was used."""
        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "claude"
        mock_primary.analyze = AsyncMock(
            return_value={
                "response": "test",
                "input_tokens": 100,
                "output_tokens": 50,
            }
        )

        router = LLMRouter(providers=[mock_primary])

        result = await router.analyze(
            system_prompt="test",
            user_prompt="test",
        )

        assert "provider" in result
        assert result["provider"] == "claude"


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
        assert settings.llm_primary_provider == "claude"  # default

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

        provider = create_provider("claude", api_key="test-key")

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
