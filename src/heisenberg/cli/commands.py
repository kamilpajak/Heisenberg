"""Command handlers for Heisenberg CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from heisenberg.analysis import analyze_unified_run, analyze_with_ai, run_analysis
from heisenberg.cli import formatters, github_fetch
from heisenberg.core.models import PlaywrightTransformer, UnifiedTestRun
from heisenberg.discovery.analysis import analyze_source_with_status
from heisenberg.discovery.display import DiscoveryDisplay
from heisenberg.discovery.models import SourceStatus
from heisenberg.discovery.service import (
    _USE_DEFAULT_CACHE,
    _USE_DEFAULT_QUARANTINE,
    discover_sources,
)
from heisenberg.integrations.github_client import post_pr_comment
from heisenberg.playground.analyze import AnalyzeConfig, ScenarioAnalyzer
from heisenberg.playground.freeze import CaseFreezer, FreezeConfig
from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator
from heisenberg.playground.validate import CaseValidator, ValidatorConfig

# Mapping of provider names to their required environment variables
PROVIDER_API_KEY_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def validate_api_key_for_provider(provider: str) -> str | None:
    """Validate that the API key is set for the given provider.

    Args:
        provider: The LLM provider name (anthropic, openai, google).

    Returns:
        None if valid, or error message string if invalid.
    """
    env_var = PROVIDER_API_KEY_ENV_VARS.get(provider)
    if not env_var:
        return f"Unknown provider: {provider}"

    if not os.environ.get(env_var):
        return f"{env_var} environment variable is not set. Set {env_var} to use --ai-analysis with {provider} provider."

    return None


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
            provider=getattr(args, "provider", "google"),
            model=getattr(args, "model", None),
        )
    except Exception as e:
        print(f"Warning: AI analysis failed: {e}", file=sys.stderr)
        return None


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

    # Validate API key early if AI analysis is requested (fail fast)
    if getattr(args, "ai_analysis", False):
        provider = getattr(args, "provider", "google")
        error = validate_api_key_for_provider(provider)
        if error:
            print(f"Error: {error}", file=sys.stderr)
            return 1

    report_format = getattr(args, "report_format", "playwright")

    if report_format == "junit":
        return _run_junit_analyze(args)

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
    ai_result = _run_ai_analysis(args, result, container_logs)

    if args.output_format == "unified-json":
        from heisenberg.utils.formatting import format_unified_as_json

        unified_run = convert_to_unified(result.report)
        print(format_unified_as_json(unified_run))
    else:
        print(formatters.format_output(args, result, ai_result))

    _post_github_comment(args, result)

    return 1 if result.has_failures else 0


def _run_junit_analyze(args: argparse.Namespace) -> int:
    """Run analysis for JUnit XML reports."""
    from heisenberg.parsers.junit import JUnitParser
    from heisenberg.utils.formatting import format_unified_as_json, format_unified_as_markdown

    try:
        report = JUnitParser.parse_file(args.report)
    except Exception as e:
        print(f"Error parsing JUnit report: {e}", file=sys.stderr)
        return 1

    unified_run = JUnitParser.to_unified(report)

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

    if args.output_format == "unified-json":
        print(format_unified_as_json(unified_run))
    elif args.output_format == "json":
        print(formatters.format_junit_json(report, ai_result))
    elif args.output_format == "github-comment":
        output = format_unified_as_markdown(unified_run)
        if ai_result:
            output += "\n\n" + ai_result.to_markdown()
        print(output)
    else:
        print(formatters.format_junit_text(report, ai_result))

    return 1 if report.total_failed > 0 else 0


def _analyze_report_data(
    report_data: dict,
    args,
    job_logs_context: str | None = None,
    screenshot_context: str | None = None,
    trace_context: str | None = None,
) -> int:
    """Analyze fetched report data and print results."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(report_data, f)
        temp_path = Path(f.name)

    try:
        result = run_analysis(report_path=temp_path)

        ai_result = None
        if getattr(args, "ai_analysis", False) and result.has_failures:
            try:
                if job_logs_context or screenshot_context or trace_context:
                    unified_run = convert_to_unified(result.report)
                    ai_result = analyze_unified_run(
                        unified_run,
                        provider=getattr(args, "provider", "google"),
                        model=getattr(args, "model", None),
                        job_logs_context=job_logs_context,
                        screenshot_context=screenshot_context,
                        trace_context=trace_context,
                    )
                else:
                    ai_result = analyze_with_ai(
                        report=result.report,
                        provider=getattr(args, "provider", "google"),
                        model=getattr(args, "model", None),
                    )
            except Exception as e:
                print(f"Warning: AI analysis failed: {e}", file=sys.stderr)

        print(formatters.format_output(args, result, ai_result))
        return 1 if result.has_failures else 0
    finally:
        temp_path.unlink()


def _validate_fetch_github_args(args: argparse.Namespace) -> tuple[str, str, str] | None:
    """Validate fetch-github args, returning (token, owner, repo) or None on error."""
    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GitHub token required. Use --token or set GITHUB_TOKEN", file=sys.stderr)
        print(
            "\nTip: For local reports, use: heisenberg analyze --report <path-to-json>",
            file=sys.stderr,
        )
        return None

    if getattr(args, "ai_analysis", False):
        provider = getattr(args, "provider", "google")
        error = validate_api_key_for_provider(provider)
        if error:
            print(f"Error: {error}", file=sys.stderr)
            return None

    repo_parts = args.repo.split("/")
    if len(repo_parts) != 2:
        print("Error: Invalid repo format. Use owner/repo", file=sys.stderr)
        return None

    return token, repo_parts[0], repo_parts[1]


async def _fetch_optional_context(
    args: argparse.Namespace, token: str, owner: str, repo: str
) -> tuple[str | None, str | None, str | None]:
    """Fetch optional context (logs, screenshots, traces) if requested."""
    job_logs_context = None
    screenshot_context = None
    trace_context = None

    if getattr(args, "include_logs", False):
        job_logs_context = await github_fetch.fetch_and_process_job_logs(
            token, owner, repo, args.run_id
        )
    if getattr(args, "include_screenshots", False):
        screenshot_context = await github_fetch.fetch_and_analyze_screenshots(
            token, owner, repo, args.run_id, args.artifact_name
        )
    if getattr(args, "include_traces", False):
        trace_context = await github_fetch.fetch_and_analyze_traces(
            token, owner, repo, args.run_id, args.artifact_name
        )

    return job_logs_context, screenshot_context, trace_context


async def run_fetch_github(args: argparse.Namespace) -> int:
    """Run the fetch-github command."""
    from heisenberg.integrations.github_artifacts import GitHubAPIError, GitHubArtifactClient

    validated = _validate_fetch_github_args(args)
    if validated is None:
        return 1

    token, owner, repo = validated

    try:
        if args.list_artifacts:
            return await github_fetch.list_artifacts(token, owner, repo, args.run_id)

        client = GitHubArtifactClient(token=token)
        run_id = args.run_id
        if run_id is None:
            run_id = await github_fetch._resolve_run_id(client, owner, repo, None)
        if run_id is None:
            print("No failed workflow runs found", file=sys.stderr)
            return 1
        report_data = await github_fetch.fetch_report(
            client, owner, repo, run_id, args.artifact_name
        )

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

        job_logs_context, screenshot_context, trace_context = await _fetch_optional_context(
            args, token, owner, repo
        )

        return _analyze_report_data(
            report_data, args, job_logs_context, screenshot_context, trace_context
        )

    except GitHubAPIError as e:
        print(f"GitHub API error: {e}", file=sys.stderr)
        print(
            "\nTip: For local reports, use: heisenberg analyze --report <path-to-json>",
            file=sys.stderr,
        )
        return 1
    except Exception as e:
        error_msg = str(e)
        if "blob" in error_msg.lower() or "merge" in error_msg.lower():
            print(f"Blob merge error: {e}", file=sys.stderr)
            print(
                "\nTip: Ensure Node.js and Playwright are installed: npm install -D @playwright/test",
                file=sys.stderr,
            )
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


async def run_freeze(args: argparse.Namespace) -> int:
    """Run the freeze command to create local artifact snapshots."""
    token = args.token or os.environ.get("GITHUB_TOKEN")

    config = FreezeConfig(
        repo=args.repo,
        output_dir=args.output,
        github_token=token,
        run_id=args.run_id,
    )

    freezer = CaseFreezer(config)

    try:
        result = await freezer.freeze()
        print(f"Frozen case: {result.id}")
        print(f"  Directory: {result.case_dir}")
        print(f"  Metadata: {result.metadata_path}")
        print(f"  Report: {result.report_path}")
        if result.trace_path:
            print(f"  Trace: {result.trace_path}")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error freezing case: {e}", file=sys.stderr)
        return 1


def run_analyze_case(args: argparse.Namespace) -> int:
    """Run the analyze-case command."""
    # Validate API key early
    provider = getattr(args, "provider", "google")
    error = validate_api_key_for_provider(provider)
    if error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if not args.case_dir.exists():
        print(f"Error: Case directory not found: {args.case_dir}", file=sys.stderr)
        return 1

    config = AnalyzeConfig(
        case_dir=args.case_dir,
        provider=provider,
        model=getattr(args, "model", None),
    )

    analyzer = ScenarioAnalyzer(config)

    try:
        result = analyzer.analyze()
        print(f"Analysis complete for: {result.repo}")
        print(f"  Root cause: {result.root_cause[:80]}...")
        print(f"  Confidence: {result.confidence}")
        print(f"  Tokens: {result.input_tokens + result.output_tokens}")
        print(f"  Saved: {args.case_dir / 'diagnosis.json'}")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error analyzing case: {e}", file=sys.stderr)
        return 1


def run_generate_manifest(args: argparse.Namespace) -> int:
    """Run the generate-manifest command."""
    if not args.cases_dir.exists():
        print(f"Error: Cases directory not found: {args.cases_dir}", file=sys.stderr)
        return 1

    config = GeneratorConfig(
        cases_dir=args.cases_dir,
        output_path=args.output,
        include_pending=getattr(args, "include_pending", False),
    )

    generator = ManifestGenerator(config)

    try:
        manifest = generator.generate_and_save()
        print(f"Manifest generated: {config.output_path}")
        print(f"  Total cases: {manifest.stats['total_cases']}")
        print(f"  HIGH confidence: {manifest.stats['high_confidence']}")
        print(f"  MEDIUM confidence: {manifest.stats['medium_confidence']}")
        print(f"  LOW confidence: {manifest.stats['low_confidence']}")
        if manifest.stats.get("pending", 0) > 0:
            print(f"  Pending: {manifest.stats['pending']}")
        return 0
    except Exception as e:
        print(f"Error generating manifest: {e}", file=sys.stderr)
        return 1


def _print_validation_issues(report) -> None:
    """Print validation issues for invalid/stale cases."""
    for result in report.results:
        if not result.is_valid:
            print(f"  [{result.status.value.upper()}] {result.case_id}")
            for issue in result.issues:
                print(f"    - {issue}")


def _print_validation_report(report, cases_dir) -> None:
    """Print human-readable validation report."""
    print(f"Validation Report for: {cases_dir}")
    print(f"  Total: {report.total}")
    print(f"  Valid: {report.valid}")
    print(f"  Stale: {report.stale}")
    print(f"  Invalid: {report.invalid}")

    if report.stale > 0 or report.invalid > 0:
        print("\nIssues found:")
        _print_validation_issues(report)


def run_validate_cases(args: argparse.Namespace) -> int:
    """Run the validate-cases command."""
    if not args.cases_dir.exists():
        print(f"Error: Cases directory not found: {args.cases_dir}", file=sys.stderr)
        return 1

    config = ValidatorConfig(
        cases_dir=args.cases_dir,
        max_age_days=args.max_age,
        require_diagnosis=not getattr(args, "no_require_diagnosis", False),
    )

    validator = CaseValidator(config)

    try:
        report = validator.generate_report()

        if getattr(args, "json", False):
            print(report.to_json())
        else:
            _print_validation_report(report, args.cases_dir)

        has_issues = report.invalid > 0 or report.stale > 0
        return 1 if has_issues else 0

    except Exception as e:
        print(f"Error validating cases: {e}", file=sys.stderr)
        return 1


# Human-readable status messages for single repo mode
_STATUS_MESSAGES: dict[SourceStatus, str] = {
    SourceStatus.COMPATIBLE: "Compatible - has Playwright artifacts with test failures",
    SourceStatus.NO_FAILURES: "No failures - Playwright artifacts exist but all tests pass",
    SourceStatus.HAS_ARTIFACTS: "Not Playwright - has artifacts but not Playwright format",
    SourceStatus.NO_ARTIFACTS: "No artifacts - workflow run exists but no artifacts found",
    SourceStatus.NO_FAILED_RUNS: "No failed runs - no recent failed workflow runs",
    SourceStatus.UNSUPPORTED_FORMAT: "HTML report - requires JSONL blob reporter format",
    SourceStatus.RATE_LIMITED: "Rate limited - GitHub API rate limit exceeded",
}


def _check_single_repo(args: argparse.Namespace) -> int:
    """Check a single repository for compatibility with Heisenberg."""
    source = analyze_source_with_status(
        repo=args.repo,
        verify_failures=not args.quick,
    )

    # JSON output
    if args.json_output:
        output_data = {
            "repo": source.repo,
            "stars": source.stars,
            "compatible": source.compatible,
            "status": source.status.value,
            "artifacts": source.artifact_names,
            "playwright_artifacts": source.playwright_artifacts,
            "run_id": source.run_id,
            "run_url": source.run_url,
        }
        json.dump(output_data, sys.stdout, indent=2)
        print()
    else:
        # Human-readable output
        message = _STATUS_MESSAGES.get(source.status, f"Unknown status: {source.status}")
        icon = "\u2713" if source.compatible else "\u2717"
        print(f"\n{args.repo}")
        print(f"  {icon} {message}")
        if source.stars:
            print(f"  Stars: {source.stars:,}")
        if source.artifact_names:
            print(f"  Artifacts: {', '.join(source.artifact_names)}")
        if source.run_url:
            print(f"  Run: {source.run_url}")
        print()

    return 0 if source.compatible else 1


def run_discover(args: argparse.Namespace) -> int:
    """Run the discover command to find GitHub repos with Playwright artifacts."""
    # Single repo mode - check specific repository
    if args.repo:
        return _check_single_repo(args)

    # JSON mode implies quiet
    quiet = args.quiet or args.json_output

    # Determine cache paths
    cache_path = None if args.no_cache else _USE_DEFAULT_CACHE
    quarantine_path = None if (args.no_cache or args.fresh) else _USE_DEFAULT_QUARANTINE

    # Create display handler
    display = DiscoveryDisplay(verbose=args.verbose, quiet=quiet)

    # Run discovery
    sources = discover_sources(
        global_limit=args.limit,
        verify_failures=not args.quick,
        on_event=display.handle,
        cache_path=cache_path,
        quarantine_path=quarantine_path,
        min_stars=args.min_stars,
    )

    # JSON output to stdout
    if args.json_output:
        output_data = [
            {
                "repo": s.repo,
                "stars": s.stars,
                "compatible": s.compatible,
                "status": s.status.value,
                "artifacts": s.artifact_names,
                "playwright_artifacts": s.playwright_artifacts,
                "run_id": s.run_id,
                "run_url": s.run_url,
            }
            for s in sources
        ]
        json.dump(output_data, sys.stdout, indent=2)
        print()  # Newline at end

    # Save to file if requested
    if args.output:
        from heisenberg.discovery.ui import save_results

        save_results(sources, str(args.output))

    return 0
