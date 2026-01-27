"""OpenAI LLM provider with dual-mode support."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from heisenberg.llm.config import PROVIDER_CONFIGS
from heisenberg.llm.models import LLMAnalysis

if TYPE_CHECKING:
    from openai import AsyncOpenAI, OpenAI

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """LLM provider for OpenAI's GPT models with sync + async support."""

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key.
            model: Model name to use. Defaults to config default.
            max_tokens: Maximum tokens in response. Defaults to config default.
            temperature: Temperature for sampling. Defaults to config default.
        """
        config = PROVIDER_CONFIGS["openai"]
        self._api_key = api_key
        self._model = model or config.default_model
        self._max_tokens = max_tokens if max_tokens is not None else config.max_tokens
        self._temperature = temperature if temperature is not None else config.temperature
        self._sync_client: OpenAI | None = None
        self._async_client: AsyncOpenAI | None = None

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "openai"

    @property
    def model(self) -> str:
        """Return the model name."""
        return self._model

    def _get_sync_client(self) -> OpenAI:
        """Get or create synchronous OpenAI client."""
        if self._sync_client is None:
            from openai import OpenAI

            self._sync_client = OpenAI(api_key=self._api_key)
        return self._sync_client

    def _get_async_client(self) -> AsyncOpenAI:
        """Get or create asynchronous OpenAI client."""
        if self._async_client is None:
            from openai import AsyncOpenAI

            self._async_client = AsyncOpenAI(api_key=self._api_key)
        return self._async_client

    def _build_messages(self, user_prompt: str, system_prompt: str | None) -> list[dict[str, str]]:
        """Build messages list for OpenAI API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        return messages

    def analyze(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> LLMAnalysis:
        """
        Analyze using OpenAI (synchronous).

        Args:
            user_prompt: User prompt containing the analysis request.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMAnalysis with response content and token usage.
        """
        client = self._get_sync_client()

        logger.debug(
            "openai_analyze_request: model=%s, max_tokens=%d",
            self._model,
            self._max_tokens,
        )

        response = client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            messages=self._build_messages(user_prompt, system_prompt),
        )

        result = LLMAnalysis(
            content=response.choices[0].message.content or "",
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            model=self._model,
            provider=self.name,
        )

        logger.debug(
            "openai_analyze_response: input_tokens=%d, output_tokens=%d",
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
        Analyze using OpenAI (asynchronous).

        Args:
            user_prompt: User prompt containing the analysis request.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMAnalysis with response content and token usage.
        """
        client = self._get_async_client()

        logger.debug(
            "openai_analyze_async_request: model=%s, max_tokens=%d",
            self._model,
            self._max_tokens,
        )

        response = await client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            messages=self._build_messages(user_prompt, system_prompt),
        )

        result = LLMAnalysis(
            content=response.choices[0].message.content or "",
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            model=self._model,
            provider=self.name,
        )

        logger.debug(
            "openai_analyze_async_response: input_tokens=%d, output_tokens=%d",
            result.input_tokens,
            result.output_tokens,
        )

        return result
