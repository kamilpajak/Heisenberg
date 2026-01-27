"""Anthropic Claude LLM provider with dual-mode support."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from heisenberg.llm.config import PROVIDER_CONFIGS
from heisenberg.llm.models import LLMAnalysis

if TYPE_CHECKING:
    from anthropic import Anthropic, AsyncAnthropic

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """LLM provider for Anthropic's Claude models with sync + async support."""

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key.
            model: Model name to use. Defaults to config default.
            max_tokens: Maximum tokens in response. Defaults to config default.
            temperature: Temperature for sampling. Defaults to config default.
        """
        config = PROVIDER_CONFIGS["anthropic"]
        self._api_key = api_key
        self._model = model or config.default_model
        self._max_tokens = max_tokens if max_tokens is not None else config.max_tokens
        self._temperature = temperature if temperature is not None else config.temperature
        self._sync_client: Anthropic | None = None
        self._async_client: AsyncAnthropic | None = None

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "anthropic"

    @property
    def model(self) -> str:
        """Return the model name."""
        return self._model

    def _get_sync_client(self) -> Anthropic:
        """Get or create synchronous Anthropic client."""
        if self._sync_client is None:
            from anthropic import Anthropic

            self._sync_client = Anthropic(api_key=self._api_key)
        return self._sync_client

    def _get_async_client(self) -> AsyncAnthropic:
        """Get or create asynchronous Anthropic client."""
        if self._async_client is None:
            from anthropic import AsyncAnthropic

            self._async_client = AsyncAnthropic(api_key=self._api_key)
        return self._async_client

    def analyze(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> LLMAnalysis:
        """
        Analyze using Claude (synchronous).

        Args:
            user_prompt: User prompt containing the analysis request.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMAnalysis with response content and token usage.
        """
        client = self._get_sync_client()

        logger.debug(
            "anthropic_analyze_request: model=%s, max_tokens=%d",
            self._model,
            self._max_tokens,
        )

        kwargs: dict = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        response = client.messages.create(**kwargs)

        result = LLMAnalysis(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self._model,
            provider=self.name,
        )

        logger.debug(
            "anthropic_analyze_response: input_tokens=%d, output_tokens=%d",
            result.input_tokens,
            result.output_tokens,
        )

        return result

    async def analyze_async(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> LLMAnalysis:
        """
        Analyze using Claude (asynchronous).

        Args:
            user_prompt: User prompt containing the analysis request.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMAnalysis with response content and token usage.
        """
        client = self._get_async_client()

        logger.debug(
            "anthropic_analyze_async_request: model=%s, max_tokens=%d",
            self._model,
            self._max_tokens,
        )

        kwargs: dict = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        response = await client.messages.create(**kwargs)

        result = LLMAnalysis(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self._model,
            provider=self.name,
        )

        logger.debug(
            "anthropic_analyze_async_response: input_tokens=%d, output_tokens=%d",
            result.input_tokens,
            result.output_tokens,
        )

        return result
