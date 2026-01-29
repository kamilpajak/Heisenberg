"""Formatters for UnifiedTestRun output.

This module provides functions to format UnifiedTestRun objects
into various output formats (markdown, JSON, GitHub comments, etc.)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heisenberg.core.models import UnifiedFailure, UnifiedTestRun


def _format_stack_trace(stack_trace: str | None, max_lines: int = 15) -> list[str]:
    """Format stack trace with optional truncation."""
    if not stack_trace:
        return []
    lines = ["", "**Stack trace:**", "```"]
    stack_lines = stack_trace.split("\n")
    if len(stack_lines) > max_lines:
        lines.extend(stack_lines[:max_lines])
        lines.append("... (truncated)")
    else:
        lines.extend(stack_lines)
    lines.append("```")
    return lines


def _format_md_failure(failure: UnifiedFailure, index: int) -> list[str]:
    """Format a single failure for markdown output."""
    lines = [f"### {index}. {failure.test_title}", f"- **File:** `{failure.file_path}`"]

    if failure.suite_path:
        lines.append(f"- **Suite:** {' > '.join(failure.suite_path)}")

    meta = failure.metadata
    lines.append(f"- **Framework:** {meta.framework.value}")
    if meta.browser:
        lines.append(f"- **Browser:** {meta.browser}")
    if meta.duration_ms:
        lines.append(f"- **Duration:** {meta.duration_ms}ms")

    lines.extend(["", "**Error:**", "```", failure.error.message, "```"])
    lines.extend(_format_stack_trace(failure.error.stack_trace))
    lines.append("")
    return lines


def format_unified_as_markdown(run: UnifiedTestRun) -> str:
    """Format UnifiedTestRun as markdown.

    Args:
        run: UnifiedTestRun to format.

    Returns:
        Markdown-formatted string.
    """
    lines = ["# Test Failure Analysis", ""]

    # Summary
    summary = run.summary()
    lines.extend(
        [
            "## Summary",
            f"- **Total tests:** {summary['total']}",
            f"- **Passed:** {summary['passed']}",
            f"- **Failed:** {summary['failed']}",
            f"- **Skipped:** {summary['skipped']}",
            f"- **Pass rate:** {summary['pass_rate']:.1%}",
        ]
    )

    if run.repository:
        lines.append(f"- **Repository:** {run.repository}")
    if run.branch:
        lines.append(f"- **Branch:** {run.branch}")
    if run.run_id:
        lines.append(f"- **Run ID:** {run.run_id}")

    lines.append("")

    # Failed tests
    if run.failures:
        lines.extend(["## Failed Tests", ""])
        for i, failure in enumerate(run.failures, 1):
            lines.extend(_format_md_failure(failure, i))

    return "\n".join(lines)


def _format_github_run_details(run: UnifiedTestRun) -> list[str]:
    """Format run details as collapsible GitHub section."""
    if not run.repository and not run.branch:
        return []
    lines = ["<details>", "<summary>Run Details</summary>", ""]
    if run.repository:
        lines.append(f"- Repository: `{run.repository}`")
    if run.branch:
        lines.append(f"- Branch: `{run.branch}`")
    if run.run_id:
        lines.append(f"- Run ID: `{run.run_id}`")
    if run.run_url:
        lines.append(f"- [View Run]({run.run_url})")
    lines.extend(["", "</details>", ""])
    return lines


def _format_github_failure(failure: UnifiedFailure, max_error_len: int = 500) -> list[str]:
    """Format a single failure for GitHub output."""
    error_msg = failure.error.message
    if len(error_msg) > max_error_len:
        error_msg = error_msg[:max_error_len] + "..."
    return [
        f"### {failure.test_title}",
        f"**File:** `{failure.file_path}`",
        "",
        "```",
        error_msg,
        "```",
        "",
    ]


def format_unified_for_github(run: UnifiedTestRun) -> str:
    """Format UnifiedTestRun for GitHub PR comment.

    Args:
        run: UnifiedTestRun to format.

    Returns:
        GitHub-flavored markdown string suitable for PR comments.
    """
    summary = run.summary()
    status = "FAILED" if run.failed_tests > 0 else "PASSED"

    lines = [
        f"## Test Results: {status}",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total | {summary['total']} |",
        f"| Passed | {summary['passed']} |",
        f"| Failed | {summary['failed']} |",
        f"| Skipped | {summary['skipped']} |",
        f"| Pass Rate | {summary['pass_rate']:.1%} |",
        "",
    ]

    lines.extend(_format_github_run_details(run))

    # Failed tests (collapsible for long lists)
    if run.failures:
        use_collapsible = len(run.failures) > 3
        if use_collapsible:
            lines.extend(
                ["<details>", f"<summary>Failed Tests ({len(run.failures)})</summary>", ""]
            )

        for failure in run.failures:
            lines.extend(_format_github_failure(failure))

        if use_collapsible:
            lines.append("</details>")

    return "\n".join(lines)


def format_unified_as_json(run: UnifiedTestRun, indent: int = 2) -> str:
    """Format UnifiedTestRun as JSON.

    Args:
        run: UnifiedTestRun to format.
        indent: JSON indentation level.

    Returns:
        JSON string representation.
    """
    return json.dumps(run.to_dict(), indent=indent)
