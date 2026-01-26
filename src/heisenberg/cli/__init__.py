"""CLI package for Heisenberg."""

import asyncio

from heisenberg.cli.commands import run_analyze, run_fetch_github
from heisenberg.cli.parsers import create_parser


def main() -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "analyze":
        return run_analyze(args)
    elif args.command == "fetch-github":
        return asyncio.run(run_fetch_github(args))

    return 1


__all__ = ["create_parser", "main"]
