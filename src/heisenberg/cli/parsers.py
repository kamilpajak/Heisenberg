"""Argument parsers for Heisenberg CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

# Shared help text constants
_PROVIDER_HELP = "LLM provider to use (default: google)"


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="heisenberg",
        description="AI Root Cause Analysis for Flaky Tests",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_analyze_parser(subparsers)
    _add_fetch_github_parser(subparsers)
    _add_freeze_parser(subparsers)
    _add_analyze_case_parser(subparsers)
    _add_generate_manifest_parser(subparsers)
    _add_validate_cases_parser(subparsers)
    _add_discover_parser(subparsers)

    return parser


def _add_analyze_parser(subparsers) -> None:
    """Add the analyze subcommand parser."""
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
        choices=["anthropic", "openai", "google"],
        default="google",
        help=_PROVIDER_HELP,
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
        "--report-format",
        choices=["playwright", "junit"],
        default="playwright",
        help="Format of the test report (default: playwright)",
    )


def _add_fetch_github_parser(subparsers) -> None:
    """Add the fetch-github subcommand parser."""
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
        default=None,
        help="Pattern to match artifact name (default: auto-select based on failed jobs)",
    )
    fetch_parser.add_argument(
        "--ai-analysis",
        "-a",
        action="store_true",
        help="Enable AI-powered root cause analysis",
    )
    fetch_parser.add_argument(
        "--output-format",
        "-f",
        choices=["github-comment", "json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    fetch_parser.add_argument(
        "--provider",
        "-p",
        choices=["anthropic", "openai", "google"],
        default="google",
        help=_PROVIDER_HELP,
    )
    fetch_parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Specific model to use (provider-dependent)",
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


def _add_freeze_parser(subparsers) -> None:
    """Add the freeze subcommand parser."""
    freeze_parser = subparsers.add_parser(
        "freeze",
        help="Freeze GitHub Actions artifacts into local snapshots for demo",
    )
    freeze_parser.add_argument(
        "--repo",
        "-r",
        type=str,
        required=True,
        help="GitHub repository in owner/repo format",
    )
    freeze_parser.add_argument(
        "--run-id",
        type=int,
        default=None,
        help="Specific workflow run ID (default: latest failed)",
    )
    freeze_parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("./cases"),
        help="Output directory for frozen cases (default: ./cases)",
    )
    freeze_parser.add_argument(
        "--token",
        "-t",
        type=str,
        default=None,
        help="GitHub token (or set GITHUB_TOKEN env var)",
    )


def _add_analyze_case_parser(subparsers) -> None:
    """Add the analyze-case subcommand parser."""
    parser = subparsers.add_parser(
        "analyze-case",
        help="Run AI analysis on a frozen case",
    )
    parser.add_argument(
        "case_dir",
        type=Path,
        help="Path to the frozen case directory",
    )
    parser.add_argument(
        "--provider",
        "-p",
        choices=["anthropic", "openai", "google"],
        default="google",
        help=_PROVIDER_HELP,
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Specific model to use (provider-dependent)",
    )


def _add_generate_manifest_parser(subparsers) -> None:
    """Add the generate-manifest subcommand parser."""
    parser = subparsers.add_parser(
        "generate-manifest",
        help="Generate manifest.json from frozen cases",
    )
    parser.add_argument(
        "cases_dir",
        type=Path,
        help="Path to the cases directory",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output path for manifest.json (default: cases_dir/manifest.json)",
    )
    parser.add_argument(
        "--include-pending",
        action="store_true",
        help="Include cases without diagnosis (pending analysis)",
    )


def _add_validate_cases_parser(subparsers) -> None:
    """Add the validate-cases subcommand parser."""
    parser = subparsers.add_parser(
        "validate-cases",
        help="Validate frozen cases for freshness and completeness",
    )
    parser.add_argument(
        "cases_dir",
        type=Path,
        help="Path to the cases directory",
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=90,
        help="Maximum age in days before case is considered stale (default: 90)",
    )
    parser.add_argument(
        "--no-require-diagnosis",
        action="store_true",
        help="Don't require diagnosis.json (allow pending cases)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )


def _add_discover_parser(subparsers) -> None:
    """Add the discover subcommand parser."""
    parser = subparsers.add_parser(
        "discover",
        help="Discover GitHub repos with Playwright test artifacts",
    )

    # Filtering
    parser.add_argument(
        "--min-stars",
        type=int,
        default=100,
        metavar="N",
        help="Minimum stars (default: 100)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        metavar="N",
        help="Max repos to analyze (default: 30)",
    )

    # Caching
    parser.add_argument(
        "--no-cache",
        action="store_true",
        dest="no_cache",
        help="Disable all caching (slowest, freshest results)",
    )
    parser.add_argument(
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
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all repos during analysis (not just compatible)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only show final summary",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON to stdout (implies --quiet)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        metavar="FILE",
        help="Save results to JSON file",
    )
