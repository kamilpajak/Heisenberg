"""LLM cost tracking and budget management."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from heisenberg.llm.config import MODEL_PRICING

__all__ = ["CostCalculator", "check_budget_alert"]


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

    def get_supported_models(self) -> list[str]:
        """Get list of supported models."""
        return self.supported_models

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
