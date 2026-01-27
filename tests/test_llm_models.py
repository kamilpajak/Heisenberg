"""Tests for LLM models and pricing configuration.

Tests cover:
- LLMAnalysis dataclass structure and properties
- Token cost calculation
- Model pricing configuration
- Provider return type contracts
"""

from __future__ import annotations


class TestLLMAnalysisModel:
    """Test suite for shared LLMAnalysis model."""

    def test_llm_analysis_importable(self):
        """LLMAnalysis should be importable from heisenberg.llm.models."""
        from heisenberg.llm.models import LLMAnalysis

        assert LLMAnalysis is not None

    def test_llm_analysis_is_dataclass(self):
        """LLMAnalysis should be a dataclass."""
        import dataclasses

        from heisenberg.llm.models import LLMAnalysis

        assert dataclasses.is_dataclass(LLMAnalysis)

    def test_llm_analysis_required_fields(self):
        """LLMAnalysis should have required fields."""
        from heisenberg.llm.models import LLMAnalysis

        analysis = LLMAnalysis(
            content="Test response",
            input_tokens=100,
            output_tokens=50,
            model="claude-3-5-sonnet-20241022",
            provider="anthropic",
        )

        assert analysis.content == "Test response"
        assert analysis.input_tokens == 100
        assert analysis.output_tokens == 50
        assert analysis.model == "claude-3-5-sonnet-20241022"
        assert analysis.provider == "anthropic"

    def test_llm_analysis_total_tokens_property(self):
        """LLMAnalysis should have total_tokens property."""
        from heisenberg.llm.models import LLMAnalysis

        analysis = LLMAnalysis(
            content="Test",
            input_tokens=100,
            output_tokens=50,
            model="gpt-4o",
            provider="openai",
        )

        assert analysis.total_tokens == 150

    def test_llm_analysis_estimated_cost_property(self):
        """LLMAnalysis should have estimated_cost property."""
        from heisenberg.llm.models import LLMAnalysis

        analysis = LLMAnalysis(
            content="Test",
            input_tokens=1_000_000,  # 1M tokens
            output_tokens=1_000_000,  # 1M tokens
            model="claude-3-5-sonnet-20241022",
            provider="anthropic",
        )

        # Claude 3.5 Sonnet: $3/1M input, $15/1M output
        # Expected: $3 + $15 = $18
        assert analysis.estimated_cost == 18.0

    def test_llm_analysis_cost_for_different_models(self):
        """LLMAnalysis should calculate cost based on model pricing."""
        from heisenberg.llm.models import LLMAnalysis

        # GPT-4o: $2.5/1M input, $10/1M output
        analysis = LLMAnalysis(
            content="Test",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            model="gpt-4o",
            provider="openai",
        )

        # Expected: $2.5 + $10 = $12.5
        assert analysis.estimated_cost == 12.5

    def test_llm_analysis_cost_for_unknown_model_uses_defaults(self):
        """LLMAnalysis should use default pricing for unknown models."""
        from heisenberg.llm.models import LLMAnalysis

        analysis = LLMAnalysis(
            content="Test",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            model="unknown-model-2025",
            provider="unknown",
        )

        # Defaults: $3/1M input, $15/1M output
        assert analysis.estimated_cost == 18.0


class TestLLMPricing:
    """Test suite for LLM pricing configuration."""

    def test_pricing_dict_exists(self):
        """PRICING dictionary should exist in models module."""
        from collections.abc import Mapping

        from heisenberg.llm.models import PRICING

        assert isinstance(PRICING, Mapping)

    def test_pricing_has_claude_models(self):
        """PRICING should include Claude models."""
        from heisenberg.llm.models import PRICING

        assert "claude-3-5-sonnet-20241022" in PRICING
        assert "claude-sonnet-4-20250514" in PRICING

    def test_pricing_has_openai_models(self):
        """PRICING should include OpenAI models."""
        from heisenberg.llm.models import PRICING

        assert "gpt-4o" in PRICING
        assert "gpt-4o-mini" in PRICING

    def test_pricing_structure(self):
        """Each model pricing should have input and output costs."""
        from heisenberg.llm.models import PRICING

        for model, pricing in PRICING.items():
            assert "input" in pricing, f"Missing 'input' for {model}"
            assert "output" in pricing, f"Missing 'output' for {model}"
            assert isinstance(pricing["input"], (int, float))
            assert isinstance(pricing["output"], (int, float))


def _is_llm_analysis_annotation(annotation, llm_analysis_class) -> bool:
    """Check if annotation refers to LLMAnalysis (handles string annotations)."""
    if annotation is llm_analysis_class:
        return True
    if annotation == llm_analysis_class:
        return True
    # Handle string annotations from __future__ annotations
    if isinstance(annotation, str):
        return "LLMAnalysis" in annotation
    return False


class TestBackendProvidersReturnLLMAnalysis:
    """Test suite for backend providers returning LLMAnalysis."""

    def test_claude_provider_returns_llm_analysis(self):
        """ClaudeProvider.analyze() should return LLMAnalysis."""
        import inspect

        from heisenberg.backend.llm.claude import ClaudeProvider
        from heisenberg.llm.models import LLMAnalysis

        # Check return type annotation
        sig = inspect.signature(ClaudeProvider.analyze)
        return_annotation = sig.return_annotation

        # Should be LLMAnalysis (not dict)
        assert _is_llm_analysis_annotation(return_annotation, LLMAnalysis)

    def test_openai_provider_returns_llm_analysis(self):
        """OpenAIProvider.analyze() should return LLMAnalysis."""
        import inspect

        from heisenberg.backend.llm.openai import OpenAIProvider
        from heisenberg.llm.models import LLMAnalysis

        # Check return type annotation
        sig = inspect.signature(OpenAIProvider.analyze)
        return_annotation = sig.return_annotation

        # Should be LLMAnalysis (not dict)
        assert _is_llm_analysis_annotation(return_annotation, LLMAnalysis)

    def test_llm_router_returns_llm_analysis(self):
        """LLMRouter.analyze() should return LLMAnalysis."""
        import inspect

        from heisenberg.backend.llm.router import LLMRouter
        from heisenberg.llm.models import LLMAnalysis

        # Check return type annotation
        sig = inspect.signature(LLMRouter.analyze)
        return_annotation = sig.return_annotation

        # Should be LLMAnalysis (not dict)
        assert _is_llm_analysis_annotation(return_annotation, LLMAnalysis)

    def test_base_provider_returns_llm_analysis(self):
        """LLMProvider.analyze() should return LLMAnalysis in signature."""
        import inspect

        from heisenberg.backend.llm.base import LLMProvider
        from heisenberg.llm.models import LLMAnalysis

        # Check return type annotation
        sig = inspect.signature(LLMProvider.analyze)
        return_annotation = sig.return_annotation

        assert _is_llm_analysis_annotation(return_annotation, LLMAnalysis)


class TestCLIClientUsesLLMAnalysis:
    """Test suite for CLI client using shared LLMAnalysis."""

    def test_cli_client_returns_llm_analysis(self):
        """LLMClient.analyze() should return LLMAnalysis."""
        import inspect

        from heisenberg.llm.client import LLMClient
        from heisenberg.llm.models import LLMAnalysis

        # Check return type annotation
        sig = inspect.signature(LLMClient.analyze)
        return_annotation = sig.return_annotation

        assert _is_llm_analysis_annotation(return_annotation, LLMAnalysis)

    def test_llm_response_is_alias_to_llm_analysis(self):
        """LLMResponse should be an alias to LLMAnalysis for backwards compatibility."""
        from heisenberg.llm.client import LLMResponse
        from heisenberg.llm.models import LLMAnalysis

        # LLMResponse should be an alias to LLMAnalysis
        assert LLMResponse is LLMAnalysis
