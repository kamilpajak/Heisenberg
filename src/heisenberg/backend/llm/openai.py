"""OpenAI LLM provider.

.. deprecated::
    This module is deprecated. Use :mod:`heisenberg.llm.providers.openai` instead.
"""

from __future__ import annotations

import warnings
from typing import Any

from heisenberg.llm.models import LLMAnalysis
from heisenberg.llm.providers.openai import OpenAIProvider as UnifiedOpenAIProvider

__all__ = ["OpenAIProvider"]

warnings.warn(
    "heisenberg.backend.llm.openai is deprecated. Use heisenberg.llm.providers.openai instead.",
    DeprecationWarning,
    stacklevel=2,
)


class OpenAIProvider(UnifiedOpenAIProvider):
    """LLM provider for OpenAI's GPT models.

    .. deprecated::
        Use :class:`heisenberg.llm.providers.openai.OpenAIProvider` instead.
    """

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> LLMAnalysis:
        """
        Analyze test failure using OpenAI.

        This method maintains backwards compatibility with the old interface
        where system_prompt was the first positional argument.

        Args:
            system_prompt: System prompt for GPT.
            user_prompt: User prompt containing test failure details.
            **kwargs: Additional arguments (model, max_tokens).

        Returns:
            LLMAnalysis with response content and token usage.
        """
        return await self.analyze_async(user_prompt, system_prompt=system_prompt)
