#!/usr/bin/env python3
"""Discover GitHub projects suitable for Heisenberg testing.

This script searches GitHub for repositories that:
1. Use Playwright for E2E testing
2. Upload test artifacts to GitHub Actions
3. Have recent failed workflow runs

Architecture follows Single Responsibility Principle:
- GitHubClient: API communication
- Domain: ProjectCandidate, CandidateStatus, validation logic
- Presenter: CLI output formatting
- Config: DEFAULT_QUERIES, PLAYWRIGHT_PATTERNS
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import TextIO

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_QUERIES = [
    'playwright "upload-artifact" path:.github/workflows extension:yml',
    '"blob-report" "upload-artifact" path:.github/workflows',
    '"playwright-report" "actions/upload-artifact" path:.github/workflows',
]

PLAYWRIGHT_PATTERNS = [
    r"^playwright[-_]?report",      # playwright-report, playwright_report
    r"^blob[-_]?report",            # blob-report (Playwright sharding)
    r"^playwright[-_]?traces?",     # playwright-trace, playwright-traces
    r"^trace\.zip$",                # trace.zip
    r"playwright.*report",          # any-playwright-report
]

_PLAYWRIGHT_REGEX = re.compile("|".join(PLAYWRIGHT_PATTERNS), re.IGNORECASE)

MAX_RUNS_TO_CHECK = 5


# =============================================================================
# DOMAIN MODELS
# =============================================================================

class CandidateStatus(Enum):
    """Status of a candidate project."""

    COMPATIBLE = "compatible"           # Has valid Playwright artifacts
    HAS_ARTIFACTS = "has_artifacts"     # Has artifacts but not Playwright
    NO_ARTIFACTS = "no_artifacts"       # Run exists but no artifacts
    NO_FAILED_RUNS = "no_failed_runs"   # No failed workflow runs


@dataclass
class ProjectCandidate:
    """A candidate project for testing."""

    repo: str
    stars: int
    status: CandidateStatus
    artifact_names: list[str] = field(default_factory=list)
    playwright_artifacts: list[str] = field(default_factory=list)
    run_id: str | None = None
    run_url: str | None = None

    @property
    def compatible(self) -> bool:
        """Whether this candidate has valid Playwright artifacts."""
        return self.status == CandidateStatus.COMPATIBLE

    @property
    def has_artifacts(self) -> bool:
        """Whether this candidate has any artifacts."""
        return len(self.artifact_names) > 0


# =============================================================================
# GITHUB CLIENT (API Communication)
# =============================================================================

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
        if e.stderr and "rate limit" in e.stderr.lower():
            print(f"⚠️  Rate limit hit: {endpoint}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        return None


def search_repos(query: str, limit: int = 30) -> list[str]:
    """Search GitHub for repositories matching query.

    Returns list of unique repo names.
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


def get_failed_runs(repo: str, limit: int = MAX_RUNS_TO_CHECK) -> list[dict]:
    """Get recent failed workflow runs for a repository."""
    cmd = [
        "gh", "api", "-X", "GET",
        f"/repos/{repo}/actions/runs?status=failure&per_page={limit}"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return []

    return data.get("workflow_runs", []) if data else []


def get_run_artifacts(repo: str, run_id: str) -> list[dict]:
    """Get artifacts for a specific workflow run."""
    data = gh_api(f"/repos/{repo}/actions/runs/{run_id}/artifacts")
    if not data or not data.get("artifacts"):
        return []
    return data["artifacts"]


# =============================================================================
# DOMAIN LOGIC (Validation & Analysis)
# =============================================================================

def is_playwright_artifact(name: str) -> bool:
    """Check if artifact name suggests Playwright report."""
    return bool(_PLAYWRIGHT_REGEX.search(name))


def filter_expired_artifacts(artifacts: list[dict]) -> list[str]:
    """Filter out expired artifacts, return names of valid ones."""
    return [
        a["name"]
        for a in artifacts
        if not a.get("expired", False)
    ]


def find_valid_artifacts(repo: str) -> tuple[str | None, str | None, list[str]]:
    """Find valid (non-expired) artifacts from recent failed runs.

    Returns:
        Tuple of (run_id, run_url, artifact_names) for first run with artifacts,
        or (first_run_id, first_run_url, []) if no artifacts found.
    """
    runs = get_failed_runs(repo)
    if not runs:
        return None, None, []

    for run in runs:
        run_id = str(run["id"])
        run_url = run.get("html_url", "")

        artifacts = get_run_artifacts(repo, run_id)
        valid_names = filter_expired_artifacts(artifacts)

        if valid_names:
            return run_id, run_url, valid_names

    # No artifacts found, return first run info
    first_run = runs[0]
    return str(first_run["id"]), first_run.get("html_url", ""), []


def determine_status(
    run_id: str | None,
    artifact_names: list[str],
    playwright_artifacts: list[str],
) -> CandidateStatus:
    """Determine the status of a candidate based on its data."""
    if not run_id:
        return CandidateStatus.NO_FAILED_RUNS
    if not artifact_names:
        return CandidateStatus.NO_ARTIFACTS
    if not playwright_artifacts:
        return CandidateStatus.HAS_ARTIFACTS
    return CandidateStatus.COMPATIBLE


def analyze_candidate(repo: str, stars: int | None = None) -> ProjectCandidate:
    """Analyze a repository as a candidate for testing."""
    if stars is None:
        stars = get_repo_stars(repo)

    run_id, run_url, artifact_names = find_valid_artifacts(repo)
    playwright_artifacts = [a for a in artifact_names if is_playwright_artifact(a)]
    status = determine_status(run_id, artifact_names, playwright_artifacts)

    return ProjectCandidate(
        repo=repo,
        stars=stars,
        status=status,
        artifact_names=artifact_names,
        playwright_artifacts=playwright_artifacts,
        run_id=run_id,
        run_url=run_url,
    )


def filter_by_min_stars(
    candidates: list[ProjectCandidate],
    min_stars: int = 100
) -> list[ProjectCandidate]:
    """Filter candidates by minimum star count."""
    return [c for c in candidates if c.stars >= min_stars]


def sort_candidates(candidates: list[ProjectCandidate]) -> list[ProjectCandidate]:
    """Sort candidates by compatibility (desc), then stars (desc)."""
    return sorted(candidates, key=lambda c: (-c.compatible, -c.stars))


# =============================================================================
# DISCOVERY ORCHESTRATION
# =============================================================================

def discover_candidates(
    global_limit: int = 30,
    min_stars: int = 100,
    queries: list[str] | None = None,
) -> list[ProjectCandidate]:
    """Discover candidate projects from GitHub.

    Args:
        global_limit: Maximum total repos to analyze across all queries
        min_stars: Minimum star count to include
        queries: Custom search queries (uses DEFAULT_QUERIES if None)

    Returns:
        List of analyzed ProjectCandidate objects, sorted by compatibility
    """
    if queries is None:
        queries = DEFAULT_QUERIES

    # Collect unique repos from all queries
    all_repos: set[str] = set()
    for query in queries:
        results = search_repos(query, limit=global_limit)
        all_repos.update(results)
        if len(all_repos) >= global_limit:
            break

    # Analyze candidates
    candidates = [analyze_candidate(repo) for repo in list(all_repos)[:global_limit]]

    # Filter and sort
    candidates = filter_by_min_stars(candidates, min_stars=min_stars)
    candidates = sort_candidates(candidates)

    return candidates


# =============================================================================
# PRESENTER (CLI Output Formatting)
# =============================================================================

def format_status_icon(status: CandidateStatus) -> str:
    """Get the icon for a candidate status."""
    icons = {
        CandidateStatus.COMPATIBLE: "✅",
        CandidateStatus.HAS_ARTIFACTS: "⚠️ ",
        CandidateStatus.NO_ARTIFACTS: "❌",
        CandidateStatus.NO_FAILED_RUNS: "⏭️ ",
    }
    return icons.get(status, "?")


def format_status_detail(candidate: ProjectCandidate) -> str:
    """Format the detail text for a candidate's status."""
    if candidate.status == CandidateStatus.COMPATIBLE:
        artifacts = ", ".join(candidate.playwright_artifacts[:3])
        return f"{candidate.stars:>5}⭐ ✓ {artifacts}"
    elif candidate.status == CandidateStatus.HAS_ARTIFACTS:
        artifacts = ", ".join(candidate.artifact_names[:3])
        return f"Artifacts: {artifacts}"
    elif candidate.status == CandidateStatus.NO_ARTIFACTS:
        return "No artifacts"
    else:
        return "No failed runs"


def print_candidate_line(
    candidate: ProjectCandidate,
    index: int,
    total: int,
    out: TextIO = sys.stdout,
) -> None:
    """Print a single candidate line."""
    icon = format_status_icon(candidate.status)
    detail = format_status_detail(candidate)
    print(f"  [{index:2}/{total}] {candidate.repo:<45} {icon} {detail}", file=out)


def print_summary(
    candidates: list[ProjectCandidate],
    min_stars: int,
    out: TextIO = sys.stdout,
) -> None:
    """Print the analysis summary."""
    compatible_count = sum(1 for c in candidates if c.compatible)

    print(f"📋 Analyzed {len(candidates)} repositories (min {min_stars}⭐)", file=out)
    print("🔬 Results:\n", file=out)

    for i, candidate in enumerate(candidates, 1):
        print_candidate_line(candidate, i, len(candidates), out)

    print(f"\n{'='*70}", file=out)
    print(f"📊 Results: {compatible_count} compatible / {len(candidates)} checked", file=out)
    print(f"{'='*70}\n", file=out)


def print_compatible_projects(
    candidates: list[ProjectCandidate],
    out: TextIO = sys.stdout,
) -> None:
    """Print details of compatible projects."""
    compatible = [c for c in candidates if c.compatible]
    if not compatible:
        return

    print("🎯 Compatible Projects (ready for Heisenberg):\n", file=out)
    for c in compatible:
        print(f"  ⭐ {c.stars:>6} | {c.repo}", file=out)
        print(f"            Artifacts: {', '.join(c.artifact_names[:5])}", file=out)
        if c.run_url:
            print(f"            Run: {c.run_url}", file=out)
        print(file=out)


def save_results(candidates: list[ProjectCandidate], output_path: str) -> None:
    """Save results to JSON file."""
    output_data = [
        {
            "repo": c.repo,
            "stars": c.stars,
            "compatible": c.compatible,
            "status": c.status.value,
            "artifacts": c.artifact_names,
            "playwright_artifacts": c.playwright_artifacts,
            "run_id": c.run_id,
            "run_url": c.run_url,
        }
        for c in candidates
    ]
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"💾 Results saved to {output_path}")


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main() -> None:
    """Main entry point for CLI."""
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

    print_summary(candidates, args.min_stars)
    print_compatible_projects(candidates)

    if args.output:
        save_results(candidates, args.output)


if __name__ == "__main__":
    main()
