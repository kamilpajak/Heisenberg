"""Main Typer CLI application for Heisenberg."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Annotated

import typer

from heisenberg.cli.case import case_app

app = typer.Typer(
    name="heisenberg",
    help="AI Root Cause Analysis for Flaky Tests",
    no_args_is_help=True,
)

# Register subcommand group
app.add_typer(case_app, name="case")

# Pattern for GitHub repo format: owner/repo (allows alphanumeric, dash, underscore, dot)
GITHUB_REPO_PATTERN = re.compile(r"^[\w-]+/[\w.-]+$")


def is_github_repo(target: str) -> bool:
    """Check if target looks like a GitHub repo (owner/repo format)."""
    return bool(GITHUB_REPO_PATTERN.match(target))


@app.command()
def analyze(
    target: Annotated[
        str,
        typer.Argument(
            help="Path to local report file OR GitHub repo (owner/repo)",
        ),
    ],
    output_format: Annotated[
        str,
        typer.Option(
            "-f",
            "--output-format",
            help="Output format",
        ),
    ] = "text",
    ai_analysis: Annotated[
        bool,
        typer.Option(
            "-a",
            "--ai-analysis",
            help="Enable AI-powered analysis",
        ),
    ] = False,
    provider: Annotated[
        str,
        typer.Option(
            "-p",
            "--provider",
            help="LLM provider (anthropic, openai, google)",
        ),
    ] = "google",
    model: Annotated[
        str | None,
        typer.Option(
            "-m",
            "--model",
            help="Specific model name",
        ),
    ] = None,
    docker_services: Annotated[
        str | None,
        typer.Option(
            "-d",
            "--docker-services",
            help="Docker services for logs (comma-separated)",
        ),
    ] = None,
    log_window: Annotated[
        int,
        typer.Option(
            "-w",
            "--log-window",
            help="Log collection window in seconds",
        ),
    ] = 30,
    post_comment: Annotated[
        bool,
        typer.Option(
            "--post-comment",
            help="Post result to GitHub PR",
        ),
    ] = False,
    container_logs: Annotated[
        Path | None,
        typer.Option(
            "-l",
            "--container-logs",
            help="Path to container logs file",
        ),
    ] = None,
    report_format: Annotated[
        str,
        typer.Option(
            "--report-format",
            help="Report format (playwright, junit)",
        ),
    ] = "playwright",
    # GitHub-specific options (used when target is owner/repo)
    token: Annotated[
        str | None,
        typer.Option(
            "-t",
            "--token",
            help="GitHub token (or set GITHUB_TOKEN)",
            envvar="GITHUB_TOKEN",
        ),
    ] = None,
    run_id: Annotated[
        int | None,
        typer.Option(
            "--run-id",
            help="Specific workflow run ID",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Save report to file instead of analyzing",
        ),
    ] = None,
    artifact_name: Annotated[
        str | None,
        typer.Option(
            "--artifact-name",
            help="Pattern to match artifact name",
        ),
    ] = None,
    list_artifacts: Annotated[
        bool,
        typer.Option(
            "--list-artifacts",
            help="List available artifacts (debug mode)",
        ),
    ] = False,
    include_logs: Annotated[
        bool,
        typer.Option(
            "--include-logs",
            help="Include GitHub Actions job logs",
        ),
    ] = False,
    include_screenshots: Annotated[
        bool,
        typer.Option(
            "--include-screenshots",
            help="Analyze failure screenshots",
        ),
    ] = False,
    include_traces: Annotated[
        bool,
        typer.Option(
            "--include-traces",
            help="Extract and analyze Playwright traces",
        ),
    ] = False,
) -> None:
    """Analyze test failures from a local report or GitHub repository.

    TARGET can be:
    - A local file path: ./report.json
    - A GitHub repo: owner/repo
    """
    if is_github_repo(target):
        exit_code = asyncio.run(
            _analyze_github(
                repo=target,
                output_format=output_format,
                ai_analysis=ai_analysis,
                provider=provider,
                model=model,
                token=token,
                run_id=run_id,
                output=output,
                artifact_name=artifact_name,
                list_artifacts=list_artifacts,
                include_logs=include_logs,
                include_screenshots=include_screenshots,
                include_traces=include_traces,
            )
        )
    else:
        exit_code = _analyze_local(
            report_path=Path(target),
            output_format=output_format,
            ai_analysis=ai_analysis,
            provider=provider,
            model=model,
            docker_services=docker_services,
            log_window=log_window,
            post_comment=post_comment,
            container_logs=container_logs,
            report_format=report_format,
        )
    raise typer.Exit(code=exit_code)


def _analyze_local(
    report_path: Path,
    output_format: str,
    ai_analysis: bool,
    provider: str,
    model: str | None,
    docker_services: str | None,
    log_window: int,
    post_comment: bool,
    container_logs: Path | None,
    report_format: str,
) -> int:
    """Analyze a local Playwright/JUnit report."""
    import argparse

    from heisenberg.cli.commands import run_analyze

    # Build args namespace to reuse existing handler
    args = argparse.Namespace(
        report=report_path,
        output_format=output_format,
        ai_analysis=ai_analysis,
        provider=provider,
        model=model,
        docker_services=docker_services.split(",") if docker_services else None,
        log_window=log_window,
        post_comment=post_comment,
        container_logs=container_logs,
        report_format=report_format,
    )

    return run_analyze(args)


async def _analyze_github(
    repo: str,
    output_format: str,
    ai_analysis: bool,
    provider: str,
    model: str | None,
    token: str | None,
    run_id: int | None,
    output: Path | None,
    artifact_name: str | None,
    list_artifacts: bool,
    include_logs: bool,
    include_screenshots: bool,
    include_traces: bool,
) -> int:
    """Fetch and analyze Playwright reports from GitHub."""
    import argparse

    from heisenberg.cli.commands import run_fetch_github

    # Build args namespace to reuse existing handler
    args = argparse.Namespace(
        repo=repo,
        output_format=output_format,
        ai_analysis=ai_analysis,
        provider=provider,
        model=model,
        token=token,
        run_id=run_id,
        output=output,
        artifact_name=artifact_name,
        list_artifacts=list_artifacts,
        include_logs=include_logs,
        include_screenshots=include_screenshots,
        include_traces=include_traces,
    )

    return await run_fetch_github(args)


@app.command()
def discover(
    repo: Annotated[
        str | None,
        typer.Option(
            "--repo",
            help="Check specific repo (owner/repo)",
        ),
    ] = None,
    min_stars: Annotated[
        int,
        typer.Option(
            "--min-stars",
            help="Minimum stars filter",
        ),
    ] = 100,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            help="Maximum repos to analyze",
        ),
    ] = 30,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help="Disable all caching",
        ),
    ] = False,
    fresh: Annotated[
        bool,
        typer.Option(
            "--fresh",
            help="Ignore quarantine cache",
        ),
    ] = False,
    quick: Annotated[
        bool,
        typer.Option(
            "--quick",
            help="Skip failure verification",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "-v",
            "--verbose",
            help="Show all repos during analysis",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "-q",
            "--quiet",
            help="Only show final summary",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Output JSON to stdout",
        ),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Save results to JSON file",
        ),
    ] = None,
) -> None:
    """Discover GitHub repos with Playwright artifacts.

    Without --repo, searches for compatible repositories.
    With --repo, checks if a specific repository is compatible.
    """
    import argparse

    from heisenberg.cli.commands import run_discover

    # Build args namespace to reuse existing handler
    args = argparse.Namespace(
        repo=repo,
        min_stars=min_stars,
        limit=limit,
        no_cache=no_cache,
        fresh=fresh,
        quick=quick,
        verbose=verbose,
        quiet=quiet,
        json_output=json_output,
        output=output,
    )

    exit_code = run_discover(args)
    raise typer.Exit(code=exit_code)


def main() -> None:
    """Entry point for the Typer CLI."""
    app()
