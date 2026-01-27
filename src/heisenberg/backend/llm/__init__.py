"""LLM provider abstraction layer.

.. deprecated::
    This module is deprecated. Use :mod:`heisenberg.llm.providers` instead.
"""

from __future__ import annotations

import warnings

# Re-export from new unified location (with backwards-compatible wrappers)
from heisenberg.backend.llm.claude import ClaudeProvider
from heisenberg.backend.llm.gemini import GeminiProvider
from heisenberg.backend.llm.openai import OpenAIProvider
from heisenberg.backend.llm.router import LLMRouter
from heisenberg.llm.providers.base import LLMProvider

__all__ = [
    "LLMProvider",
    "ClaudeProvider",
    "GeminiProvider",
    "OpenAIProvider",
    "LLMRouter",
    "create_provider",
]

# Suppress the warnings from submodule imports during package import
warnings.filterwarnings("ignore", message="heisenberg.backend.llm.*", category=DeprecationWarning)


def create_provider(provider_name: str, api_key: str) -> LLMProvider:
    """
    Factory function to create LLM providers.

    .. deprecated::
        Use :func:`heisenberg.llm.providers.create_provider` instead.

    Args:
        provider_name: Name of the provider ("anthropic", "openai", or "google").
        api_key: API key for the provider.

    Returns:
        LLMProvider instance (backwards-compatible wrapper).

    Raises:
        ValueError: If provider name is unknown.
    """
    warnings.warn(
        "heisenberg.backend.llm.create_provider is deprecated. "
        "Use heisenberg.llm.providers.create_provider instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    providers: dict[str, type] = {
        "anthropic": ClaudeProvider,
        "openai": OpenAIProvider,
        "google": GeminiProvider,
    }

    if provider_name not in providers:
        raise ValueError(f"Unknown provider: {provider_name}")

    return providers[provider_name](api_key=api_key)
