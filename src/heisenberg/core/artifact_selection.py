"""Artifact selection logic for identifying Playwright test reports.

This module provides functions to select the best artifact from GitHub Actions
workflow runs, using a scoring system that prioritizes artifacts matching
failed job names.
"""

from __future__ import annotations

import re

# Patterns that indicate a Playwright test artifact
PLAYWRIGHT_PATTERNS = [
    r"^playwright[-_]?report",  # playwright-report, playwright_report
    r"^blob[-_]?report",  # blob-report (Playwright sharding)
    r"^playwright[-_]?traces?",  # playwright-trace, playwright-traces
    r"^trace\.zip$",  # trace.zip
    r"playwright.*report",  # any-playwright-report
    r"playwright.*traces?",  # middleware-starter-playwright-traces
]

_PLAYWRIGHT_REGEX = re.compile("|".join(PLAYWRIGHT_PATTERNS), re.IGNORECASE)


def _normalize(s: str) -> str:
    """Normalize string by removing hyphens and underscores.

    Used for fuzzy matching between job names and artifact names.
    """
    return s.replace("-", "").replace("_", "")


def is_playwright_artifact(name: str) -> bool:
    """Check if artifact name suggests Playwright report."""
    return bool(_PLAYWRIGHT_REGEX.search(name))


def _extract_job_name_core(job_name: str) -> str:
    """Extract core job name, removing matrix suffixes and OS info.

    Examples:
        "e2e-web (ubuntu-latest)" -> "e2e-web"
        "e2e-desktop (ubuntu-latest) [3/4]" -> "e2e-desktop"
        "npm audit" -> "npm audit"
    """
    # Remove matrix suffix like [1/4], [3/4]
    name = re.sub(r"\s*\[\d+/\d+\]", "", job_name)
    # Remove OS suffix like (ubuntu-latest), (windows-latest)
    name = re.sub(r"\s*\([^)]+\)", "", name)
    return name.strip()


def _extract_shard_index(text: str) -> int | None:
    """Extract shard index from job name or artifact name.

    Examples:
        "[3/4]" -> 3
        "blob-report-desktop-3" -> 3
        "e2e-results" -> None
    """
    # Matrix format: [3/4]
    matrix_match = re.search(r"\[(\d+)/\d+\]", text)
    if matrix_match:
        return int(matrix_match.group(1))

    # Artifact suffix format: -3, _3
    suffix_match = re.search(r"[-_](\d+)$", text)
    if suffix_match:
        return int(suffix_match.group(1))

    return None


def select_best_artifact(artifacts: list[dict], failed_jobs: list[str]) -> dict | None:
    """Select the best artifact to check for test failures.

    Uses a scoring system to prioritize:
    1. Artifacts matching failed job names (highest priority)
    2. Artifacts matching Playwright naming patterns
    3. Artifacts with "report" in name

    Args:
        artifacts: List of artifact dicts with 'name' key
        failed_jobs: List of failed job names from GitHub API

    Returns:
        Best artifact dict, or None if no suitable artifact found.
    """
    if not artifacts:
        return None

    # Extract core job names for matching
    failed_job_cores = [_extract_job_name_core(job) for job in failed_jobs]
    failed_job_shards = {
        _extract_job_name_core(job): _extract_shard_index(job) for job in failed_jobs
    }

    scored: list[tuple[int, dict]] = []

    for artifact in artifacts:
        name = artifact.get("name", "")
        name_lower = name.lower()
        score = 0

        # Job name matching (highest priority)
        for job_core in failed_job_cores:
            job_lower = job_core.lower()
            # Check if job name prefix matches artifact
            # e.g., "e2e-web" matches "e2e-web-reports"
            if _normalize(job_lower) in _normalize(name_lower):
                score += 50
                # Bonus for shard index match
                job_shard = failed_job_shards.get(job_core)
                artifact_shard = _extract_shard_index(name)
                if job_shard and artifact_shard and job_shard == artifact_shard:
                    score += 20
                break

        # Playwright pattern matching
        if is_playwright_artifact(name):
            score += 30

        # Keyword bonuses
        if "playwright" in name_lower:
            score += 15
        if "blob" in name_lower:
            score += 10
        if "report" in name_lower:
            score += 5
        if "e2e" in name_lower:
            score += 5

        scored.append((score, artifact))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Return best match if score is meaningful (> 5 = at least has "report")
    if scored and scored[0][0] > 5:
        return scored[0][1]

    return None
