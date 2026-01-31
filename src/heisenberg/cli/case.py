"""Case subcommand group for Heisenberg CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

case_app = typer.Typer(
    name="case",
    help="Manage frozen test cases for analysis",
    no_args_is_help=True,
)


@case_app.command()
def freeze(
    repo: Annotated[
        str,
        typer.Option(
            "-r",
            "--repo",
            help="GitHub repository (owner/repo)",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "-o",
            "--output",
            help="Output directory for frozen cases",
        ),
    ] = Path("./cases"),
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
) -> None:
    """Freeze artifacts from a GitHub repository for offline analysis.

    Creates a local snapshot of test artifacts including reports,
    traces, and metadata for later analysis.
    """
    exit_code = asyncio.run(_freeze_impl(repo, output, token, run_id))
    raise typer.Exit(code=exit_code)


async def _freeze_impl(
    repo: str,
    output: Path,
    token: str | None,
    run_id: int | None,
) -> int:
    """Implementation of freeze command."""
    import argparse

    from heisenberg.cli.commands import run_freeze

    args = argparse.Namespace(
        repo=repo,
        output=output,
        token=token,
        run_id=run_id,
    )

    return await run_freeze(args)


@case_app.command()
def replay(
    case_dir: Annotated[
        Path,
        typer.Argument(
            help="Path to frozen case directory",
        ),
    ],
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
) -> None:
    """Run AI analysis on a frozen test case.

    Analyzes a previously frozen case directory and generates
    a diagnosis with root cause analysis.
    """
    exit_code = _replay_impl(case_dir, provider, model)
    raise typer.Exit(code=exit_code)


def _replay_impl(case_dir: Path, provider: str, model: str | None) -> int:
    """Implementation of replay command."""
    import argparse

    from heisenberg.cli.commands import run_analyze_case

    args = argparse.Namespace(
        case_dir=case_dir,
        provider=provider,
        model=model,
    )

    return run_analyze_case(args)


@case_app.command()
def validate(
    cases_dir: Annotated[
        Path,
        typer.Argument(
            help="Path to cases directory",
        ),
    ],
    max_age: Annotated[
        int,
        typer.Option(
            "--max-age",
            help="Maximum age in days before stale",
        ),
    ] = 90,
    no_require_diagnosis: Annotated[
        bool,
        typer.Option(
            "--no-require-diagnosis",
            help="Allow cases without diagnosis",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Output results as JSON",
        ),
    ] = False,
) -> None:
    """Validate frozen cases for freshness and completeness.

    Checks that cases are not stale and have required files.
    Returns exit code 1 if issues are found.
    """
    exit_code = _validate_impl(cases_dir, max_age, no_require_diagnosis, json_output)
    raise typer.Exit(code=exit_code)


def _validate_impl(
    cases_dir: Path,
    max_age: int,
    no_require_diagnosis: bool,
    json_output: bool,
) -> int:
    """Implementation of validate command."""
    import argparse

    from heisenberg.cli.commands import run_validate_cases

    args = argparse.Namespace(
        cases_dir=cases_dir,
        max_age=max_age,
        no_require_diagnosis=no_require_diagnosis,
        json=json_output,
    )

    return run_validate_cases(args)


@case_app.command()
def index(
    cases_dir: Annotated[
        Path,
        typer.Argument(
            help="Path to cases directory",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Output path for manifest (default: cases_dir/manifest.json)",
        ),
    ] = None,
    include_pending: Annotated[
        bool,
        typer.Option(
            "--include-pending",
            help="Include cases without diagnosis",
        ),
    ] = False,
) -> None:
    """Generate manifest.json from frozen cases.

    Creates an index of all cases with their diagnosis status
    and confidence levels for quick reference.
    """
    exit_code = _index_impl(cases_dir, output, include_pending)
    raise typer.Exit(code=exit_code)


def _index_impl(
    cases_dir: Path,
    output: Path | None,
    include_pending: bool,
) -> int:
    """Implementation of index command."""
    import argparse

    from heisenberg.cli.commands import run_generate_manifest

    # Default output path if not provided
    if output is None:
        output = cases_dir / "manifest.json"

    args = argparse.Namespace(
        cases_dir=cases_dir,
        output=output,
        include_pending=include_pending,
    )

    return run_generate_manifest(args)
