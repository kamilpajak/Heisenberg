"""Base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        ...

    @abstractmethod
    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Analyze test failure using the LLM.

        Args:
            system_prompt: System prompt for the LLM.
            user_prompt: User prompt containing test failure details.
            **kwargs: Additional provider-specific arguments.

        Returns:
            Dictionary with response, input_tokens, output_tokens.
        """
        ...
