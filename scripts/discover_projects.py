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
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def search_repos(query: str, limit: int = 30) -> list[str]:
    """Search GitHub for repositories matching query."""
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
    repos = {item["repository"]["full_name"] for item in data["items"][:limit]}
    return list(repos)


def get_repo_stars(repo: str) -> int:
    """Get star count for a repository."""
    data = gh_api(f"/repos/{repo}")
    return data.get("stargazers_count", 0) if data else 0


def check_artifacts(repo: str) -> tuple[str | None, str | None, list[str]]:
    """Check if repo has artifacts in latest failed run."""
    # Get latest failed run - use URL params directly
    cmd = ["gh", "api", "-X", "GET", f"/repos/{repo}/actions/runs?status=failure&per_page=1"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None, None, []

    if not data or not data.get("workflow_runs"):
        return None, None, []

    run = data["workflow_runs"][0]
    run_id = str(run["id"])
    run_url = run.get("html_url", "")

    # Get artifacts for this run
    artifacts_data = gh_api(f"/repos/{repo}/actions/runs/{run_id}/artifacts")
    if not artifacts_data or not artifacts_data.get("artifacts"):
        return run_id, run_url, []

    artifact_names = [a["name"] for a in artifacts_data["artifacts"]]
    return run_id, run_url, artifact_names


def is_playwright_artifact(name: str) -> bool:
    """Check if artifact name suggests Playwright report."""
    keywords = ["playwright", "report", "test-results", "e2e", "blob"]
    name_lower = name.lower()
    return any(kw in name_lower for kw in keywords)


def analyze_candidate(repo: str) -> ProjectCandidate:
    """Analyze a repository as a candidate for testing."""
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


def main():
    parser = argparse.ArgumentParser(description="Discover projects for Heisenberg testing")
    parser.add_argument("--min-stars", type=int, default=100, help="Minimum stars")
    parser.add_argument("--limit", type=int, default=30, help="Max repos per query")
    parser.add_argument("--output", "-o", help="Output JSON file")
    args = parser.parse_args()

    print("🔍 Searching GitHub for Playwright projects with artifacts...\n")

    # Search queries optimized for finding repos with test artifacts
    queries = [
        'playwright "upload-artifact" path:.github/workflows extension:yml',
        '"blob-report" "upload-artifact" path:.github/workflows',
        '"playwright-report" "actions/upload-artifact" path:.github/workflows',
    ]

    all_repos: set[str] = set()
    for query in queries:
        print(f"  Query: {query[:60]}...")
        repos = search_repos(query, limit=args.limit)
        all_repos.update(repos)
        print(f"         Found {len(repos)} repos\n")

    print(f"📋 Total unique repositories: {len(all_repos)}")
    print("🔬 Analyzing candidates...\n")

    candidates = []
    compatible_count = 0

    for i, repo in enumerate(sorted(all_repos), 1):
        print(f"  [{i:2}/{len(all_repos)}] {repo:<45}", end=" ", flush=True)
        candidate = analyze_candidate(repo)
        candidates.append(candidate)

        if candidate.compatible:
            compatible_count += 1
            print(f"✅ {candidate.stars:>5}⭐ {candidate.notes}")
        elif candidate.has_artifacts:
            print(f"⚠️  {candidate.notes}")
        elif candidate.run_id:
            print(f"❌ {candidate.notes}")
        else:
            print("⏭️  No failed runs")

    # Sort by compatibility, then stars
    candidates.sort(key=lambda c: (-c.compatible, -c.stars))

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
