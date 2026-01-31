"""CLI argument parser and main entry point."""

from __future__ import annotations

import argparse
import json
import sys

from .analysis import analyze_source_with_status
from .display import DiscoveryDisplay
from .models import SourceStatus
from .service import _USE_DEFAULT_CACHE, _USE_DEFAULT_QUARANTINE, discover_sources

# Human-readable status messages for single repo mode
STATUS_MESSAGES: dict[SourceStatus, str] = {
    SourceStatus.COMPATIBLE: "✓ Compatible - has Playwright artifacts with test failures",
    SourceStatus.NO_FAILURES: "✗ No failures - Playwright artifacts exist but all tests pass",
    SourceStatus.HAS_ARTIFACTS: "✗ Not Playwright - has artifacts but not Playwright format",
    SourceStatus.NO_ARTIFACTS: "✗ No artifacts - workflow run exists but no artifacts found",
    SourceStatus.NO_FAILED_RUNS: "✗ No failed runs - no recent failed workflow runs",
    SourceStatus.UNSUPPORTED_FORMAT: "✗ HTML report - requires JSONL blob reporter format",
    SourceStatus.RATE_LIMITED: "✗ Rate limited - GitHub API rate limit exceeded",
}


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="Discover GitHub repos with Playwright test artifacts"
    )

    # Single repo mode
    parser.add_argument(
        "--repo",
        metavar="OWNER/REPO",
        help="Check specific repository instead of searching GitHub",
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
        "--quick",
        action="store_true",
        help="Skip failure verification (faster, may include repos with 0 failures)",
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


def _check_single_repo(args: argparse.Namespace) -> None:
    """Check a single repository for compatibility."""
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
        message = STATUS_MESSAGES.get(source.status, f"Unknown status: {source.status}")
        print(f"\n{args.repo}")
        print(f"  {message}")
        if source.stars:
            print(f"  Stars: {source.stars:,}")
        if source.artifact_names:
            print(f"  Artifacts: {', '.join(source.artifact_names)}")
        if source.run_url:
            print(f"  Run: {source.run_url}")
        print()

    # Exit code based on compatibility
    sys.exit(0 if source.compatible else 1)


def main() -> None:
    """Main entry point for CLI."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Single repo mode - check specific repository
    if args.repo:
        _check_single_repo(args)
        return

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
        from .ui import save_results

        save_results(sources, args.output)
