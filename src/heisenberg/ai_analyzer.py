"""AI-powered analyzer for test failure diagnosis."""

from __future__ import annotations

from dataclasses import dataclass

from heisenberg.diagnosis import Diagnosis, parse_diagnosis
from heisenberg.docker_logs import ContainerLogs
from heisenberg.llm_client import LLMClient
from heisenberg.playwright_parser import PlaywrightReport
from heisenberg.prompt_builder import build_analysis_prompt

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

        lines.extend([
            "### Suggested Fix",
            self.diagnosis.suggested_fix,
            "",
            "### Confidence",
            f"**{self.diagnosis.confidence.value}**",
        ])

        if self.diagnosis.confidence_explanation:
            lines.append(f"\n{self.diagnosis.confidence_explanation}")

        lines.extend([
            "",
            "---",
            f"*Tokens: {self.total_tokens} | Est. cost: ${self.estimated_cost:.4f}*",
        ])

        return "\n".join(lines)


class AIAnalyzer:
    """AI-powered analyzer for test failures."""

    def __init__(
        self,
        report: PlaywrightReport,
        container_logs: dict[str, ContainerLogs] | None = None,
        api_key: str | None = None,
    ):
        """
        Initialize AI analyzer.

        Args:
            report: Playwright test report.
            container_logs: Optional container logs for context.
            api_key: Anthropic API key. If None, uses from_environment().
        """
        self.report = report
        self.container_logs = container_logs or {}
        self.api_key = api_key

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

        # Get LLM client
        if self.api_key:
            llm = LLMClient(api_key=self.api_key)
        else:
            llm = LLMClient.from_environment()

        # Call LLM
        response = llm.analyze(user_prompt, system_prompt=system_prompt)

        # Parse diagnosis
        diagnosis = parse_diagnosis(response.content)

        return AIAnalysisResult(
            diagnosis=diagnosis,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )


def analyze_with_ai(
    report: PlaywrightReport,
    container_logs: dict[str, ContainerLogs] | None = None,
    api_key: str | None = None,
) -> AIAnalysisResult:
    """
    Convenience function for AI analysis.

    Args:
        report: Playwright test report.
        container_logs: Optional container logs.
        api_key: Optional API key. If None, reads from environment.

    Returns:
        AIAnalysisResult with diagnosis.
    """
    analyzer = AIAnalyzer(
        report=report,
        container_logs=container_logs,
        api_key=api_key,
    )
    return analyzer.analyze()
