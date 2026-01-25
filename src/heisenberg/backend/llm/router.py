"""LLM router with fallback support."""

from __future__ import annotations

from typing import Any

import httpx
from anthropic import APIError as AnthropicAPIError
from openai import APIError as OpenAIAPIError

from heisenberg.backend.llm.base import LLMProvider
from heisenberg.backend.logging import get_logger
from heisenberg.llm.models import LLMAnalysis

logger = get_logger(__name__)

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
    """Routes LLM requests with automatic fallback on failure."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        """
        Initialize the router with ordered providers.

        Args:
            providers: List of providers in priority order (first is primary).
        """
        if not providers:
            raise ValueError("At least one provider is required")

        self._providers = providers

    @property
    def providers(self) -> list[LLMProvider]:
        """Return the list of providers."""
        return self._providers

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> LLMAnalysis:
        """
        Analyze using providers with automatic fallback.

        Args:
            system_prompt: System prompt for the LLM.
            user_prompt: User prompt containing test failure details.
            **kwargs: Additional arguments passed to providers.

        Returns:
            LLMAnalysis with response content, token usage, and provider info.

        Raises:
            Exception: If all providers fail.
        """
        last_error: Exception | None = None

        for provider in self._providers:
            try:
                logger.info(
                    "llm_router_attempt",
                    provider=provider.name,
                )

                result = await provider.analyze(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    **kwargs,
                )

                logger.info(
                    "llm_router_success",
                    provider=provider.name,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                )

                return result

            except LLM_RECOVERABLE_ERRORS as e:
                last_error = e
                logger.warning(
                    "llm_router_fallback",
                    failed_provider=provider.name,
                    error=str(e),
                )
                continue

        # All providers failed
        logger.error(
            "llm_router_all_failed",
            providers=[p.name for p in self._providers],
            last_error=str(last_error),
        )

        if last_error:
            raise last_error
        raise RuntimeError("All LLM providers failed")
