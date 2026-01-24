"""LLM cost tracking and budget management."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

# Model pricing per million tokens (as of Jan 2024)
MODEL_PRICING: dict[str, dict[str, Decimal]] = {
    # Claude models
    "claude-3-5-sonnet-20241022": {
        "input": Decimal("3.00"),
        "output": Decimal("15.00"),
    },
    "claude-3-5-haiku-20241022": {
        "input": Decimal("1.00"),
        "output": Decimal("5.00"),
    },
    "claude-3-opus-20240229": {
        "input": Decimal("15.00"),
        "output": Decimal("75.00"),
    },
    # OpenAI models
    "gpt-4o": {
        "input": Decimal("2.50"),
        "output": Decimal("10.00"),
    },
    "gpt-4o-mini": {
        "input": Decimal("0.15"),
        "output": Decimal("0.60"),
    },
    "gpt-4-turbo": {
        "input": Decimal("10.00"),
        "output": Decimal("30.00"),
    },
}


class CostCalculator:
    """Calculate LLM API costs based on token usage."""

    def __init__(self, pricing: dict[str, dict[str, Decimal]] | None = None) -> None:
        """
        Initialize the cost calculator.

        Args:
            pricing: Optional custom pricing dictionary. Uses defaults if not provided.
        """
        self._pricing = pricing or MODEL_PRICING

    @property
    def supported_models(self) -> list[str]:
        """Get list of supported models."""
        return list(self._pricing.keys())

    def calculate_cost(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Decimal:
        """
        Calculate the cost for a given model and token usage.

        Args:
            model_name: Name of the LLM model used.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.

        Returns:
            Cost in USD as Decimal.
        """
        if model_name not in self._pricing:
            return Decimal("0")

        pricing = self._pricing[model_name]
        input_cost = (Decimal(input_tokens) * pricing["input"]) / Decimal("1000000")
        output_cost = (Decimal(output_tokens) * pricing["output"]) / Decimal("1000000")

        return input_cost + output_cost


def check_budget_alert(
    current_spend: Decimal,
    threshold: Decimal,
) -> dict[str, Any]:
    """
    Check if spending has exceeded budget threshold.

    Args:
        current_spend: Current spending amount in USD.
        threshold: Budget threshold in USD.

    Returns:
        Dictionary with alert status and percentage.
    """
    if threshold <= 0:
        return {
            "alert": False,
            "percentage": 0.0,
            "message": "No budget threshold set",
        }

    percentage = float((current_spend / threshold) * 100)
    alert = current_spend >= threshold

    return {
        "alert": alert,
        "percentage": round(percentage, 1),
        "current_spend": str(current_spend),
        "threshold": str(threshold),
        "message": "Budget threshold exceeded" if alert else "Within budget",
    }
