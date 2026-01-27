"""Unified LLM provider abstraction layer."""

from __future__ import annotations

from heisenberg.llm.providers.anthropic import AnthropicProvider
from heisenberg.llm.providers.base import LLMProvider
from heisenberg.llm.providers.gemini import GeminiProvider
from heisenberg.llm.providers.openai import OpenAIProvider

__all__ = [
    "LLMProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "create_provider",
]


def create_provider(
    provider_name: str,
    api_key: str,
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> LLMProvider:
    """
    Factory function to create LLM providers.

    Args:
        provider_name: Name of the provider ("anthropic", "openai", or "google").
        api_key: API key for the provider.
        model: Optional model name override.
        max_tokens: Optional max tokens override.
        temperature: Optional temperature override.

    Returns:
        LLMProvider instance.

    Raises:
        ValueError: If provider name is unknown.
    """
    providers: dict[str, type] = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "google": GeminiProvider,
    }

    if provider_name not in providers:
        valid = ", ".join(sorted(providers.keys()))
        raise ValueError(f"Unknown provider: {provider_name}. Valid providers: {valid}")

    return providers[provider_name](
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
