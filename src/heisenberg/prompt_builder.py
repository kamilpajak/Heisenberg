"""Prompt builder for LLM analysis of test failures."""

from __future__ import annotations

from heisenberg.docker_logs import ContainerLogs
from heisenberg.log_compressor import compress_logs_for_llm
from heisenberg.playwright_parser import PlaywrightReport


def get_system_prompt() -> str:
    """
    Get the system prompt for test failure analysis.

    Returns:
        System prompt string defining the AI's role and output format.
    """
    return """You are an expert test failure analyst specializing in end-to-end testing with Playwright.

Your task is to analyze test failures and identify the root cause. You will be provided with:
1. Failed test information (name, file, error message, stack trace)
2. Backend container logs from around the time of failure (if available)

When analyzing, consider:
- Timing issues (race conditions, timeouts, slow responses)
- Backend errors (API failures, database issues, service unavailability)
- Frontend issues (element not found, incorrect selectors, state problems)
- Environment issues (network, configuration, resource constraints)
- Flaky test patterns (intermittent failures due to timing or external dependencies)

Provide your analysis in this format:

## Root Cause Analysis
[Explain the most likely root cause in 2-3 sentences]

## Evidence
[List specific evidence from the error message, stack trace, and logs that support your analysis]

## Suggested Fix
[Provide actionable recommendations to fix the issue]

## Confidence Score
[Rate your confidence: HIGH (>80%), MEDIUM (50-80%), or LOW (<50%)]
[Brief explanation of confidence level]

Be concise but thorough. Focus on actionable insights."""


class PromptBuilder:
    """Builds prompts for LLM analysis from test failure data."""

    def __init__(
        self,
        report: PlaywrightReport,
        container_logs: dict[str, ContainerLogs] | None = None,
        max_log_lines: int = 50,
        compress_logs: bool = True,
        max_tokens: int | None = None,
    ):
        """
        Initialize prompt builder.

        Args:
            report: Playwright test report with failure details.
            container_logs: Optional dict of container logs.
            max_log_lines: Maximum log lines to include per container.
            compress_logs: Whether to compress/filter logs.
            max_tokens: Optional token limit for logs section.
        """
        self.report = report
        self.container_logs = container_logs or {}
        self.max_log_lines = max_log_lines
        self.compress_logs = compress_logs
        self.max_tokens = max_tokens

    def build(self) -> str:
        """
        Build the analysis prompt.

        Returns:
            Formatted prompt string for LLM.
        """
        sections = [
            self._build_header(),
            self._build_failed_tests_section(),
        ]

        if self.container_logs:
            sections.append(self._build_logs_section())

        sections.append(self._build_instructions())

        return "\n\n".join(sections)

    def _build_header(self) -> str:
        """Build prompt header with summary."""
        total_tests = (
            self.report.total_passed
            + self.report.total_failed
            + self.report.total_skipped
            + self.report.total_flaky
        )
        return f"""# Test Failure Analysis Request

## Summary
- Total tests: {total_tests}
- Passed: {self.report.total_passed}
- Failed: {self.report.total_failed}
- Skipped: {self.report.total_skipped}
- Flaky: {self.report.total_flaky}"""

    def _build_failed_tests_section(self) -> str:
        """Build section for failed test details."""
        lines = ["## Failed Tests"]

        for i, test in enumerate(self.report.failed_tests, 1):
            lines.append(f"\n### Test {i}: {test.title}")
            lines.append(f"- **File:** {test.file}")
            lines.append(f"- **Suite:** {test.suite}")
            lines.append(f"- **Project:** {test.project}")
            lines.append(f"- **Duration:** {test.duration_ms}ms")

            if test.start_time:
                lines.append(f"- **Start time:** {test.start_time.isoformat()}")

            if test.trace_path:
                lines.append(f"- **Trace:** {test.trace_path}")

            for j, error in enumerate(test.errors, 1):
                lines.append(f"\n#### Error {j}")
                lines.append(f"**Message:**\n```\n{error.message}\n```")
                if error.stack:
                    # Truncate very long stack traces
                    stack = error.stack
                    stack_lines = stack.split("\n")
                    if len(stack_lines) > 20:
                        stack = "\n".join(stack_lines[:20]) + "\n... (truncated)"
                    lines.append(f"\n**Stack Trace:**\n```\n{stack}\n```")

        return "\n".join(lines)

    def _build_logs_section(self) -> str:
        """Build section for container logs."""
        lines = ["## Backend Container Logs"]
        lines.append("Logs collected from containers around the time of test failure:\n")

        # Get focus timestamp from earliest failure
        focus_timestamp = None
        if self.report.failed_tests:
            failure_times = [t.start_time for t in self.report.failed_tests if t.start_time]
            if failure_times:
                focus_timestamp = min(failure_times)

        # Compress logs if enabled
        if self.compress_logs and self.container_logs:
            compressed = compress_logs_for_llm(
                self.container_logs,
                max_tokens=self.max_tokens,
                max_lines=self.max_log_lines * len(self.container_logs),
                focus_timestamp=focus_timestamp,
                deduplicate=True,
                filter_noise=True,
            )
            logs_to_use = compressed.logs

            if compressed.was_truncated:
                lines.append(
                    f"*(Logs compressed: {compressed.total_lines} of "
                    f"{compressed.original_lines} lines, "
                    f"~{compressed.estimated_tokens} tokens)*\n"
                )
        else:
            logs_to_use = self.container_logs

        for name, logs in logs_to_use.items():
            lines.append(f"### Container: {name}")

            if not logs.entries:
                lines.append("*No logs available*")
                continue

            # Truncate if too many entries (fallback if compression disabled)
            entries = logs.entries
            if not self.compress_logs and len(entries) > self.max_log_lines:
                half = self.max_log_lines // 2
                entries = entries[:half] + entries[-half:]
                lines.append(f"*(Showing {self.max_log_lines} of {len(logs.entries)} lines)*\n")

            lines.append("```")
            for entry in entries:
                lines.append(str(entry))
            lines.append("```")

        return "\n".join(lines)

    def _build_instructions(self) -> str:
        """Build analysis instructions."""
        return """## Analysis Request

Please analyze the test failure(s) above and provide:
1. Root cause analysis
2. Supporting evidence from errors and logs
3. Suggested fix or investigation steps
4. Your confidence level in the diagnosis"""


def build_analysis_prompt(
    report: PlaywrightReport,
    container_logs: dict[str, ContainerLogs] | None = None,
    max_log_lines: int = 50,
) -> tuple[str, str]:
    """
    Convenience function to build analysis prompts.

    Args:
        report: Playwright test report.
        container_logs: Optional container logs.
        max_log_lines: Maximum log lines per container.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    builder = PromptBuilder(
        report=report,
        container_logs=container_logs,
        max_log_lines=max_log_lines,
    )
    return get_system_prompt(), builder.build()
