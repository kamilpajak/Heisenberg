"""LLM client for AI-powered test failure analysis."""

from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic

from heisenberg.llm.models import LLMAnalysis

# Backwards compatibility alias
LLMResponse = LLMAnalysis


class LLMClientError(Exception):
    """Exception raised for LLM client errors."""

    pass


@dataclass
class LLMConfig:
    """Configuration for LLM client."""

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.3


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
    ) -> LLMAnalysis:
        """
        Send analysis request to Claude.

        Args:
            prompt: The user prompt with test failure context.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMAnalysis with analysis result.

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

            return LLMAnalysis(
                content=response.content[0].text,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=self.config.model,
                provider="claude",
            )

        except anthropic.APIError as e:
            raise LLMClientError(f"LLM API request failed: {e.message}") from e
