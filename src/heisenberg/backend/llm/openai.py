"""OpenAI LLM provider."""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from heisenberg.backend.llm.base import LLMProvider
from heisenberg.backend.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider(LLMProvider):
    """LLM provider for OpenAI's GPT models."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        max_tokens: int = 4096,
    ) -> None:
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key.
            model: Model name to use.
            max_tokens: Maximum tokens in response.
        """
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._client = AsyncOpenAI(api_key=api_key)

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "openai"

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Analyze test failure using OpenAI.

        Args:
            system_prompt: System prompt for GPT.
            user_prompt: User prompt containing test failure details.
            **kwargs: Additional arguments (model, max_tokens).

        Returns:
            Dictionary with response, input_tokens, output_tokens.
        """
        model = kwargs.get("model", self._model)
        max_tokens = kwargs.get("max_tokens", self._max_tokens)

        logger.debug(
            "openai_analyze_request",
            model=model,
            max_tokens=max_tokens,
        )

        response = await self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        result = {
            "response": response.choices[0].message.content,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "model": model,
        }

        logger.debug(
            "openai_analyze_response",
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
        )

        return result
