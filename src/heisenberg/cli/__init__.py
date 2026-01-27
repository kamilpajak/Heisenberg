"""CLI package for Heisenberg."""

import asyncio

from heisenberg.cli.commands import (
    run_analyze,
    run_analyze_scenario,
    run_fetch_github,
    run_freeze,
    run_generate_manifest,
    run_validate_scenarios,
)
from heisenberg.cli.parsers import create_parser


def main() -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "analyze":
        return run_analyze(args)
    elif args.command == "fetch-github":
        return asyncio.run(run_fetch_github(args))
    elif args.command == "freeze":
        return asyncio.run(run_freeze(args))
    elif args.command == "analyze-scenario":
        return run_analyze_scenario(args)
    elif args.command == "generate-manifest":
        return run_generate_manifest(args)
    elif args.command == "validate-scenarios":
        return run_validate_scenarios(args)

    return 1


__all__ = [
    "create_parser",
    "main",
    "run_analyze_scenario",
    "run_freeze",
    "run_generate_manifest",
    "run_validate_scenarios",
]
