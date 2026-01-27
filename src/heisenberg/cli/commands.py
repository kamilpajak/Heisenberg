"""Command handlers for Heisenberg CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from heisenberg.cli import formatters, github_fetch
from heisenberg.core.analyzer import analyze_unified_run, analyze_with_ai
from heisenberg.core.legacy_analyzer import run_analysis
from heisenberg.core.models import PlaywrightTransformer, UnifiedTestRun
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
            provider=getattr(args, "provider", "anthropic"),
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
        provider = getattr(args, "provider", "anthropic")
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
                        provider=getattr(args, "provider", "anthropic"),
                        model=getattr(args, "model", None),
                        job_logs_context=job_logs_context,
                        screenshot_context=screenshot_context,
                        trace_context=trace_context,
                    )
                else:
                    ai_result = analyze_with_ai(
                        report=result.report,
                        provider=getattr(args, "provider", "anthropic"),
                        model=getattr(args, "model", None),
                    )
            except Exception as e:
                print(f"Warning: AI analysis failed: {e}", file=sys.stderr)

        print(formatters.format_text_output(result, ai_result))
        return 1 if result.has_failures else 0
    finally:
        temp_path.unlink()


async def run_fetch_github(args: argparse.Namespace) -> int:
    """Run the fetch-github command."""
    from heisenberg.integrations.github_artifacts import GitHubAPIError, GitHubArtifactClient

    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GitHub token required. Use --token or set GITHUB_TOKEN", file=sys.stderr)
        print(
            "\nTip: For local reports, use: heisenberg analyze --report <path-to-json>",
            file=sys.stderr,
        )
        return 1

    # Validate API key early if AI analysis is requested (fail fast)
    if getattr(args, "ai_analysis", False):
        provider = getattr(args, "provider", "anthropic")
        error = validate_api_key_for_provider(provider)
        if error:
            print(f"Error: {error}", file=sys.stderr)
            return 1

    repo_parts = args.repo.split("/")
    if len(repo_parts) != 2:
        print("Error: Invalid repo format. Use owner/repo", file=sys.stderr)
        return 1

    owner, repo = repo_parts

    try:
        if args.list_artifacts:
            return await github_fetch.list_artifacts(token, owner, repo, args.run_id)

        if args.merge_blobs:
            report_data = await github_fetch.fetch_and_merge_blobs(
                token, owner, repo, args.run_id, args.artifact_name
            )
        else:
            client = GitHubArtifactClient(token=token)
            if args.run_id:
                report_data = await github_fetch.fetch_report_from_run(
                    client, owner, repo, args.run_id, args.artifact_name
                )
            else:
                report_data = await client.fetch_latest_report(
                    owner, repo, artifact_name_pattern=args.artifact_name
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

        job_logs_context = None
        if getattr(args, "include_logs", False):
            job_logs_context = await github_fetch.fetch_and_process_job_logs(
                token, owner, repo, args.run_id
            )

        screenshot_context = None
        if getattr(args, "include_screenshots", False):
            screenshot_context = await github_fetch.fetch_and_analyze_screenshots(
                token, owner, repo, args.run_id, args.artifact_name
            )

        trace_context = None
        if getattr(args, "include_traces", False):
            trace_context = await github_fetch.fetch_and_analyze_traces(
                token, owner, repo, args.run_id, args.artifact_name
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
        print(f"Error freezing scenario: {e}", file=sys.stderr)
        return 1


def run_analyze_case(args: argparse.Namespace) -> int:
    """Run the analyze-case command."""
    # Validate API key early
    provider = getattr(args, "provider", "anthropic")
    error = validate_api_key_for_provider(provider)
    if error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if not args.case_dir.exists():
        print(f"Error: Scenario directory not found: {args.case_dir}", file=sys.stderr)
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
        print(f"Error analyzing scenario: {e}", file=sys.stderr)
        return 1


def run_generate_manifest(args: argparse.Namespace) -> int:
    """Run the generate-manifest command."""
    if not args.cases_dir.exists():
        print(f"Error: Scenarios directory not found: {args.cases_dir}", file=sys.stderr)
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
        print(f"  Total scenarios: {manifest.stats['total_scenarios']}")
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
        print(f"Error: Scenarios directory not found: {args.cases_dir}", file=sys.stderr)
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
        print(f"Error validating scenarios: {e}", file=sys.stderr)
        return 1
