"""LLM client for AI-powered test failure analysis."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import anthropic


class LLMClientError(Exception):
    """Exception raised for LLM client errors."""

    pass


@dataclass
class LLMConfig:
    """Configuration for LLM client."""

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.3


@dataclass
class LLMResponse:
    """Response from LLM analysis."""

    content: str
    input_tokens: int
    output_tokens: int

    # Claude 3.5 Sonnet pricing (per million tokens)
    INPUT_COST_PER_MILLION: float = field(default=3.0, repr=False)
    OUTPUT_COST_PER_MILLION: float = field(default=15.0, repr=False)

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost(self) -> float:
        """Estimate cost in USD based on token usage."""
        input_cost = self.input_tokens * self.INPUT_COST_PER_MILLION / 1_000_000
        output_cost = self.output_tokens * self.OUTPUT_COST_PER_MILLION / 1_000_000
        return input_cost + output_cost


class LLMClient:
    """Client for Anthropic Claude API."""

    def __init__(self, api_key: str, config: LLMConfig | None = None):
        """
        Initialize client with API key.

        Args:
            api_key: Anthropic API key.
            config: Optional LLM configuration.
        """
        self.api_key = api_key
        self.config = config or LLMConfig()
        self._client: anthropic.Anthropic | None = None

    @classmethod
    def from_environment(cls, config: LLMConfig | None = None) -> LLMClient:
        """
        Create client from ANTHROPIC_API_KEY environment variable.

        Args:
            config: Optional LLM configuration.

        Returns:
            LLMClient instance.

        Raises:
            ValueError: If ANTHROPIC_API_KEY is not set.
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Please provide an Anthropic API key for LLM analysis."
            )
        return cls(api_key=api_key, config=config)

    def _get_client(self) -> anthropic.Anthropic:
        """Get or create Anthropic client."""
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def analyze(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """
        Send analysis request to Claude.

        Args:
            prompt: The user prompt with test failure context.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMResponse with analysis result.

        Raises:
            Exception: If API request fails.
        """
        client = self._get_client()

        try:
            kwargs: dict = {
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "messages": [{"role": "user", "content": prompt}],
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            response = client.messages.create(**kwargs)

            return LLMResponse(
                content=response.content[0].text,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        except anthropic.APIError as e:
            raise LLMClientError(f"LLM API request failed: {e.message}") from e
