#!/usr/bin/env python3
"""Discover GitHub projects suitable for Heisenberg testing.

This script searches GitHub for repositories that:
1. Use Playwright for E2E testing
2. Upload test artifacts to GitHub Actions
3. Have recent failed workflow runs
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class ProjectCandidate:
    """A candidate project for testing."""

    repo: str
    stars: int
    has_artifacts: bool
    artifact_names: list[str]
    run_id: str | None
    run_url: str | None
    compatible: bool
    notes: str


def gh_api(endpoint: str, params: dict | None = None) -> dict | list | None:
    """Call GitHub API via gh CLI."""
    cmd = ["gh", "api", endpoint]
    if params:
        for k, v in params.items():
            cmd.extend(["-f", f"{k}={v}"])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout) if result.stdout.strip() else None
    except subprocess.CalledProcessError as e:
        # Log rate limit warnings
        if e.stderr and "rate limit" in e.stderr.lower():
            print(f"⚠️  Rate limit hit: {endpoint}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        return None


def search_repos(query: str, limit: int = 30) -> list[str]:
    """Search GitHub for repositories matching query.

    Returns list of unique repo names.
    Note: /search/code doesn't return stargazers_count, so stars
    must be fetched separately via analyze_candidate.
    """
    import urllib.parse

    encoded_query = urllib.parse.quote(query)
    endpoint = f"/search/code?q={encoded_query}&per_page={min(limit, 100)}"

    cmd = ["gh", "api", "-X", "GET", endpoint]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return []

    if not data or "items" not in data:
        return []

    # Extract unique repo names (stars not available in /search/code)
    seen: set[str] = set()
    for item in data["items"][:limit]:
        repo_data = item.get("repository", {})
        repo_name = repo_data.get("full_name", "")
        if repo_name:
            seen.add(repo_name)

    return list(seen)


def get_repo_stars(repo: str) -> int:
    """Get star count for a repository."""
    data = gh_api(f"/repos/{repo}")
    return data.get("stargazers_count", 0) if data else 0


def check_artifacts(repo: str) -> tuple[str | None, str | None, list[str]]:
    """Check if repo has artifacts in recent failed runs.

    Checks multiple failed runs (up to 5) to find valid artifacts.
    Skips expired artifacts.
    """
    # Get multiple failed runs (not just the latest)
    cmd = [
        "gh", "api", "-X", "GET",
        f"/repos/{repo}/actions/runs?status=failure&per_page=5"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None, None, []

    if not data or not data.get("workflow_runs"):
        return None, None, []

    # Check each run until we find one with valid artifacts
    for run in data["workflow_runs"]:
        run_id = str(run["id"])
        run_url = run.get("html_url", "")

        # Get artifacts for this run
        artifacts_data = gh_api(f"/repos/{repo}/actions/runs/{run_id}/artifacts")
        if not artifacts_data or not artifacts_data.get("artifacts"):
            continue

        # Filter out expired artifacts
        valid_artifacts = [
            a["name"]
            for a in artifacts_data["artifacts"]
            if not a.get("expired", False)
        ]

        if valid_artifacts:
            return run_id, run_url, valid_artifacts

    # No runs with valid artifacts found
    first_run = data["workflow_runs"][0]
    return str(first_run["id"]), first_run.get("html_url", ""), []


# Strict patterns for Playwright artifacts
PLAYWRIGHT_PATTERNS = [
    r"^playwright[-_]?report",      # playwright-report, playwright_report
    r"^blob[-_]?report",            # blob-report (Playwright sharding)
    r"^playwright[-_]?traces?",     # playwright-trace, playwright-traces
    r"^trace\.zip$",                # trace.zip
    r"playwright.*report",          # any-playwright-report
]

_PLAYWRIGHT_REGEX = re.compile(
    "|".join(PLAYWRIGHT_PATTERNS),
    re.IGNORECASE
)


def is_playwright_artifact(name: str) -> bool:
    """Check if artifact name suggests Playwright report.

    Uses strict regex patterns to avoid false positives like
    'coverage-report' or 'cypress-e2e-results'.
    """
    return bool(_PLAYWRIGHT_REGEX.search(name))


def analyze_candidate(repo: str, stars: int | None = None) -> ProjectCandidate:
    """Analyze a repository as a candidate for testing.

    Args:
        repo: Repository in owner/repo format
        stars: Optional star count (avoids API call if provided)
    """
    # Use provided stars or fetch from API
    if stars is None:
        stars = get_repo_stars(repo)

    run_id, run_url, artifact_names = check_artifacts(repo)

    has_artifacts = len(artifact_names) > 0
    playwright_artifacts = [a for a in artifact_names if is_playwright_artifact(a)]
    compatible = len(playwright_artifacts) > 0

    if not run_id:
        notes = "No failed runs"
    elif not has_artifacts:
        notes = "No artifacts"
    elif not compatible:
        notes = f"Artifacts: {', '.join(artifact_names[:3])}"
    else:
        notes = f"✓ {', '.join(playwright_artifacts[:3])}"

    return ProjectCandidate(
        repo=repo,
        stars=stars,
        has_artifacts=has_artifacts,
        artifact_names=artifact_names,
        run_id=run_id,
        run_url=run_url,
        compatible=compatible,
        notes=notes,
    )


def filter_by_min_stars(
    candidates: list[ProjectCandidate],
    min_stars: int = 100
) -> list[ProjectCandidate]:
    """Filter candidates by minimum star count."""
    return [c for c in candidates if c.stars >= min_stars]


def discover_candidates(
    global_limit: int = 30,
    min_stars: int = 100,
    queries: list[str] | None = None,
) -> list[ProjectCandidate]:
    """Discover candidate projects from GitHub.

    Args:
        global_limit: Maximum total repos to analyze across all queries
        min_stars: Minimum star count to include
        queries: Custom search queries (uses defaults if None)

    Returns:
        List of analyzed ProjectCandidate objects
    """
    if queries is None:
        queries = [
            'playwright "upload-artifact" path:.github/workflows extension:yml',
            '"blob-report" "upload-artifact" path:.github/workflows',
            '"playwright-report" "actions/upload-artifact" path:.github/workflows',
        ]

    # Collect unique repos from all queries
    all_repos: set[str] = set()
    for query in queries:
        results = search_repos(query, limit=global_limit)
        all_repos.update(results)
        # Stop if we have enough
        if len(all_repos) >= global_limit:
            break

    # Analyze candidates (stars fetched via API in analyze_candidate)
    candidates = []
    for repo in list(all_repos)[:global_limit]:
        candidate = analyze_candidate(repo)
        candidates.append(candidate)

    # Filter by min_stars
    candidates = filter_by_min_stars(candidates, min_stars=min_stars)

    # Sort by compatibility, then stars
    candidates.sort(key=lambda c: (-c.compatible, -c.stars))

    return candidates


def main():
    parser = argparse.ArgumentParser(
        description="Discover projects for Heisenberg testing"
    )
    parser.add_argument(
        "--min-stars", type=int, default=100, help="Minimum stars"
    )
    parser.add_argument(
        "--limit", type=int, default=30, help="Max repos to analyze (global)"
    )
    parser.add_argument("--output", "-o", help="Output JSON file")
    args = parser.parse_args()

    print("🔍 Searching GitHub for Playwright projects with artifacts...\n")

    candidates = discover_candidates(
        global_limit=args.limit,
        min_stars=args.min_stars,
    )

    compatible_count = sum(1 for c in candidates if c.compatible)

    print(f"📋 Analyzed {len(candidates)} repositories (min {args.min_stars}⭐)")
    print("🔬 Results:\n")

    for i, candidate in enumerate(candidates, 1):
        print(f"  [{i:2}/{len(candidates)}] {candidate.repo:<45}", end=" ")
        if candidate.compatible:
            print(f"✅ {candidate.stars:>5}⭐ {candidate.notes}")
        elif candidate.has_artifacts:
            print(f"⚠️  {candidate.notes}")
        elif candidate.run_id:
            print(f"❌ {candidate.notes}")
        else:
            print("⏭️  No failed runs")

    print(f"\n{'='*70}")
    print(f"📊 Results: {compatible_count} compatible / {len(candidates)} checked")
    print(f"{'='*70}\n")

    if compatible_count > 0:
        print("🎯 Compatible Projects (ready for Heisenberg):\n")
        for c in candidates:
            if c.compatible:
                print(f"  ⭐ {c.stars:>6} | {c.repo}")
                print(f"            Artifacts: {', '.join(c.artifact_names[:5])}")
                if c.run_url:
                    print(f"            Run: {c.run_url}")
                print()

    if args.output:
        output_data = [
            {
                "repo": c.repo,
                "stars": c.stars,
                "compatible": c.compatible,
                "artifacts": c.artifact_names,
                "run_id": c.run_id,
                "run_url": c.run_url,
                "notes": c.notes,
            }
            for c in candidates
        ]
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"💾 Results saved to {args.output}")


if __name__ == "__main__":
    main()
