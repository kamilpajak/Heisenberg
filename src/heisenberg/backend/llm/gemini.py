"""Google Gemini LLM provider.

.. deprecated::
    This module is deprecated. Use :mod:`heisenberg.llm.providers.gemini` instead.
"""

from __future__ import annotations

import warnings
from typing import Any

from heisenberg.llm.models import LLMAnalysis
from heisenberg.llm.providers.gemini import GeminiProvider as UnifiedGeminiProvider

__all__ = ["GeminiProvider"]

warnings.warn(
    "heisenberg.backend.llm.gemini is deprecated. Use heisenberg.llm.providers.gemini instead.",
    DeprecationWarning,
    stacklevel=2,
)


class GeminiProvider(UnifiedGeminiProvider):
    """LLM provider for Google's Gemini models.

    .. deprecated::
        Use :class:`heisenberg.llm.providers.gemini.GeminiProvider` instead.
    """

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> LLMAnalysis:
        """
        Analyze test failure using Gemini.

        This method maintains backwards compatibility with the old interface
        where system_prompt was the first positional argument.

        Args:
            system_prompt: System prompt for Gemini.
            user_prompt: User prompt containing test failure details.
            **kwargs: Additional arguments (model, max_tokens).

        Returns:
            LLMAnalysis with response content and token usage.
        """
        return await self.analyze_async(user_prompt, system_prompt=system_prompt)

    async def _call_api(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> LLMAnalysis:
        """Internal API call method for mocking in tests."""
        return await self.analyze(system_prompt, user_prompt, **kwargs)
