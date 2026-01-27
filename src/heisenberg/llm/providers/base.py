"""Base protocol for LLM providers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from heisenberg.llm.models import LLMAnalysis


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers with dual-mode (sync + async) support."""

    @property
    def name(self) -> str:
        """Return the provider name (e.g., 'anthropic', 'openai', 'google')."""
        ...

    def analyze(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> LLMAnalysis:
        """
        Analyze using the LLM (synchronous).

        Args:
            user_prompt: User prompt containing the analysis request.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMAnalysis with response content and token usage.
        """
        ...

    async def analyze_async(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> LLMAnalysis:
        """
        Analyze using the LLM (asynchronous).

        Args:
            user_prompt: User prompt containing the analysis request.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMAnalysis with response content and token usage.
        """
        ...
