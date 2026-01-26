"""Argument parsers for Heisenberg CLI."""

from __future__ import annotations

import argparse
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="heisenberg",
        description="AI Root Cause Analysis for Flaky Tests",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_analyze_parser(subparsers)
    _add_fetch_github_parser(subparsers)

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
        default="anthropic",
        help="LLM provider to use (default: anthropic)",
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
        "--use-unified",
        action="store_true",
        help="Use unified failure model for analysis (framework-agnostic)",
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
        default="playwright",
        help="Pattern to match artifact name (default: playwright)",
    )
    fetch_parser.add_argument(
        "--ai-analysis",
        "-a",
        action="store_true",
        help="Enable AI-powered root cause analysis",
    )
    fetch_parser.add_argument(
        "--provider",
        "-p",
        choices=["anthropic", "openai", "google"],
        default="anthropic",
        help="LLM provider to use (default: anthropic)",
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
