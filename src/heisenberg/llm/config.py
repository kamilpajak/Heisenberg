"""Unified LLM configuration."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for an LLM provider."""

    default_model: str
    max_tokens: int = 4096
    temperature: float = 0.3
    env_var: str = ""


# Provider configurations - single source of truth
PROVIDER_CONFIGS: MappingProxyType[str, ProviderConfig] = MappingProxyType(
    {
        "anthropic": ProviderConfig(
            default_model="claude-sonnet-4-20250514",
            env_var="ANTHROPIC_API_KEY",
        ),
        "openai": ProviderConfig(
            default_model="gpt-5",
            env_var="OPENAI_API_KEY",
        ),
        "google": ProviderConfig(
            default_model="gemini-3-pro-preview",
            env_var="GOOGLE_API_KEY",
        ),
    }
)


# Model pricing per million tokens - single source of truth
# Using Decimal for precise cost calculations
MODEL_PRICING: MappingProxyType[str, MappingProxyType[str, Decimal]] = MappingProxyType(
    {
        # Claude models
        "claude-3-5-sonnet-20241022": MappingProxyType(
            {"input": Decimal("3.00"), "output": Decimal("15.00")}
        ),
        "claude-sonnet-4-20250514": MappingProxyType(
            {"input": Decimal("3.00"), "output": Decimal("15.00")}
        ),
        "claude-3-5-haiku-20241022": MappingProxyType(
            {"input": Decimal("1.00"), "output": Decimal("5.00")}
        ),
        "claude-3-opus-20240229": MappingProxyType(
            {"input": Decimal("15.00"), "output": Decimal("75.00")}
        ),
        # OpenAI models
        "gpt-5": MappingProxyType({"input": Decimal("2.50"), "output": Decimal("10.00")}),
        "gpt-4o": MappingProxyType({"input": Decimal("2.50"), "output": Decimal("10.00")}),
        "gpt-4o-mini": MappingProxyType({"input": Decimal("0.15"), "output": Decimal("0.60")}),
        "gpt-4-turbo": MappingProxyType({"input": Decimal("10.00"), "output": Decimal("30.00")}),
        # Gemini models
        "gemini-3-pro-preview": MappingProxyType(
            {"input": Decimal("1.25"), "output": Decimal("5.00")}
        ),
        "gemini-2.0-flash": MappingProxyType({"input": Decimal("0.10"), "output": Decimal("0.40")}),
        "gemini-1.5-pro": MappingProxyType({"input": Decimal("1.25"), "output": Decimal("5.00")}),
        "gemini-1.5-flash": MappingProxyType(
            {"input": Decimal("0.075"), "output": Decimal("0.30")}
        ),
    }
)

# Default costs per million tokens (fallback when model not in PRICING)
DEFAULT_INPUT_COST = Decimal("3.00")
DEFAULT_OUTPUT_COST = Decimal("15.00")


def get_model_pricing(model: str) -> tuple[Decimal, Decimal]:
    """
    Get input and output pricing for a model.

    Args:
        model: Model name.

    Returns:
        Tuple of (input_cost_per_million, output_cost_per_million).
    """
    pricing = MODEL_PRICING.get(model, {})
    input_cost = pricing.get("input", DEFAULT_INPUT_COST)
    output_cost = pricing.get("output", DEFAULT_OUTPUT_COST)
    return input_cost, output_cost


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """
    Calculate cost for a given model and token usage.

    Args:
        model: Model name.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.

    Returns:
        Cost in USD as Decimal.
    """
    input_cost_per_million, output_cost_per_million = get_model_pricing(model)

    input_cost = (Decimal(input_tokens) * input_cost_per_million) / Decimal("1000000")
    output_cost = (Decimal(output_tokens) * output_cost_per_million) / Decimal("1000000")

    return input_cost + output_cost
