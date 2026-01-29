"""Prompt builder for LLM analysis of test failures."""

from __future__ import annotations

from typing import TYPE_CHECKING

from heisenberg.integrations.docker import ContainerLogs

if TYPE_CHECKING:
    from heisenberg.core.models import UnifiedFailure, UnifiedTestRun


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


def build_unified_prompt(
    run: UnifiedTestRun,
    container_logs: dict[str, ContainerLogs] | None = None,
    job_logs_context: str | None = None,
    screenshot_context: str | None = None,
    trace_context: str | None = None,
) -> tuple[str, str]:
    """
    Build analysis prompts from UnifiedTestRun.

    This is the framework-agnostic version of build_analysis_prompt.
    It works with the unified failure model instead of Playwright-specific reports.

    Args:
        run: UnifiedTestRun containing test failures.
        container_logs: Optional container logs for context.
        job_logs_context: Optional pre-formatted job logs snippets.
        screenshot_context: Optional pre-formatted screenshot descriptions.
        trace_context: Optional pre-formatted Playwright trace analysis.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """

    system_prompt = get_system_prompt()
    user_prompt = _build_unified_user_prompt(
        run, container_logs, job_logs_context, screenshot_context, trace_context
    )
    return system_prompt, user_prompt


def _build_prompt_header(run: UnifiedTestRun) -> str:
    """Build the header section with summary information."""
    summary = run.summary()
    header = f"""# Test Failure Analysis Request

## Summary
- Total tests: {summary["total"]}
- Passed: {summary["passed"]}
- Failed: {summary["failed"]}
- Skipped: {summary["skipped"]}
- Pass rate: {summary["pass_rate"]:.1%}"""

    if run.repository:
        header += f"\n- Repository: {run.repository}"
    if run.branch:
        header += f"\n- Branch: {run.branch}"
    if run.run_id:
        header += f"\n- Run ID: {run.run_id}"
    return header


def _format_failure_for_prompt(failure: UnifiedFailure, index: int) -> list[str]:
    """Format a single test failure for the prompt."""
    lines = [f"\n### Test {index}: {failure.test_title}", f"- **File:** {failure.file_path}"]

    if failure.suite_path:
        lines.append(f"- **Suite:** {' > '.join(failure.suite_path)}")

    meta = failure.metadata
    lines.append(f"- **Framework:** {meta.framework.value}")
    if meta.browser:
        lines.append(f"- **Browser:** {meta.browser}")
    if meta.duration_ms:
        lines.append(f"- **Duration:** {meta.duration_ms}ms")
    if meta.retry_count > 0:
        lines.append(f"- **Retries:** {meta.retry_count}")

    error = failure.error
    lines.extend(["\n#### Error", f"**Message:**\n```\n{error.message}\n```"])

    if error.stack_trace:
        stack_lines = error.stack_trace.split("\n")
        stack = (
            "\n".join(stack_lines[:20]) + "\n... (truncated)"
            if len(stack_lines) > 20
            else error.stack_trace
        )
        lines.append(f"\n**Stack Trace:**\n```\n{stack}\n```")

    if error.location:
        lines.append(
            f"- **Location:** Line {error.location.get('line')}, "
            f"Column {error.location.get('column', 0)}"
        )
    return lines


def _build_container_logs_section(container_logs: dict[str, ContainerLogs]) -> str:
    """Build container logs section for prompt."""
    lines = [
        "## Backend Container Logs",
        "Logs collected from containers around the time of test failure:\n",
    ]
    for name, logs in container_logs.items():
        lines.append(f"### Container: {name}")
        if not logs.entries:
            lines.append("*No logs available*")
            continue
        lines.append("```")
        entries = logs.entries[:50] if len(logs.entries) > 50 else logs.entries
        lines.extend(str(entry) for entry in entries)
        lines.append("```")
    return "\n".join(lines)


def _build_unified_user_prompt(
    run: UnifiedTestRun,
    container_logs: dict[str, ContainerLogs] | None = None,
    job_logs_context: str | None = None,
    screenshot_context: str | None = None,
    trace_context: str | None = None,
) -> str:
    """Build user prompt from UnifiedTestRun."""
    sections = [_build_prompt_header(run)]

    # Failed tests section
    failed_tests_lines = ["## Failed Tests"]
    for i, failure in enumerate(run.failures, 1):
        failed_tests_lines.extend(_format_failure_for_prompt(failure, i))
    sections.append("\n".join(failed_tests_lines))

    if container_logs:
        sections.append(_build_container_logs_section(container_logs))

    # Job logs context (GitHub Actions logs)
    if job_logs_context:
        sections.append(job_logs_context)

    # Screenshot context (visual analysis)
    if screenshot_context:
        sections.append(screenshot_context)

    # Trace context (Playwright traces - console, network, actions)
    if trace_context:
        sections.append(trace_context)

    # Analysis instructions
    instructions = """## Analysis Request

Please analyze the test failure(s) above and provide:
1. Root cause analysis
2. Supporting evidence from errors and logs
3. Suggested fix or investigation steps
4. Your confidence level in the diagnosis"""

    sections.append(instructions)

    return "\n\n".join(sections)
