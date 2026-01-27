"""LLM client for AI-powered test failure analysis.

.. deprecated::
    This module is deprecated. Use :mod:`heisenberg.llm.providers` instead.
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass

import anthropic

from heisenberg.llm.models import LLMAnalysis
from heisenberg.llm.providers.anthropic import AnthropicProvider

# Backwards compatibility alias
LLMResponse = LLMAnalysis


class LLMClientError(Exception):
    """Exception raised for LLM client errors."""

    pass


@dataclass
class LLMConfig:
    """Configuration for LLM client.

    .. deprecated::
        Use :class:`heisenberg.llm.config.ProviderConfig` instead.
    """

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.3


class LLMClient:
    """Client for Anthropic Claude API.

    .. deprecated::
        Use :class:`heisenberg.llm.providers.anthropic.AnthropicProvider` instead.
    """

    def __init__(self, api_key: str, config: LLMConfig | None = None):
        """
        Initialize client with API key.

        Args:
            api_key: Anthropic API key.
            config: Optional LLM configuration.
        """
        warnings.warn(
            "LLMClient is deprecated. Use heisenberg.llm.providers.AnthropicProvider instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.api_key = api_key
        self.config = config or LLMConfig()
        self._provider: AnthropicProvider | None = None

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

    def _get_provider(self) -> AnthropicProvider:
        """Get or create Anthropic provider."""
        if self._provider is None:
            self._provider = AnthropicProvider(
                api_key=self.api_key,
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
        return self._provider

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
            LLMClientError: If API request fails.
        """
        provider = self._get_provider()

        try:
            return provider.analyze(prompt, system_prompt=system_prompt)
        except anthropic.APIError as e:
            raise LLMClientError(f"LLM API request failed: {e.message}") from e
