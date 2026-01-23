"""Command-line interface for Heisenberg."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from heisenberg.comment_formatter import format_pr_comment
from heisenberg.playwright_parser import parse_playwright_report


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="heisenberg",
        description="AI Root Cause Analysis for Flaky Tests",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze Playwright test results",
    )
    analyze_parser.add_argument(
        "--report",
        "-r",
        type=Path,
        required=True,
        help="Path to Playwright JSON report file",
    )
    analyze_parser.add_argument(
        "--output-format",
        "-f",
        choices=["github-comment", "json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    analyze_parser.add_argument(
        "--docker-services",
        "-d",
        type=str,
        default="",
        help="Comma-separated list of Docker services to collect logs from",
    )
    analyze_parser.add_argument(
        "--log-window",
        "-w",
        type=int,
        default=30,
        help="Time window in seconds around failure to collect logs (default: 30)",
    )

    args = parser.parse_args()

    if args.command == "analyze":
        return run_analyze(args)

    return 1


def run_analyze(args: argparse.Namespace) -> int:
    """Run the analyze command."""
    report_path = args.report

    if not report_path.exists():
        print(f"Error: Report file not found: {report_path}", file=sys.stderr)
        return 1

    try:
        report = parse_playwright_report(report_path)
    except ValueError as e:
        print(f"Error parsing report: {e}", file=sys.stderr)
        return 1

    if args.output_format == "github-comment":
        output = format_pr_comment(report)
    elif args.output_format == "json":
        # TODO: Implement JSON output
        output = f'{{"failed_tests": {len(report.failed_tests)}}}'
    else:
        # Text output
        output = _format_text_output(report)

    print(output)

    # Return non-zero if there are failures
    return 1 if report.has_failures else 0


def _format_text_output(report) -> str:
    """Format report as plain text."""
    lines = [
        "Heisenberg Test Analysis",
        "=" * 40,
        "",
        f"Summary: {report.summary}",
        "",
    ]

    if report.has_failures:
        lines.append("Failed Tests:")
        lines.append("-" * 40)
        for test in report.failed_tests:
            lines.append(f"  - {test.full_name}")
            lines.append(f"    File: {test.file}")
            lines.append(f"    Status: {test.status}")
            if test.errors:
                lines.append(f"    Error: {test.errors[0].message[:100]}...")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
