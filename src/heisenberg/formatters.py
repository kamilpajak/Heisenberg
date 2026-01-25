"""Formatters for UnifiedTestRun output.

This module provides functions to format UnifiedTestRun objects
into various output formats (markdown, JSON, GitHub comments, etc.)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heisenberg.unified_model import UnifiedTestRun


def format_unified_as_markdown(run: UnifiedTestRun) -> str:
    """Format UnifiedTestRun as markdown.

    Args:
        run: UnifiedTestRun to format.

    Returns:
        Markdown-formatted string.
    """
    lines = []

    # Header
    lines.append("# Test Failure Analysis")
    lines.append("")

    # Summary
    summary = run.summary()
    lines.append("## Summary")
    lines.append(f"- **Total tests:** {summary['total']}")
    lines.append(f"- **Passed:** {summary['passed']}")
    lines.append(f"- **Failed:** {summary['failed']}")
    lines.append(f"- **Skipped:** {summary['skipped']}")
    lines.append(f"- **Pass rate:** {summary['pass_rate']:.1%}")

    if run.repository:
        lines.append(f"- **Repository:** {run.repository}")
    if run.branch:
        lines.append(f"- **Branch:** {run.branch}")
    if run.run_id:
        lines.append(f"- **Run ID:** {run.run_id}")

    lines.append("")

    # Failed tests
    if run.failures:
        lines.append("## Failed Tests")
        lines.append("")

        for i, failure in enumerate(run.failures, 1):
            lines.append(f"### {i}. {failure.test_title}")
            lines.append(f"- **File:** `{failure.file_path}`")

            if failure.suite_path:
                lines.append(f"- **Suite:** {' > '.join(failure.suite_path)}")

            meta = failure.metadata
            lines.append(f"- **Framework:** {meta.framework.value}")
            if meta.browser:
                lines.append(f"- **Browser:** {meta.browser}")
            if meta.duration_ms:
                lines.append(f"- **Duration:** {meta.duration_ms}ms")

            lines.append("")
            lines.append("**Error:**")
            lines.append("```")
            lines.append(failure.error.message)
            lines.append("```")

            if failure.error.stack_trace:
                lines.append("")
                lines.append("**Stack trace:**")
                lines.append("```")
                # Truncate long stack traces
                stack_lines = failure.error.stack_trace.split("\n")
                if len(stack_lines) > 15:
                    lines.extend(stack_lines[:15])
                    lines.append("... (truncated)")
                else:
                    lines.extend(stack_lines)
                lines.append("```")

            lines.append("")

    return "\n".join(lines)


def format_unified_for_github(run: UnifiedTestRun) -> str:
    """Format UnifiedTestRun for GitHub PR comment.

    Args:
        run: UnifiedTestRun to format.

    Returns:
        GitHub-flavored markdown string suitable for PR comments.
    """
    lines = []

    # Header with emoji-free status
    summary = run.summary()
    status = "FAILED" if run.failed_tests > 0 else "PASSED"
    lines.append(f"## Test Results: {status}")
    lines.append("")

    # Compact summary table
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total | {summary['total']} |")
    lines.append(f"| Passed | {summary['passed']} |")
    lines.append(f"| Failed | {summary['failed']} |")
    lines.append(f"| Skipped | {summary['skipped']} |")
    lines.append(f"| Pass Rate | {summary['pass_rate']:.1%} |")
    lines.append("")

    # Context
    if run.repository or run.branch:
        lines.append("<details>")
        lines.append("<summary>Run Details</summary>")
        lines.append("")
        if run.repository:
            lines.append(f"- Repository: `{run.repository}`")
        if run.branch:
            lines.append(f"- Branch: `{run.branch}`")
        if run.run_id:
            lines.append(f"- Run ID: `{run.run_id}`")
        if run.run_url:
            lines.append(f"- [View Run]({run.run_url})")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # Failed tests (collapsible for long lists)
    if run.failures:
        if len(run.failures) > 3:
            lines.append("<details>")
            lines.append(f"<summary>Failed Tests ({len(run.failures)})</summary>")
            lines.append("")

        for failure in run.failures:
            lines.append(f"### {failure.test_title}")
            lines.append(f"**File:** `{failure.file_path}`")
            lines.append("")
            lines.append("```")
            # Truncate error message for readability
            error_msg = failure.error.message
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            lines.append(error_msg)
            lines.append("```")
            lines.append("")

        if len(run.failures) > 3:
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
