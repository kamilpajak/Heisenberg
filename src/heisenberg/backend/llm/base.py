"""Base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from heisenberg.llm.models import LLMAnalysis


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
    ) -> LLMAnalysis:
        """
        Analyze test failure using the LLM.

        Args:
            system_prompt: System prompt for the LLM.
            user_prompt: User prompt containing test failure details.
            **kwargs: Additional provider-specific arguments.

        Returns:
            LLMAnalysis with response content and token usage.
        """
        ...
