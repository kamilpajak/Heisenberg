"""Shared LLM response models."""

from __future__ import annotations

from dataclasses import dataclass

# Pricing per million tokens (as of 2025)
PRICING: dict[str, dict[str, float]] = {
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
}

DEFAULT_INPUT_COST = 3.0
DEFAULT_OUTPUT_COST = 15.0


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
        input_cost_per_million = pricing.get("input", DEFAULT_INPUT_COST)
        output_cost_per_million = pricing.get("output", DEFAULT_OUTPUT_COST)

        input_cost = self.input_tokens * input_cost_per_million / 1_000_000
        output_cost = self.output_tokens * output_cost_per_million / 1_000_000
        return input_cost + output_cost
