"""Adapter to make LLMRouter compatible with AnalyzeService."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heisenberg.backend.llm.router import LLMRouter


@dataclass
class LLMResponse:
    """Response from LLM analysis, compatible with AnalyzeService."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str = ""
    provider: str = ""


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
    ) -> LLMResponse:
        """
        Analyze prompt with LLM, adapting interface for AnalyzeService.

        Args:
            prompt: User prompt to analyze.
            system_prompt: Optional system prompt.

        Returns:
            LLMResponse compatible with AnalyzeService.
        """
        result = await self._router.analyze(
            system_prompt=system_prompt or "",
            user_prompt=prompt,
        )

        return LLMResponse(
            content=result["response"],
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            model=result.get("model", ""),
            provider=result.get("provider", ""),
        )
