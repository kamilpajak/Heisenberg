"""AI-powered analyzer for test failure diagnosis."""

from __future__ import annotations

import os
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING

from heisenberg.core.diagnosis import Diagnosis, parse_diagnosis
from heisenberg.core.models import PlaywrightTransformer
from heisenberg.integrations.docker import ContainerLogs
from heisenberg.llm.config import PROVIDER_CONFIGS, calculate_cost

if TYPE_CHECKING:
    from heisenberg.core.models import UnifiedTestRun
    from heisenberg.parsers.playwright import PlaywrightReport

# Marker for AI-generated content
HEISENBERG_AI_MARKER = "## Heisenberg AI Analysis"


@dataclass
class AIAnalysisResult:
    """Result of AI-powered analysis."""

    diagnosis: Diagnosis
    input_tokens: int
    output_tokens: int
    provider: str = "google"
    model: str | None = None

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost(self) -> float:
        """Estimate cost in USD based on model pricing.

        Uses centralized pricing from llm/config.py. Falls back to provider's
        default model if specific model not set.
        """
        # Determine model for pricing lookup
        model = self.model
        if not model:
            # Fall back to provider's default model
            config = PROVIDER_CONFIGS.get(self.provider)
            model = config.default_model if config else "gemini-3-pro-preview"

        return float(calculate_cost(model, self.input_tokens, self.output_tokens))

    def to_markdown(self) -> str:
        """Format result as markdown for PR comment."""
        lines = [
            HEISENBERG_AI_MARKER,
            "",
            "### Root Cause",
            self.diagnosis.root_cause,
            "",
        ]

        if self.diagnosis.evidence:
            lines.append("### Evidence")
            for item in self.diagnosis.evidence:
                lines.append(f"- {item}")
            lines.append("")

        lines.extend(
            [
                "### Suggested Fix",
                self.diagnosis.suggested_fix,
                "",
                "### Confidence",
                f"**{self.diagnosis.confidence.value}**",
            ]
        )

        if self.diagnosis.confidence_explanation:
            lines.append(f"\n{self.diagnosis.confidence_explanation}")

        lines.extend(
            [
                "",
                "---",
                f"*Tokens: {self.total_tokens} | Est. cost: ${self.estimated_cost:.4f}*",
            ]
        )

        return "\n".join(lines)


def analyze_with_ai(
    report: PlaywrightReport,
    container_logs: dict[str, ContainerLogs] | str | None = None,
    api_key: str | None = None,
    provider: str = "google",
    model: str | None = None,
) -> AIAnalysisResult:
    """
    Convenience function for AI analysis.

    This function converts the PlaywrightReport to UnifiedTestRun and delegates
    to :func:`analyze_unified_run`. For new code, prefer using
    :func:`analyze_unified_run` directly with :class:`UnifiedTestRun`.

    Args:
        report: Playwright test report.
        container_logs: Optional container logs (dict or string).
        api_key: Optional API key. If None, reads from environment.
        provider: LLM provider to use (anthropic, openai, google).
        model: Specific model to use (provider-dependent).

    Returns:
        AIAnalysisResult with diagnosis.
    """
    # Convert string logs to dict format if needed
    logs_dict: dict[str, ContainerLogs] | None = None
    if isinstance(container_logs, str):
        logs_dict = {"logs": SimpleNamespace(entries=container_logs.split("\n"))}  # type: ignore[dict-item]
    elif container_logs:
        logs_dict = container_logs

    # Convert PlaywrightReport to UnifiedTestRun
    unified_run = PlaywrightTransformer.transform_report(report)

    # Delegate to unified analysis
    return analyze_unified_run(
        unified_run,
        container_logs=logs_dict,
        api_key=api_key,
        provider=provider,
        model=model,
    )


def analyze_unified_run(
    run: UnifiedTestRun,
    container_logs: dict[str, ContainerLogs] | None = None,
    api_key: str | None = None,
    provider: str = "google",
    model: str | None = None,
    job_logs_context: str | None = None,
    screenshot_context: str | None = None,
    trace_context: str | None = None,
) -> AIAnalysisResult:
    """
    Analyze test failures using the unified model.

    This is the framework-agnostic version of analyze_with_ai.
    It works with UnifiedTestRun instead of PlaywrightReport.

    Args:
        run: UnifiedTestRun containing test failures.
        container_logs: Optional container logs for context.
        api_key: Optional API key. If None, reads from environment.
        provider: LLM provider to use (anthropic, openai, google).
        model: Specific model to use (provider-dependent).
        job_logs_context: Optional pre-formatted job logs snippets.
        screenshot_context: Optional pre-formatted screenshot descriptions.
        trace_context: Optional pre-formatted Playwright trace analysis.

    Returns:
        AIAnalysisResult with diagnosis.
    """
    from heisenberg.llm.prompts import build_unified_prompt

    # Build prompts from unified model
    system_prompt, user_prompt = build_unified_prompt(
        run, container_logs, job_logs_context, screenshot_context, trace_context
    )

    # Get LLM client
    llm = _get_llm_client_for_provider(provider, api_key, model)

    # Call LLM
    response = llm.analyze(user_prompt, system_prompt=system_prompt)

    # Parse diagnosis
    diagnosis = parse_diagnosis(response.content)

    return AIAnalysisResult(
        diagnosis=diagnosis,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        provider=provider,
        model=getattr(response, "model", model),
    )


def _get_llm_client_for_provider(
    provider: str,
    api_key: str | None = None,
    model: str | None = None,
):
    """Get LLM client for the specified provider."""
    from heisenberg.llm.providers import create_provider

    # Get config for environment variable lookup
    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        valid = ", ".join(sorted(PROVIDER_CONFIGS.keys()))
        raise ValueError(f"Unknown provider: {provider}. Valid providers: {valid}")

    # Resolve API key from parameter or environment
    resolved_api_key = api_key or os.environ.get(config.env_var)
    if not resolved_api_key:
        raise ValueError(f"{config.env_var} environment variable is not set.")

    return create_provider(provider, resolved_api_key, model=model)
