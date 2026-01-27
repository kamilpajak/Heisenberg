"""LLM router with fallback support.

.. deprecated::
    This module is deprecated. Use :mod:`heisenberg.llm.router` instead.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

from heisenberg.llm.models import LLMAnalysis
from heisenberg.llm.router import LLM_RECOVERABLE_ERRORS
from heisenberg.llm.router import LLMRouter as UnifiedLLMRouter

if TYPE_CHECKING:
    pass

__all__ = ["LLMRouter", "LLM_RECOVERABLE_ERRORS"]

warnings.warn(
    "heisenberg.backend.llm.router is deprecated. Use heisenberg.llm.router instead.",
    DeprecationWarning,
    stacklevel=2,
)


class LLMRouter(UnifiedLLMRouter):
    """Routes LLM requests with automatic fallback on failure.

    .. deprecated::
        Use :class:`heisenberg.llm.router.LLMRouter` instead.
    """

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> LLMAnalysis:
        """
        Analyze using providers with automatic fallback.

        This method maintains backwards compatibility with the old interface
        where system_prompt was the first positional argument.

        Args:
            system_prompt: System prompt for the LLM.
            user_prompt: User prompt containing test failure details.
            **kwargs: Additional arguments passed to providers.

        Returns:
            LLMAnalysis with response content, token usage, and provider info.

        Raises:
            Exception: If all providers fail.
        """
        return await self.analyze_async(user_prompt, system_prompt=system_prompt)
