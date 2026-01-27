"""Adapter to make LLMRouter compatible with AnalyzeService."""

from __future__ import annotations

from typing import TYPE_CHECKING

from heisenberg.llm.models import LLMAnalysis

if TYPE_CHECKING:
    from heisenberg.llm.router import LLMRouter

# Backwards compatibility alias
LLMResponse = LLMAnalysis


class LLMRouterAdapter:
    """Adapter to make LLMRouter compatible with AnalyzeService's LLMClientProtocol."""

    def __init__(self, router: LLMRouter) -> None:
        """
        Initialize the adapter.

        Args:
            router: The LLMRouter to wrap.
        """
        self._router = router

    async def analyze(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LLMAnalysis:
        """
        Analyze prompt with LLM, adapting interface for AnalyzeService.

        Args:
            prompt: User prompt to analyze.
            system_prompt: Optional system prompt.

        Returns:
            LLMAnalysis with response content and token usage.
        """
        return await self._router.analyze_async(
            prompt,
            system_prompt=system_prompt,
        )
