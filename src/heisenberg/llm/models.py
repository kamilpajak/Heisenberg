"""Shared LLM response models."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from heisenberg.llm.config import (
    DEFAULT_INPUT_COST,
    DEFAULT_OUTPUT_COST,
    MODEL_PRICING,
)

# Pricing per million tokens - derived from config for backwards compatibility
# Uses float instead of Decimal for simpler cost estimation in LLMAnalysis
PRICING: MappingProxyType[str, MappingProxyType[str, float]] = MappingProxyType(
    {
        model: MappingProxyType(
            {"input": float(prices["input"]), "output": float(prices["output"])}
        )
        for model, prices in MODEL_PRICING.items()
    }
)


@dataclass
class LLMAnalysis:
    """Unified response from LLM analysis."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost(self) -> float:
        """Estimate cost in USD based on token usage."""
        pricing = PRICING.get(self.model, {})
        input_cost_per_million = pricing.get("input", float(DEFAULT_INPUT_COST))
        output_cost_per_million = pricing.get("output", float(DEFAULT_OUTPUT_COST))

        input_cost = self.input_tokens * input_cost_per_million / 1_000_000
        output_cost = self.output_tokens * output_cost_per_million / 1_000_000
        return input_cost + output_cost
