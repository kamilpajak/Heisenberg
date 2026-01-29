"""CLI argument parser and main entry point."""

from __future__ import annotations

import argparse

from .analysis import filter_by_min_stars
from .service import _USE_DEFAULT_CACHE, _USE_DEFAULT_QUARANTINE, discover_sources
from .ui import print_summary, save_results


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser for CLI."""
    parser = argparse.ArgumentParser(description="Discover projects for Heisenberg testing")
    parser.add_argument("--min-stars", type=int, default=100, help="Minimum stars")
    parser.add_argument("--limit", type=int, default=30, help="Max repos to analyze (global)")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Download artifacts to verify they have actual failures (slower)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        dest="no_cache",
        help="Disable verification cache (force re-download of artifacts)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore quarantine cache (re-analyze all repos)",
    )
    return parser


def main() -> None:
    """Main entry point for CLI."""
    parser = create_argument_parser()
    args = parser.parse_args()

    print("Searching GitHub for Playwright projects with artifacts...\n")
    if args.verify:
        cache_info = " (cache disabled)" if args.no_cache else ""
        print(f"Verification enabled - downloading artifacts to check for failures{cache_info}\n")

    # Determine cache_path: None to disable, or use default
    cache_path = None if args.no_cache else _USE_DEFAULT_CACHE

    # Determine quarantine_path: None if --no-cache or --fresh, else default
    quarantine_path = None if (args.no_cache or args.fresh) else _USE_DEFAULT_QUARANTINE

    sources = discover_sources(
        global_limit=args.limit,
        verify_failures=args.verify,
        show_progress=True,  # Use Rich progress display
        cache_path=cache_path,
        quarantine_path=quarantine_path,
    )

    total_analyzed = len(sources)
    sources = filter_by_min_stars(sources, min_stars=args.min_stars)

    print_summary(sources, args.min_stars, total_analyzed=total_analyzed)

    if args.output:
        save_results(sources, args.output)
