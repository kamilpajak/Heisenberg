"""LLM provider abstraction layer."""

from __future__ import annotations

from heisenberg.backend.llm.base import LLMProvider
from heisenberg.backend.llm.claude import ClaudeProvider
from heisenberg.backend.llm.openai import OpenAIProvider
from heisenberg.backend.llm.router import LLMRouter

__all__ = [
    "LLMProvider",
    "ClaudeProvider",
    "OpenAIProvider",
    "LLMRouter",
    "create_provider",
]


def create_provider(provider_name: str, api_key: str) -> LLMProvider:
    """
    Factory function to create LLM providers.

    Args:
        provider_name: Name of the provider ("claude" or "openai").
        api_key: API key for the provider.

    Returns:
        LLMProvider instance.

    Raises:
        ValueError: If provider name is unknown.
    """
    providers = {
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
    }

    if provider_name not in providers:
        raise ValueError(f"Unknown provider: {provider_name}")

    return providers[provider_name](api_key=api_key)
