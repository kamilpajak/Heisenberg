"""CLI argument parser and main entry point."""

from __future__ import annotations

import argparse
import json
import sys

from .display import DiscoveryDisplay
from .service import _USE_DEFAULT_CACHE, _USE_DEFAULT_QUARANTINE, discover_sources


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="Discover GitHub repos with Playwright test artifacts"
    )

    # Filtering
    filter_group = parser.add_argument_group("filtering")
    filter_group.add_argument(
        "--min-stars",
        type=int,
        default=100,
        metavar="N",
        help="Minimum stars (default: 100)",
    )
    filter_group.add_argument(
        "--limit",
        type=int,
        default=30,
        metavar="N",
        help="Max repos to analyze (default: 30)",
    )

    # Caching
    cache_group = parser.add_argument_group("caching")
    cache_group.add_argument(
        "--no-cache",
        action="store_true",
        dest="no_cache",
        help="Disable all caching (slowest, freshest results)",
    )
    cache_group.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore quarantine cache (re-check previously filtered repos)",
    )

    # Verification
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Download artifacts to verify failures exist (slower)",
    )

    # Output modes
    output_group = parser.add_argument_group("output")
    output_group.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all repos during analysis (not just compatible)",
    )
    output_group.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only show final summary",
    )
    output_group.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON to stdout (implies --quiet)",
    )
    output_group.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="Save results to JSON file",
    )

    return parser


def main() -> None:
    """Main entry point for CLI."""
    parser = create_argument_parser()
    args = parser.parse_args()

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
        verify_failures=args.verify,
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
        from .ui import save_results

        save_results(sources, args.output)
