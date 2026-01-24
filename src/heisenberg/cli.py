"""Command-line interface for Heisenberg."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from heisenberg.ai_analyzer import analyze_with_ai
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
    analyze_parser.add_argument(
        "--ai-analysis",
        "-a",
        action="store_true",
        help="Enable AI-powered root cause analysis (requires API key)",
    )
    analyze_parser.add_argument(
        "--provider",
        "-p",
        choices=["claude", "openai", "gemini"],
        default="claude",
        help="LLM provider to use (default: claude)",
    )
    analyze_parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Specific model to use (provider-dependent)",
    )
    analyze_parser.add_argument(
        "--container-logs",
        "-l",
        type=Path,
        default=None,
        help="Path to container logs file for additional context",
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

    # Load container logs from file if provided
    container_logs = result.container_logs
    container_logs_path = getattr(args, "container_logs", None)
    if container_logs_path and container_logs_path.exists():
        try:
            container_logs_content = container_logs_path.read_text()
            # Add file-based logs to container_logs dict
            if container_logs is None:
                container_logs = {}
            container_logs["logs_file"] = container_logs_content
        except Exception as e:
            print(f"Warning: Failed to read container logs: {e}", file=sys.stderr)

    # Run AI analysis if requested and there are failures
    ai_result = None
    if getattr(args, "ai_analysis", False) and result.has_failures:
        try:
            ai_result = analyze_with_ai(
                report=result.report,
                container_logs=container_logs,
                provider=getattr(args, "provider", "claude"),
                model=getattr(args, "model", None),
            )
        except Exception as e:
            print(f"Warning: AI analysis failed: {e}", file=sys.stderr)

    # Format output
    if args.output_format == "github-comment":
        output = result.to_markdown()
        if ai_result:
            output += "\n\n" + ai_result.to_markdown()
    elif args.output_format == "json":
        # Detect flaky tests (tests with retries or intermittent failures)
        flaky_detected = any(
            getattr(t, "retry_count", 0) > 0 or t.status == "flaky"
            for t in result.report.failed_tests
        )
        data = {
            "has_failures": result.has_failures,
            "flaky_detected": flaky_detected,
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
        }
        if ai_result:
            data["ai_diagnosis"] = {
                "root_cause": ai_result.diagnosis.root_cause,
                "evidence": ai_result.diagnosis.evidence,
                "suggested_fix": ai_result.diagnosis.suggested_fix,
                "confidence": ai_result.diagnosis.confidence.value,
                "tokens_used": ai_result.total_tokens,
                "estimated_cost": ai_result.estimated_cost,
            }
        output = json.dumps(data, indent=2)
    else:
        output = _format_text_output(result, ai_result)

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


def _format_text_output(result, ai_result=None) -> str:
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

    # Add AI diagnosis if available
    if ai_result:
        lines.append("AI Diagnosis:")
        lines.append("-" * 40)
        lines.append(f"  Root Cause: {ai_result.diagnosis.root_cause}")
        lines.append("")
        if ai_result.diagnosis.evidence:
            lines.append("  Evidence:")
            for item in ai_result.diagnosis.evidence:
                lines.append(f"    - {item}")
            lines.append("")
        lines.append(f"  Suggested Fix: {ai_result.diagnosis.suggested_fix}")
        lines.append("")
        lines.append(f"  Confidence: {ai_result.diagnosis.confidence.value}")
        if ai_result.diagnosis.confidence_explanation:
            lines.append(f"  ({ai_result.diagnosis.confidence_explanation})")
        lines.append("")
        lines.append(f"  Tokens: {ai_result.total_tokens} | Cost: ${ai_result.estimated_cost:.4f}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
