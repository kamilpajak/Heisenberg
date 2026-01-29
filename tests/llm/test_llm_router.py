"""Tests for LLM router with fallback support.

Consolidates router tests from:
- test_backend_multi_llm.py (TestLLMRouter, TestLLMRouterExceptionHandling)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from heisenberg.llm.models import LLMAnalysis
from tests.factories import make_llm_analysis


class TestLLMRouter:
    """Test suite for LLM router with fallback."""

    def test_llm_router_exists(self):
        """LLMRouter should be importable."""
        from heisenberg.llm.router import LLMRouter

        assert LLMRouter is not None

    def test_llm_router_accepts_providers(self):
        """LLMRouter should accept multiple providers."""
        from heisenberg.llm.providers.base import LLMProvider
        from heisenberg.llm.router import LLMRouter

        mock_provider1 = MagicMock(spec=LLMProvider)
        mock_provider1.name = "provider1"
        mock_provider2 = MagicMock(spec=LLMProvider)
        mock_provider2.name = "provider2"

        router = LLMRouter(providers=[mock_provider1, mock_provider2])

        assert len(router.providers) == 2

    @pytest.mark.asyncio
    async def test_llm_router_uses_primary_provider(self):
        """LLMRouter should use primary provider first."""
        from heisenberg.llm.providers.base import LLMProvider
        from heisenberg.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_primary.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="test", provider="primary")
        )

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock()

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        result = await router.analyze_async(
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

        from heisenberg.llm.providers.base import LLMProvider
        from heisenberg.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_primary.analyze_async = AsyncMock(side_effect=httpx.ConnectError("API error"))

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        result = await router.analyze_async(
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
        from heisenberg.llm.providers.base import LLMProvider
        from heisenberg.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "anthropic"
        mock_primary.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="test", provider="anthropic")
        )

        router = LLMRouter(providers=[mock_primary])

        result = await router.analyze_async(
            system_prompt="test",
            user_prompt="test",
        )

        assert isinstance(result, LLMAnalysis)
        assert result.provider == "anthropic"


class TestLLMRouterExceptionHandling:
    """Test suite for narrowed exception handling in LLMRouter.

    Tests that the router correctly catches recoverable API errors (rate limits,
    network issues) and falls back, while propagating programming errors.
    """

    @pytest.mark.asyncio
    async def test_router_catches_anthropic_api_error(self):
        """LLMRouter should catch and handle Anthropic API errors."""
        from anthropic import APIError as AnthropicAPIError

        from heisenberg.llm.providers.base import LLMProvider
        from heisenberg.llm.router import LLMRouter

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
        result = await router.analyze_async(system_prompt="test", user_prompt="test")

        assert result.content == "fallback response"
        mock_primary.analyze_async.assert_called_once()
        mock_fallback.analyze_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_router_catches_openai_api_error(self):
        """LLMRouter should catch and handle OpenAI API errors."""
        from openai import APIError as OpenAIAPIError

        from heisenberg.llm.providers.base import LLMProvider
        from heisenberg.llm.router import LLMRouter

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
        result = await router.analyze_async(system_prompt="test", user_prompt="test")

        assert result.content == "fallback response"

    @pytest.mark.asyncio
    async def test_router_catches_httpx_errors(self):
        """LLMRouter should catch and handle httpx network errors."""
        import httpx

        from heisenberg.llm.providers.base import LLMProvider
        from heisenberg.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_primary.analyze_async = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])
        result = await router.analyze_async(system_prompt="test", user_prompt="test")

        assert result.content == "fallback response"

    @pytest.mark.asyncio
    async def test_router_catches_google_api_error(self):
        """LLMRouter should catch and handle Google API errors."""
        pytest.importorskip("google.api_core")
        from google.api_core.exceptions import GoogleAPIError

        from heisenberg.llm.providers.base import LLMProvider
        from heisenberg.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_primary.analyze_async = AsyncMock(side_effect=GoogleAPIError("Quota exceeded"))

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(
            return_value=make_llm_analysis(content="fallback response", provider="fallback")
        )

        router = LLMRouter(providers=[mock_primary, mock_fallback])
        result = await router.analyze_async(system_prompt="test", user_prompt="test")

        assert result.content == "fallback response"

    @pytest.mark.asyncio
    async def test_router_propagates_programming_errors(self):
        """LLMRouter should NOT catch programming errors like TypeError."""
        from heisenberg.llm.providers.base import LLMProvider
        from heisenberg.llm.router import LLMRouter

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
            await router.analyze_async(system_prompt="test", user_prompt="test")

        mock_fallback.analyze_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_router_propagates_attribute_errors(self):
        """LLMRouter should NOT catch programming errors like AttributeError."""
        from heisenberg.llm.providers.base import LLMProvider
        from heisenberg.llm.router import LLMRouter

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
            await router.analyze_async(system_prompt="test", user_prompt="test")

        mock_fallback.analyze_async.assert_not_called()


class TestLLMRouterAllFail:
    """Test suite for router behavior when all providers fail."""

    @pytest.mark.asyncio
    async def test_router_raises_last_error_when_all_fail(self):
        """LLMRouter should raise the last error when all providers fail."""
        import httpx

        from heisenberg.llm.providers.base import LLMProvider
        from heisenberg.llm.router import LLMRouter

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.name = "primary"
        mock_primary.analyze_async = AsyncMock(side_effect=httpx.ConnectError("Primary failed"))

        mock_fallback = MagicMock(spec=LLMProvider)
        mock_fallback.name = "fallback"
        mock_fallback.analyze_async = AsyncMock(side_effect=httpx.ConnectError("Fallback failed"))

        router = LLMRouter(providers=[mock_primary, mock_fallback])

        with pytest.raises(httpx.ConnectError, match="Fallback failed"):
            await router.analyze_async(system_prompt="test", user_prompt="test")

        mock_primary.analyze_async.assert_called_once()
        mock_fallback.analyze_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_router_with_single_provider_raises_on_failure(self):
        """LLMRouter with single provider should raise on failure."""
        import httpx

        from heisenberg.llm.providers.base import LLMProvider
        from heisenberg.llm.router import LLMRouter

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.name = "single"
        mock_provider.analyze_async = AsyncMock(side_effect=httpx.ConnectError("API down"))

        router = LLMRouter(providers=[mock_provider])

        with pytest.raises(httpx.ConnectError, match="API down"):
            await router.analyze_async(system_prompt="test", user_prompt="test")
