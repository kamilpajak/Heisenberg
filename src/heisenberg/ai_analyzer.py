"""AI-powered analyzer for test failure diagnosis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from heisenberg.diagnosis import Diagnosis, parse_diagnosis
from heisenberg.docker_logs import ContainerLogs
from heisenberg.llm_client import LLMClient, LLMResponse
from heisenberg.playwright_parser import PlaywrightReport
from heisenberg.prompt_builder import build_analysis_prompt

if TYPE_CHECKING:
    from heisenberg.unified_model import UnifiedTestRun

# Marker for AI-generated content
HEISENBERG_AI_MARKER = "## Heisenberg AI Analysis"


@dataclass
class AIAnalysisResult:
    """Result of AI-powered analysis."""

    diagnosis: Diagnosis
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost(self) -> float:
        """Estimate cost in USD (Claude 3.5 Sonnet pricing)."""
        input_cost = self.input_tokens * 3 / 1_000_000
        output_cost = self.output_tokens * 15 / 1_000_000
        return input_cost + output_cost

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


class AIAnalyzer:
    """AI-powered analyzer for test failures."""

    def __init__(
        self,
        report: PlaywrightReport,
        container_logs: dict[str, ContainerLogs] | None = None,
        api_key: str | None = None,
        provider: str = "claude",
        model: str | None = None,
    ):
        """
        Initialize AI analyzer.

        Args:
            report: Playwright test report.
            container_logs: Optional container logs for context.
            api_key: API key. If None, uses from_environment().
            provider: LLM provider (claude, openai, gemini).
            model: Specific model to use.
        """
        self.report = report
        self.container_logs = container_logs or {}
        self.api_key = api_key
        self.provider = provider
        self.model = model

    def analyze(self) -> AIAnalysisResult:
        """
        Run AI analysis on test failures.

        Returns:
            AIAnalysisResult with diagnosis and token usage.
        """
        # Build prompt
        system_prompt, user_prompt = build_analysis_prompt(
            self.report,
            container_logs=self.container_logs,
        )

        # Get LLM client based on provider
        llm = self._get_llm_client()

        # Call LLM
        response = llm.analyze(user_prompt, system_prompt=system_prompt)

        # Parse diagnosis
        diagnosis = parse_diagnosis(response.content)

        return AIAnalysisResult(
            diagnosis=diagnosis,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

    def _get_llm_client(self):
        """Get appropriate LLM client based on provider."""
        import os

        from heisenberg.llm_client import LLMConfig

        # Use appropriate client based on provider
        if self.provider == "claude":
            config = LLMConfig()
            if self.model:
                config.model = self.model
            # Use from_environment if no api_key provided (for mockability)
            if self.api_key:
                return LLMClient(api_key=self.api_key, config=config)
            else:
                return LLMClient.from_environment(config=config)
        elif self.provider == "openai":
            api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set.")
            return OpenAICompatibleClient(api_key=api_key, model=self.model)
        elif self.provider == "gemini":
            api_key = self.api_key or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable is not set.")
            return GeminiCompatibleClient(api_key=api_key, model=self.model)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")


class OpenAICompatibleClient:
    """OpenAI-compatible LLM client for CLI."""

    def __init__(self, api_key: str, model: str | None = None):
        self.api_key = api_key
        self.model = model or "gpt-4o"

    def analyze(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Send analysis request to OpenAI."""
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=4096,
            temperature=0.3,
        )

        return LLMResponse(
            content=response.choices[0].message.content or "",
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            model=self.model,
            provider="openai",
        )


class GeminiCompatibleClient:
    """Gemini-compatible LLM client for CLI."""

    def __init__(self, api_key: str, model: str | None = None):
        self.api_key = api_key
        self.model = model or "gemini-3-pro-preview"

    def analyze(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Send analysis request to Gemini."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)

        config = types.GenerateContentConfig(
            system_instruction=system_prompt or "",
            max_output_tokens=4096,
        )

        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        return LLMResponse(
            content=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model,
            provider="gemini",
        )


def analyze_with_ai(
    report: PlaywrightReport,
    container_logs: dict[str, ContainerLogs] | str | None = None,
    api_key: str | None = None,
    provider: str = "claude",
    model: str | None = None,
) -> AIAnalysisResult:
    """
    Convenience function for AI analysis.

    Args:
        report: Playwright test report.
        container_logs: Optional container logs (dict or string).
        api_key: Optional API key. If None, reads from environment.
        provider: LLM provider to use (claude, openai, gemini).
        model: Specific model to use (provider-dependent).

    Returns:
        AIAnalysisResult with diagnosis.
    """
    # Convert string logs to dict format if needed
    logs_dict = None
    if isinstance(container_logs, str):
        logs_dict = {"logs": type("Logs", (), {"entries": container_logs.split("\n")})()}
    elif container_logs:
        logs_dict = container_logs

    analyzer = AIAnalyzer(
        report=report,
        container_logs=logs_dict,
        api_key=api_key,
        provider=provider,
        model=model,
    )
    return analyzer.analyze()


def analyze_unified_run(
    run: UnifiedTestRun,
    container_logs: dict[str, ContainerLogs] | None = None,
    api_key: str | None = None,
    provider: str = "claude",
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
        provider: LLM provider to use (claude, openai, gemini).
        model: Specific model to use (provider-dependent).
        job_logs_context: Optional pre-formatted job logs snippets.
        screenshot_context: Optional pre-formatted screenshot descriptions.
        trace_context: Optional pre-formatted Playwright trace analysis.

    Returns:
        AIAnalysisResult with diagnosis.
    """
    from heisenberg.prompt_builder import build_unified_prompt

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
    )


def _get_llm_client_for_provider(
    provider: str,
    api_key: str | None = None,
    model: str | None = None,
):
    """Get LLM client for the specified provider."""
    import os

    from heisenberg.llm_client import LLMClient, LLMConfig

    if provider == "claude":
        config = LLMConfig()
        if model:
            config.model = model
        if api_key:
            return LLMClient(api_key=api_key, config=config)
        else:
            return LLMClient.from_environment(config=config)
    elif provider == "openai":
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        return OpenAICompatibleClient(api_key=api_key, model=model)
    elif provider == "gemini":
        api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set.")
        return GeminiCompatibleClient(api_key=api_key, model=model)
    else:
        raise ValueError(f"Unknown provider: {provider}")
