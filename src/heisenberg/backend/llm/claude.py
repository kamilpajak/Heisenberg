"""Claude/Anthropic LLM provider.

.. deprecated::
    This module is deprecated. Use :mod:`heisenberg.llm.providers.anthropic` instead.
"""

from __future__ import annotations

import warnings
from typing import Any

from heisenberg.llm.models import LLMAnalysis
from heisenberg.llm.providers.anthropic import AnthropicProvider

__all__ = ["ClaudeProvider"]

warnings.warn(
    "heisenberg.backend.llm.claude is deprecated. Use heisenberg.llm.providers.anthropic instead.",
    DeprecationWarning,
    stacklevel=2,
)


class ClaudeProvider(AnthropicProvider):
    """LLM provider for Anthropic's Claude models.

    .. deprecated::
        Use :class:`heisenberg.llm.providers.anthropic.AnthropicProvider` instead.
    """

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> LLMAnalysis:
        """
        Analyze test failure using Claude.

        This method maintains backwards compatibility with the old interface
        where system_prompt was the first positional argument.

        Args:
            system_prompt: System prompt for Claude.
            user_prompt: User prompt containing test failure details.
            **kwargs: Additional arguments (model, max_tokens).

        Returns:
            LLMAnalysis with response content and token usage.
        """
        return await self.analyze_async(user_prompt, system_prompt=system_prompt)
