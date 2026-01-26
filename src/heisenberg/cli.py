"""Command-line interface for Heisenberg."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from heisenberg.ai_analyzer import analyze_unified_run, analyze_with_ai
from heisenberg.analyzer import run_analysis
from heisenberg.github_client import post_pr_comment
from heisenberg.unified_model import PlaywrightTransformer, UnifiedTestRun


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
        choices=["github-comment", "json", "text", "unified-json"],
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
    analyze_parser.add_argument(
        "--use-unified",
        action="store_true",
        help="Use unified failure model for analysis (framework-agnostic)",
    )
    analyze_parser.add_argument(
        "--report-format",
        choices=["playwright", "junit"],
        default="playwright",
        help="Format of the test report (default: playwright)",
    )

    # fetch-github command
    fetch_parser = subparsers.add_parser(
        "fetch-github",
        help="Fetch and analyze Playwright report from GitHub Actions",
    )
    fetch_parser.add_argument(
        "--repo",
        "-r",
        type=str,
        required=True,
        help="GitHub repository in owner/repo format",
    )
    fetch_parser.add_argument(
        "--token",
        "-t",
        type=str,
        default=None,
        help="GitHub token (or set GITHUB_TOKEN env var)",
    )
    fetch_parser.add_argument(
        "--run-id",
        type=int,
        default=None,
        help="Specific workflow run ID (default: latest failed)",
    )
    fetch_parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Save report to file instead of analyzing",
    )
    fetch_parser.add_argument(
        "--artifact-name",
        default="playwright",
        help="Pattern to match artifact name (default: playwright)",
    )
    fetch_parser.add_argument(
        "--ai-analysis",
        "-a",
        action="store_true",
        help="Enable AI-powered root cause analysis",
    )
    fetch_parser.add_argument(
        "--provider",
        "-p",
        choices=["claude", "openai", "gemini"],
        default="claude",
        help="LLM provider to use (default: claude)",
    )
    fetch_parser.add_argument(
        "--list-artifacts",
        action="store_true",
        help="List available artifacts for debugging (does not analyze)",
    )
    fetch_parser.add_argument(
        "--merge-blobs",
        action="store_true",
        help="Merge Playwright blob reports before analysis (requires npx/playwright)",
    )
    fetch_parser.add_argument(
        "--include-logs",
        action="store_true",
        help="Include GitHub Actions job logs in analysis for enhanced diagnostics",
    )
    fetch_parser.add_argument(
        "--include-screenshots",
        action="store_true",
        help="Analyze failure screenshots with vision model (requires Gemini)",
    )
    fetch_parser.add_argument(
        "--include-traces",
        action="store_true",
        help="Extract and analyze Playwright traces (console logs, network, actions)",
    )

    args = parser.parse_args()

    if args.command == "analyze":
        return run_analyze(args)
    elif args.command == "fetch-github":
        return run_fetch_github(args)

    return 1


def _load_container_logs(args, result):
    """Load container logs from file if provided."""
    container_logs = result.container_logs
    container_logs_path = getattr(args, "container_logs", None)

    if not (container_logs_path and container_logs_path.exists()):
        return container_logs

    try:
        container_logs_content = container_logs_path.read_text()
        if container_logs is None:
            container_logs = {}
        container_logs["logs_file"] = container_logs_content
    except Exception as e:
        print(f"Warning: Failed to read container logs: {e}", file=sys.stderr)

    return container_logs


def _run_ai_analysis(args, result, container_logs):
    """Run AI analysis if requested and there are failures."""
    if not (getattr(args, "ai_analysis", False) and result.has_failures):
        return None

    try:
        return analyze_with_ai(
            report=result.report,
            container_logs=container_logs,
            provider=getattr(args, "provider", "claude"),
            model=getattr(args, "model", None),
        )
    except Exception as e:
        print(f"Warning: AI analysis failed: {e}", file=sys.stderr)
        return None


def _format_json_output(result, ai_result) -> str:
    """Format result as JSON."""
    flaky_detected = any(
        getattr(t, "retry_count", 0) > 0 or t.status == "flaky" for t in result.report.failed_tests
    )
    data = {
        "has_failures": result.has_failures,
        "flaky_detected": flaky_detected,
        "summary": result.summary,
        "failed_tests_count": len(result.report.failed_tests),
        "failed_tests": [
            {"name": t.full_name, "file": t.file, "status": t.status, "error": t.error_summary}
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
    return json.dumps(data, indent=2)


def _format_output(args, result, ai_result) -> str:
    """Format output based on requested format."""
    if args.output_format == "github-comment":
        output = result.to_markdown()
        if ai_result:
            output += "\n\n" + ai_result.to_markdown()
        return output
    elif args.output_format == "json":
        return _format_json_output(result, ai_result)
    return _format_text_output(result, ai_result)


def _post_github_comment(args, result):
    """Post result to GitHub if requested."""
    if not (args.post_comment and args.output_format == "github-comment"):
        return

    try:
        response = post_pr_comment(result.to_markdown())
        if response:
            print(f"\nComment posted: {response.get('html_url', 'success')}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Failed to post comment: {e}", file=sys.stderr)


def convert_to_unified(
    report,
    run_id: str | None = None,
    repository: str | None = None,
    branch: str | None = None,
) -> UnifiedTestRun:
    """Convert a PlaywrightReport to UnifiedTestRun.

    Args:
        report: PlaywrightReport instance.
        run_id: Optional run identifier.
        repository: Optional repository name.
        branch: Optional branch name.

    Returns:
        UnifiedTestRun instance.
    """
    return PlaywrightTransformer.transform_report(
        report,
        run_id=run_id,
        repository=repository,
        branch=branch,
    )


def run_analyze(args: argparse.Namespace) -> int:
    """Run the analyze command."""
    if not args.report.exists():
        print(f"Error: Report file not found: {args.report}", file=sys.stderr)
        return 1

    report_format = getattr(args, "report_format", "playwright")

    # Handle JUnit format
    if report_format == "junit":
        return _run_junit_analyze(args)

    # Handle Playwright format (default)
    try:
        result = run_analysis(
            report_path=args.report,
            docker_services=args.docker_services,
            log_window_seconds=args.log_window,
        )
    except ValueError as e:
        print(f"Error analyzing report: {e}", file=sys.stderr)
        return 1

    container_logs = _load_container_logs(args, result)

    # Use unified model if requested
    use_unified = getattr(args, "use_unified", False)
    if use_unified and args.ai_analysis:
        unified_run = convert_to_unified(result.report)
        ai_result = analyze_unified_run(
            unified_run,
            container_logs=container_logs,
            provider=args.provider,
            model=getattr(args, "model", None),
        )
    else:
        ai_result = _run_ai_analysis(args, result, container_logs)

    # Handle unified-json output format
    if args.output_format == "unified-json":
        from heisenberg.formatters import format_unified_as_json

        unified_run = convert_to_unified(result.report)
        print(format_unified_as_json(unified_run))
    else:
        print(_format_output(args, result, ai_result))

    _post_github_comment(args, result)

    return 1 if result.has_failures else 0


def _run_junit_analyze(args: argparse.Namespace) -> int:
    """Run analysis for JUnit XML reports."""
    from heisenberg.formatters import format_unified_as_json, format_unified_as_markdown
    from heisenberg.junit_parser import JUnitParser

    try:
        report = JUnitParser.parse_file(args.report)
    except Exception as e:
        print(f"Error parsing JUnit report: {e}", file=sys.stderr)
        return 1

    unified_run = JUnitParser.to_unified(report)

    # AI analysis if requested
    ai_result = None
    if args.ai_analysis and report.total_failed > 0:
        try:
            ai_result = analyze_unified_run(
                unified_run,
                provider=args.provider,
                model=getattr(args, "model", None),
            )
        except Exception as e:
            print(f"Warning: AI analysis failed: {e}", file=sys.stderr)

    # Output based on format
    if args.output_format == "unified-json":
        print(format_unified_as_json(unified_run))
    elif args.output_format == "json":
        print(_format_junit_json(report, ai_result))
    elif args.output_format == "github-comment":
        output = format_unified_as_markdown(unified_run)
        if ai_result:
            output += "\n\n" + ai_result.to_markdown()
        print(output)
    else:
        print(_format_junit_text(report, ai_result))

    return 1 if report.total_failed > 0 else 0


def _format_junit_json(report, ai_result) -> str:
    """Format JUnit report as JSON."""
    data = {
        "has_failures": report.total_failed > 0,
        "summary": {
            "total": report.total_tests,
            "passed": report.total_passed,
            "failed": report.total_failed,
            "errors": report.total_errors,
            "skipped": report.total_skipped,
        },
        "failed_tests": [
            {
                "name": tc.name,
                "classname": tc.classname,
                "status": tc.status,
                "error": tc.failure_message,
            }
            for tc in report.failed_tests
        ],
    }
    if ai_result:
        data["ai_diagnosis"] = {
            "root_cause": ai_result.diagnosis.root_cause,
            "evidence": ai_result.diagnosis.evidence,
            "suggested_fix": ai_result.diagnosis.suggested_fix,
            "confidence": ai_result.diagnosis.confidence.value,
        }
    return json.dumps(data, indent=2)


def _format_junit_text(report, ai_result=None) -> str:
    """Format JUnit report as plain text."""
    lines = [
        "Heisenberg Test Analysis (JUnit)",
        "=" * 40,
        "",
        f"Summary: {report.total_passed} passed, {report.total_failed} failed, "
        f"{report.total_skipped} skipped",
        "",
    ]

    if report.failed_tests:
        lines.extend(["Failed Tests:", "-" * 40])
        for tc in report.failed_tests:
            lines.append(f"  - {tc.classname} > {tc.name}")
            lines.append(f"    Status: {tc.status}")
            if tc.failure_message:
                msg = tc.failure_message
                if len(msg) > 100:
                    msg = msg[:100] + "..."
                lines.append(f"    Error: {msg}")
            lines.append("")

    if ai_result:
        lines.extend(_format_ai_diagnosis_section(ai_result))

    return "\n".join(lines)


def _format_failed_tests_section(failed_tests: list) -> list[str]:
    """Format failed tests section."""
    lines = ["Failed Tests:", "-" * 40]
    for test in failed_tests:
        lines.append(f"  - {test.full_name}")
        lines.append(f"    File: {test.file}")
        lines.append(f"    Status: {test.status}")
        if test.errors:
            error_msg = test.errors[0].message
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
            lines.append(f"    Error: {error_msg}")
        lines.append("")
    return lines


def _format_container_logs_section(container_logs: dict) -> list[str]:
    """Format container logs section."""
    lines = ["Backend Logs:", "-" * 40]
    for name, logs in container_logs.items():
        lines.append(f"  [{name}]")
        for entry in logs.entries[:10]:
            lines.append(f"    {entry}")
        if len(logs.entries) > 10:
            lines.append(f"    ... and {len(logs.entries) - 10} more entries")
        lines.append("")
    return lines


def _format_ai_diagnosis_section(ai_result) -> list[str]:
    """Format AI diagnosis section."""
    lines = ["AI Diagnosis:", "-" * 40]
    lines.append(f"  Root Cause: {ai_result.diagnosis.root_cause}")
    lines.append("")
    if ai_result.diagnosis.evidence:
        lines.append("  Evidence:")
        lines.extend(f"    - {item}" for item in ai_result.diagnosis.evidence)
        lines.append("")
    lines.append(f"  Suggested Fix: {ai_result.diagnosis.suggested_fix}")
    lines.append("")
    lines.append(f"  Confidence: {ai_result.diagnosis.confidence.value}")
    if ai_result.diagnosis.confidence_explanation:
        lines.append(f"  ({ai_result.diagnosis.confidence_explanation})")
    lines.append("")
    lines.append(f"  Tokens: {ai_result.total_tokens} | Cost: ${ai_result.estimated_cost:.4f}")
    lines.append("")
    return lines


def _format_text_output(result, ai_result=None) -> str:
    """Format result as plain text."""
    lines = ["Heisenberg Test Analysis", "=" * 40, "", f"Summary: {result.summary}", ""]

    if result.has_failures:
        lines.extend(_format_failed_tests_section(result.report.failed_tests))

    if result.container_logs:
        lines.extend(_format_container_logs_section(result.container_logs))

    if ai_result:
        lines.extend(_format_ai_diagnosis_section(ai_result))

    return "\n".join(lines)


async def _fetch_report_from_run(client, owner: str, repo: str, run_id: int, artifact_name: str):
    """Fetch Playwright report from a specific workflow run."""
    artifacts = await client.get_artifacts(owner, repo, run_id=run_id)
    matching = [a for a in artifacts if artifact_name.lower() in a.name.lower()]

    if not matching:
        return None

    zip_data = await client.download_artifact(owner, repo, matching[0].id)
    return client.extract_playwright_report(zip_data)


def _analyze_report_data(
    report_data: dict,
    args,
    job_logs_context: str | None = None,
    screenshot_context: str | None = None,
    trace_context: str | None = None,
) -> int:
    """Analyze fetched report data and print results."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(report_data, f)
        temp_path = Path(f.name)

    try:
        result = run_analysis(report_path=temp_path)

        # Run AI analysis with additional context if available
        ai_result = None
        if getattr(args, "ai_analysis", False) and result.has_failures:
            try:
                # Use unified model when we have additional context
                if job_logs_context or screenshot_context or trace_context:
                    unified_run = convert_to_unified(result.report)
                    ai_result = analyze_unified_run(
                        unified_run,
                        provider=getattr(args, "provider", "claude"),
                        model=getattr(args, "model", None),
                        job_logs_context=job_logs_context,
                        screenshot_context=screenshot_context,
                        trace_context=trace_context,
                    )
                else:
                    ai_result = analyze_with_ai(
                        report=result.report,
                        provider=getattr(args, "provider", "claude"),
                        model=getattr(args, "model", None),
                    )
            except Exception as e:
                print(f"Warning: AI analysis failed: {e}", file=sys.stderr)

        print(_format_text_output(result, ai_result))
        return 1 if result.has_failures else 0
    finally:
        temp_path.unlink()


def _fetch_and_process_job_logs(
    token: str,
    owner: str,
    repo: str,
    run_id: int | None,
) -> str | None:
    """Fetch and process job logs from GitHub Actions.

    Args:
        token: GitHub token.
        owner: Repository owner.
        repo: Repository name.
        run_id: Optional specific workflow run ID.

    Returns:
        Formatted job logs context string, or None if no logs available.
    """
    import asyncio

    from heisenberg.github_artifacts import GitHubArtifactClient
    from heisenberg.github_logs_fetcher import GitHubLogsFetcher
    from heisenberg.job_logs_processor import JobLogsProcessor

    # Get run ID if not specified
    if run_id is None:

        async def get_latest_failed_run_id():
            client = GitHubArtifactClient(token=token)
            runs = await client.list_workflow_runs(owner, repo)
            failed_runs = [r for r in runs if r.conclusion == "failure"]
            return failed_runs[0].id if failed_runs else None

        try:
            run_id = asyncio.run(get_latest_failed_run_id())
        except Exception:
            return None

    if run_id is None:
        return None

    print(f"Fetching job logs for run {run_id}...", file=sys.stderr)

    fetcher = GitHubLogsFetcher()
    logs_by_job = fetcher.fetch_logs_for_run(f"{owner}/{repo}", str(run_id))

    if not logs_by_job:
        print("No job logs found.", file=sys.stderr)
        return None

    # Process logs and extract relevant snippets
    processor = JobLogsProcessor()
    all_snippets = []

    for _job_name, log_content in logs_by_job.items():
        snippets = processor.extract_snippets(log_content)
        all_snippets.extend(snippets)

    if not all_snippets:
        print("No error snippets found in job logs.", file=sys.stderr)
        return None

    print(f"Found {len(all_snippets)} relevant log snippet(s).", file=sys.stderr)
    return processor.format_for_prompt(all_snippets)


def _fetch_and_analyze_screenshots(
    token: str,
    owner: str,
    repo: str,
    run_id: int | None,
    artifact_name: str,
) -> str | None:
    """Fetch and analyze screenshots from Playwright artifacts.

    Args:
        token: GitHub token.
        owner: Repository owner.
        repo: Repository name.
        run_id: Optional specific workflow run ID.
        artifact_name: Pattern to match artifact name.

    Returns:
        Formatted screenshot analysis string, or None if no screenshots.
    """
    import asyncio

    from heisenberg.github_artifacts import GitHubArtifactClient
    from heisenberg.screenshot_analyzer import (
        ScreenshotAnalyzer,
        extract_screenshots_from_artifact,
        format_screenshots_for_prompt,
    )

    async def fetch_artifacts():
        client = GitHubArtifactClient(token=token)

        # Get run ID if not specified
        actual_run_id = run_id
        if actual_run_id is None:
            runs = await client.list_workflow_runs(owner, repo)
            failed_runs = [r for r in runs if r.conclusion == "failure"]
            if not failed_runs:
                return None
            actual_run_id = failed_runs[0].id

        # Get artifacts matching the pattern
        artifacts = await client.get_artifacts(owner, repo, run_id=actual_run_id)
        matching = [a for a in artifacts if artifact_name.lower() in a.name.lower()]

        if not matching:
            return None

        # Download artifact and extract screenshots
        all_screenshots = []
        for artifact in matching[:1]:  # Only first matching artifact
            print(f"Extracting screenshots from: {artifact.name}...", file=sys.stderr)
            zip_data = await client.download_artifact(owner, repo, artifact.id)
            screenshots = extract_screenshots_from_artifact(zip_data)
            all_screenshots.extend(screenshots)

        return all_screenshots

    try:
        screenshots = asyncio.run(fetch_artifacts())
    except Exception as e:
        print(f"Warning: Failed to fetch screenshots: {e}", file=sys.stderr)
        return None

    if not screenshots:
        print("No screenshots found in artifacts.", file=sys.stderr)
        return None

    print(f"Found {len(screenshots)} screenshot(s). Analyzing...", file=sys.stderr)

    # Analyze screenshots with vision model
    analyzer = ScreenshotAnalyzer(provider="gemini")
    analyzed = analyzer.analyze_batch(screenshots, max_screenshots=5)

    # Format for prompt
    return format_screenshots_for_prompt(analyzed)


def _fetch_and_analyze_traces(
    token: str,
    owner: str,
    repo: str,
    run_id: int | None,
    artifact_name: str,
) -> str | None:
    """Fetch and analyze Playwright traces from artifacts.

    Args:
        token: GitHub token.
        owner: Repository owner.
        repo: Repository name.
        run_id: Optional specific workflow run ID.
        artifact_name: Pattern to match artifact name.

    Returns:
        Formatted trace analysis string, or None if no traces.
    """
    import asyncio

    from heisenberg.github_artifacts import GitHubArtifactClient
    from heisenberg.trace_analyzer import (
        TraceAnalyzer,
        extract_trace_from_artifact,
        format_trace_for_prompt,
    )

    async def fetch_artifacts():
        client = GitHubArtifactClient(token=token)

        # Get run ID if not specified
        actual_run_id = run_id
        if actual_run_id is None:
            runs = await client.list_workflow_runs(owner, repo)
            failed_runs = [r for r in runs if r.conclusion == "failure"]
            if not failed_runs:
                return None
            actual_run_id = failed_runs[0].id

        # Get artifacts matching the pattern
        artifacts = await client.get_artifacts(owner, repo, run_id=actual_run_id)
        matching = [a for a in artifacts if artifact_name.lower() in a.name.lower()]

        if not matching:
            return None

        # Download artifact and extract traces
        all_traces = []
        for artifact in matching[:1]:  # Only first matching artifact
            print(f"Extracting traces from: {artifact.name}...", file=sys.stderr)
            zip_data = await client.download_artifact(owner, repo, artifact.id)
            traces = extract_trace_from_artifact(zip_data)
            all_traces.extend(traces)

        return all_traces, zip_data

    try:
        result = asyncio.run(fetch_artifacts())
    except Exception as e:
        print(f"Warning: Failed to fetch traces: {e}", file=sys.stderr)
        return None

    if not result:
        print("No traces found in artifacts.", file=sys.stderr)
        return None

    traces, zip_data = result

    if not traces:
        print("No trace files found in artifacts.", file=sys.stderr)
        return None

    print(f"Found {len(traces)} trace file(s). Analyzing...", file=sys.stderr)

    # Analyze each trace
    analyzer = TraceAnalyzer()

    # We need to re-extract and analyze each trace with actual data
    import io
    import zipfile

    analyzed_traces = []
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data), "r") as outer_zip:
            for file_info in outer_zip.filelist:
                name = file_info.filename.lower()
                if not name.endswith("trace.zip"):
                    continue

                # Extract test name from path
                path_parts = file_info.filename.split("/")
                test_name = path_parts[-2] if len(path_parts) > 1 else "unknown"
                file_path = next(
                    (p for p in path_parts if ".spec." in p or ".test." in p),
                    "unknown-file",
                )

                # Read and analyze the trace
                trace_zip_data = outer_zip.read(file_info.filename)
                trace_ctx = analyzer.analyze(trace_zip_data, test_name, file_path)
                analyzed_traces.append(trace_ctx)

                # Limit to 5 traces
                if len(analyzed_traces) >= 5:
                    break
    except Exception as e:
        print(f"Warning: Error analyzing traces: {e}", file=sys.stderr)

    if not analyzed_traces:
        return None

    # Format for prompt
    return format_trace_for_prompt(analyzed_traces)


def _format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable format."""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


async def run_list_artifacts(
    token: str,
    owner: str,
    repo: str,
    run_id: int | None,
    output=None,
) -> int:
    """List artifacts for debugging purposes.

    Args:
        token: GitHub token
        owner: Repository owner
        repo: Repository name
        run_id: Optional specific workflow run ID
        output: Output stream (defaults to stdout)

    Returns:
        0 on success, 1 on error
    """
    from heisenberg.github_artifacts import GitHubArtifactClient

    if output is None:
        output = sys.stdout

    client = GitHubArtifactClient(token=token)

    # Get run ID if not specified
    if run_id is None:
        runs = await client.list_workflow_runs(owner, repo)
        failed_runs = [r for r in runs if r.conclusion == "failure"]
        if not failed_runs:
            output.write("No failed workflow runs found.\n")
            output.write(
                "\nTip: For local reports, use: heisenberg analyze --report <path-to-json>\n"
            )
            return 0
        run_id = failed_runs[0].id
        output.write(f"Using latest failed run: {run_id}\n")
        output.write(f"  URL: {failed_runs[0].html_url}\n\n")

    # Get artifacts
    artifacts = await client.get_artifacts(owner, repo, run_id=run_id)

    if not artifacts:
        output.write(f"No artifacts found for run {run_id}.\n")
        return 0

    output.write(f"Artifacts for run {run_id}:\n")
    output.write("-" * 60 + "\n")

    for artifact in artifacts:
        expired_marker = " [EXPIRED]" if artifact.expired else ""
        size = _format_size(artifact.size_in_bytes)
        output.write(f"  {artifact.name:<40} {size:>10}{expired_marker}\n")

    output.write("-" * 60 + "\n")
    output.write(f"Total: {len(artifacts)} artifact(s)\n")

    # Show hint about matching pattern
    output.write("\nTip: Use --artifact-name <pattern> to filter artifacts.\n")
    output.write("     Example: --artifact-name playwright\n")

    return 0


async def _fetch_and_merge_blobs(
    token: str,
    owner: str,
    repo: str,
    run_id: int | None,
    artifact_name: str,
) -> dict | None:
    """Fetch blob artifacts and merge them into a JSON report.

    Args:
        token: GitHub token
        owner: Repository owner
        repo: Repository name
        run_id: Optional specific workflow run ID
        artifact_name: Pattern to match artifact name

    Returns:
        Merged JSON report or None
    """
    from heisenberg.blob_merger import BlobMergeError, extract_blob_zips, merge_blob_reports
    from heisenberg.github_artifacts import GitHubArtifactClient

    client = GitHubArtifactClient(token=token)

    # Get run ID if not specified
    if run_id is None:
        runs = await client.list_workflow_runs(owner, repo)
        failed_runs = [r for r in runs if r.conclusion == "failure"]
        if not failed_runs:
            return None
        run_id = failed_runs[0].id
        print(f"Using latest failed run: {run_id}", file=sys.stderr)

    # Get artifacts matching the pattern
    artifacts = await client.get_artifacts(owner, repo, run_id=run_id)
    matching = [a for a in artifacts if artifact_name.lower() in a.name.lower()]

    if not matching:
        return None

    # Download and extract blob ZIP files from all matching artifacts
    all_blob_zips = []
    for artifact in matching:
        print(f"Downloading artifact: {artifact.name}...", file=sys.stderr)
        zip_data = await client.download_artifact(owner, repo, artifact.id)
        blob_zips = extract_blob_zips(zip_data)
        all_blob_zips.extend(blob_zips)

    if not all_blob_zips:
        raise BlobMergeError(
            f"No blob ZIP files found in artifacts. "
            f"Found {len(matching)} artifact(s) but no report-*.zip files inside."
        )

    print(f"Merging {len(all_blob_zips)} blob report(s)...", file=sys.stderr)
    return await merge_blob_reports(blob_zips=all_blob_zips)


def run_fetch_github(args: argparse.Namespace) -> int:
    """Run the fetch-github command."""
    import asyncio
    import os

    from heisenberg.github_artifacts import GitHubAPIError, GitHubArtifactClient

    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GitHub token required. Use --token or set GITHUB_TOKEN", file=sys.stderr)
        print(
            "\nTip: For local reports, use: heisenberg analyze --report <path-to-json>",
            file=sys.stderr,
        )
        return 1

    repo_parts = args.repo.split("/")
    if len(repo_parts) != 2:
        print("Error: Invalid repo format. Use owner/repo", file=sys.stderr)
        return 1

    owner, repo = repo_parts

    # Handle --list-artifacts flag
    if args.list_artifacts:
        try:
            return asyncio.run(run_list_artifacts(token, owner, repo, args.run_id))
        except GitHubAPIError as e:
            print(f"GitHub API error: {e}", file=sys.stderr)
            return 1

    # Handle --merge-blobs flag
    if args.merge_blobs:
        try:
            report_data = asyncio.run(
                _fetch_and_merge_blobs(token, owner, repo, args.run_id, args.artifact_name)
            )
        except GitHubAPIError as e:
            print(f"GitHub API error: {e}", file=sys.stderr)
            print(
                "\nTip: For local reports, use: heisenberg analyze --report <path-to-json>",
                file=sys.stderr,
            )
            return 1
        except Exception as e:
            print(f"Blob merge error: {e}", file=sys.stderr)
            print(
                "\nTip: Ensure Node.js and Playwright are installed: npm install -D @playwright/test",
                file=sys.stderr,
            )
            return 1
    else:

        async def fetch_report():
            client = GitHubArtifactClient(token=token)

            if args.run_id:
                return await _fetch_report_from_run(
                    client, owner, repo, args.run_id, args.artifact_name
                )
            return await client.fetch_latest_report(
                owner, repo, artifact_name_pattern=args.artifact_name
            )

        try:
            report_data = asyncio.run(fetch_report())
        except GitHubAPIError as e:
            print(f"GitHub API error: {e}", file=sys.stderr)
            print(
                "\nTip: For local reports, use: heisenberg analyze --report <path-to-json>",
                file=sys.stderr,
            )
            return 1

    if not report_data:
        msg = (
            f"No artifacts matching '{args.artifact_name}' found"
            if args.run_id
            else "No Playwright report found"
        )
        print(msg, file=sys.stderr)
        print(
            "\nTip: Use --list-artifacts to see available artifacts, or use local workflow:",
            file=sys.stderr,
        )
        print("     heisenberg analyze --report <path-to-json>", file=sys.stderr)
        return 1

    if args.output:
        args.output.write_text(json.dumps(report_data, indent=2))
        print(f"Report saved to {args.output}")
        return 0

    # Fetch job logs if requested
    job_logs_context = None
    if getattr(args, "include_logs", False):
        job_logs_context = _fetch_and_process_job_logs(token, owner, repo, args.run_id)

    # Analyze screenshots if requested
    screenshot_context = None
    if getattr(args, "include_screenshots", False):
        screenshot_context = _fetch_and_analyze_screenshots(
            token, owner, repo, args.run_id, args.artifact_name
        )

    # Analyze traces if requested
    trace_context = None
    if getattr(args, "include_traces", False):
        trace_context = _fetch_and_analyze_traces(
            token, owner, repo, args.run_id, args.artifact_name
        )

    return _analyze_report_data(
        report_data, args, job_logs_context, screenshot_context, trace_context
    )


if __name__ == "__main__":
    sys.exit(main())
