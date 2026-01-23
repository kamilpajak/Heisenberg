"""Command-line interface for Heisenberg."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from heisenberg.analyzer import run_analysis
from heisenberg.github_client import post_pr_comment


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
    analyze_parser.add_argument(
        "--post-comment",
        action="store_true",
        help="Post result as GitHub PR comment (requires GITHUB_TOKEN)",
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
        result = run_analysis(
            report_path=report_path,
            docker_services=args.docker_services,
            log_window_seconds=args.log_window,
        )
    except ValueError as e:
        print(f"Error analyzing report: {e}", file=sys.stderr)
        return 1

    # Format output
    if args.output_format == "github-comment":
        output = result.to_markdown()
    elif args.output_format == "json":
        output = json.dumps(
            {
                "has_failures": result.has_failures,
                "summary": result.summary,
                "failed_tests_count": len(result.report.failed_tests),
                "failed_tests": [
                    {
                        "name": t.full_name,
                        "file": t.file,
                        "status": t.status,
                        "error": t.error_summary,
                    }
                    for t in result.report.failed_tests
                ],
            },
            indent=2,
        )
    else:
        output = _format_text_output(result)

    print(output)

    # Post to GitHub if requested
    if args.post_comment and args.output_format == "github-comment":
        try:
            response = post_pr_comment(result.to_markdown())
            if response:
                print(
                    f"\nComment posted: {response.get('html_url', 'success')}",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"Warning: Failed to post comment: {e}", file=sys.stderr)

    # Return non-zero if there are failures
    return 1 if result.has_failures else 0


def _format_text_output(result) -> str:
    """Format result as plain text."""
    lines = [
        "Heisenberg Test Analysis",
        "=" * 40,
        "",
        f"Summary: {result.summary}",
        "",
    ]

    if result.has_failures:
        lines.append("Failed Tests:")
        lines.append("-" * 40)
        for test in result.report.failed_tests:
            lines.append(f"  - {test.full_name}")
            lines.append(f"    File: {test.file}")
            lines.append(f"    Status: {test.status}")
            if test.errors:
                error_msg = test.errors[0].message
                if len(error_msg) > 100:
                    error_msg = error_msg[:100] + "..."
                lines.append(f"    Error: {error_msg}")
            lines.append("")

    # Add container logs if available
    if result.container_logs:
        lines.append("Backend Logs:")
        lines.append("-" * 40)
        for name, logs in result.container_logs.items():
            lines.append(f"  [{name}]")
            for entry in logs.entries[:10]:  # Limit to 10 entries per container
                lines.append(f"    {entry}")
            if len(logs.entries) > 10:
                lines.append(f"    ... and {len(logs.entries) - 10} more entries")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
