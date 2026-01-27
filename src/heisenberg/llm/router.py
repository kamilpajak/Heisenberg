"""LLM router with fallback support for sync and async operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
from anthropic import APIError as AnthropicAPIError
from openai import APIError as OpenAIAPIError

from heisenberg.llm.models import LLMAnalysis

if TYPE_CHECKING:
    from heisenberg.llm.providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Exceptions that indicate recoverable API/network errors (should trigger fallback)
# Programming errors like TypeError, KeyError, AttributeError should propagate
LLM_RECOVERABLE_ERRORS: tuple[type[Exception], ...] = (
    AnthropicAPIError,
    OpenAIAPIError,
    httpx.RequestError,
    httpx.HTTPStatusError,
)

# Try to import Google API error if available
try:
    from google.api_core.exceptions import GoogleAPIError

    LLM_RECOVERABLE_ERRORS = (*LLM_RECOVERABLE_ERRORS, GoogleAPIError)
except ImportError:
    pass


class LLMRouter:
    """Routes LLM requests with automatic fallback on failure (sync + async)."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        """
        Initialize the router with ordered providers.

        Args:
            providers: List of providers in priority order (first is primary).

        Raises:
            ValueError: If no providers are provided.
        """
        if not providers:
            raise ValueError("At least one provider is required")

        self._providers = providers

    @property
    def providers(self) -> list[LLMProvider]:
        """Return the list of providers."""
        return self._providers

    def analyze(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> LLMAnalysis:
        """
        Analyze using providers with automatic fallback (synchronous).

        Args:
            user_prompt: User prompt containing the analysis request.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMAnalysis with response content, token usage, and provider info.

        Raises:
            Exception: If all providers fail.
        """
        last_error: Exception | None = None

        for provider in self._providers:
            try:
                logger.info("llm_router_attempt: provider=%s", provider.name)

                result = provider.analyze(
                    user_prompt,
                    system_prompt=system_prompt,
                )

                logger.info(
                    "llm_router_success: provider=%s, input_tokens=%d, output_tokens=%d",
                    provider.name,
                    result.input_tokens,
                    result.output_tokens,
                )

                return result

            except LLM_RECOVERABLE_ERRORS as e:
                last_error = e
                logger.warning(
                    "llm_router_fallback: failed_provider=%s, error=%s",
                    provider.name,
                    str(e),
                )
                continue

        # All providers failed
        logger.error(
            "llm_router_all_failed: providers=%s, last_error=%s",
            [p.name for p in self._providers],
            str(last_error),
        )

        if last_error:
            raise last_error
        raise RuntimeError("All LLM providers failed")

    async def analyze_async(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> LLMAnalysis:
        """
        Analyze using providers with automatic fallback (asynchronous).

        Args:
            user_prompt: User prompt containing the analysis request.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMAnalysis with response content, token usage, and provider info.

        Raises:
            Exception: If all providers fail.
        """
        last_error: Exception | None = None

        for provider in self._providers:
            try:
                logger.info("llm_router_async_attempt: provider=%s", provider.name)

                result = await provider.analyze_async(
                    user_prompt,
                    system_prompt=system_prompt,
                )

                logger.info(
                    "llm_router_async_success: provider=%s, input_tokens=%d, output_tokens=%d",
                    provider.name,
                    result.input_tokens,
                    result.output_tokens,
                )

                return result

            except LLM_RECOVERABLE_ERRORS as e:
                last_error = e
                logger.warning(
                    "llm_router_async_fallback: failed_provider=%s, error=%s",
                    provider.name,
                    str(e),
                )
                continue

        # All providers failed
        logger.error(
            "llm_router_async_all_failed: providers=%s, last_error=%s",
            [p.name for p in self._providers],
            str(last_error),
        )

        if last_error:
            raise last_error
        raise RuntimeError("All LLM providers failed")
