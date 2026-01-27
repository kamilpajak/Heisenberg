"""Tests for Phase 1 refactoring - TDD approach.

Phase 1 includes:
1. Caching settings with @lru_cache
2. Narrowing exception handling in LLMRouter
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from heisenberg.llm.models import LLMAnalysis


def _mock_llm_analysis(
    content: str = "test",
    input_tokens: int = 100,
    output_tokens: int = 50,
    model: str = "test-model",
    provider: str = "test-provider",
) -> LLMAnalysis:
    """Create a mock LLMAnalysis for testing."""
    return LLMAnalysis(
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
        provider=provider,
    )


@pytest.fixture
def settings_env(monkeypatch):
    """Set required environment variables for Settings."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-testing")
    yield
    # Clear cache after test to avoid pollution
    from heisenberg.backend.config import get_settings

    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()


class TestSettingsCaching:
    """Test suite for settings caching with @lru_cache."""

    def test_get_settings_returns_same_instance(self, settings_env):
        """get_settings() should return the same cached instance."""
        from heisenberg.backend.config import get_settings

        # Clear cache if it exists
        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the exact same object (cached)
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

        # Clear and get first instance
        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()

        settings1 = get_settings()

        # Clear cache
        get_settings.cache_clear()

        # Get new instance
        settings2 = get_settings()

        # Should be different objects after cache clear
        assert settings1 is not settings2


class TestLLMRouterExceptionHandling:
    """Test suite for narrowed exception handling in LLMRouter."""

    @pytest.mark.asyncio
    async def test_router_catches_anthropic_api_error(self):
        """LLMRouter should catch and handle Anthropic API errors."""
        from anthropic import APIError as AnthropicAPIError

        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"

        # Create a proper Anthropic API error
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
            return_value=_mock_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        result = await router.analyze(
            system_prompt="test",
            user_prompt="test",
        )

        # Should have fallen back successfully
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

        # Create a proper OpenAI API error
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
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
            return_value=_mock_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        result = await router.analyze(
            system_prompt="test",
            user_prompt="test",
        )

        # Should have fallen back successfully
        assert result.content == "fallback response"
        mock_primary.analyze_async.assert_called_once()
        mock_fallback.analyze_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_router_catches_httpx_request_error(self):
        """LLMRouter should catch and handle httpx request errors."""
        import httpx

        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_primary.analyze_async = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(
            return_value=_mock_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        result = await router.analyze(
            system_prompt="test",
            user_prompt="test",
        )

        # Should have fallen back successfully
        assert result.content == "fallback response"

    @pytest.mark.asyncio
    async def test_router_catches_httpx_http_status_error(self):
        """LLMRouter should catch and handle httpx HTTP status errors."""
        import httpx

        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"

        # Create a proper HTTPStatusError
        mock_request = httpx.Request("POST", "https://api.example.com")
        mock_response = httpx.Response(500, request=mock_request)
        mock_primary.analyze_async = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error", request=mock_request, response=mock_response
            )
        )

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(
            return_value=_mock_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        result = await router.analyze(
            system_prompt="test",
            user_prompt="test",
        )

        # Should have fallen back successfully
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
            return_value=_mock_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        # Should propagate TypeError, not fall back
        with pytest.raises(TypeError, match="NoneType"):
            await router.analyze(
                system_prompt="test",
                user_prompt="test",
            )

        # Fallback should NOT have been called
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
            return_value=_mock_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        # Should propagate AttributeError, not fall back
        with pytest.raises(AttributeError, match="NoneType"):
            await router.analyze(
                system_prompt="test",
                user_prompt="test",
            )

        # Fallback should NOT have been called
        mock_fallback.analyze_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_router_propagates_key_errors(self):
        """LLMRouter should NOT catch programming errors like KeyError."""
        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.backend.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_primary.analyze_async = AsyncMock(side_effect=KeyError("missing_key"))

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(
            return_value=_mock_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        # Should propagate KeyError, not fall back
        with pytest.raises(KeyError, match="missing_key"):
            await router.analyze(
                system_prompt="test",
                user_prompt="test",
            )

        # Fallback should NOT have been called
        mock_fallback.analyze_async.assert_not_called()

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
            return_value=_mock_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        result = await router.analyze(
            system_prompt="test",
            user_prompt="test",
        )

        # Should have fallen back successfully
        assert result.content == "fallback response"
