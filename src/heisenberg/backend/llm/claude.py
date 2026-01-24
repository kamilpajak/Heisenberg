"""Claude/Anthropic LLM provider."""

from __future__ import annotations

from typing import Any

from anthropic import AsyncAnthropic

from heisenberg.backend.llm.base import LLMProvider
from heisenberg.backend.logging import get_logger

logger = get_logger(__name__)


class ClaudeProvider(LLMProvider):
    """LLM provider for Anthropic's Claude models."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 4096,
    ) -> None:
        """
        Initialize Claude provider.

        Args:
            api_key: Anthropic API key.
            model: Model name to use.
            max_tokens: Maximum tokens in response.
        """
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._client = AsyncAnthropic(api_key=api_key)

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "claude"

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Analyze test failure using Claude.

        Args:
            system_prompt: System prompt for Claude.
            user_prompt: User prompt containing test failure details.
            **kwargs: Additional arguments (model, max_tokens).

        Returns:
            Dictionary with response, input_tokens, output_tokens.
        """
        model = kwargs.get("model", self._model)
        max_tokens = kwargs.get("max_tokens", self._max_tokens)

        logger.debug(
            "claude_analyze_request",
            model=model,
            max_tokens=max_tokens,
        )

        response = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        result = {
            "response": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": model,
        }

        logger.debug(
            "claude_analyze_response",
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
        )

        return result
