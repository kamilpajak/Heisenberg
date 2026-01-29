"""Artifact analysis, source verification, and status determination."""

from __future__ import annotations

import json
from collections.abc import Callable

from .cache import RunCache
from .client import (
    download_artifact_to_dir,
    get_failed_runs,
    get_repo_stars,
    get_run_artifacts,
)
from .models import (
    _PLAYWRIGHT_REGEX,
    ProjectSource,
    SourceStatus,
)


def is_playwright_artifact(name: str) -> bool:
    """Check if artifact name suggests Playwright report."""
    return bool(_PLAYWRIGHT_REGEX.search(name))


def _extract_failure_count(data: dict) -> int | None:
    """Extract failure count from Playwright report data."""
    if not isinstance(data, dict):
        return None

    stats = data.get("stats", {})
    if not stats:
        return None

    # Playwright JSON reporter format: unexpected, flaky
    if "unexpected" in stats:
        return stats.get("unexpected", 0) + stats.get("flaky", 0)

    # Playwright blob/JSONL format: failed
    if "failed" in stats:
        return stats.get("failed", 0)

    return None


def _extract_failure_count_from_jsonl(jsonl_content: str) -> int | None:
    """Extract failure count from Playwright JSONL blob report.

    Counts onTestEnd events with 'failed' or 'timedOut' status.
    Returns None if no onTestEnd events are found (not a valid JSONL report).
    """
    if not jsonl_content.strip():
        return None

    failures = 0
    has_test_events = False

    for line in jsonl_content.strip().split("\n"):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("method") == "onTestEnd":
            has_test_events = True
            status = obj.get("params", {}).get("result", {}).get("status")
            if status in ("failed", "timedOut"):
                failures += 1

    return failures if has_test_events else None


def _extract_failure_count_from_html(html_content: str) -> int | None:
    """Extract failure count from Playwright HTML report.

    Playwright's HTML reporter embeds a base64-encoded ZIP at the end of the file
    containing report.json with test stats.
    """
    import base64
    import io
    import re
    import zipfile

    match = re.search(r"([A-Za-z0-9+/=]{100,})</script>", html_content)  # NOSONAR
    if not match:
        return None

    try:
        raw = base64.b64decode(match.group(1))
        zf = zipfile.ZipFile(io.BytesIO(raw))
        for name in zf.namelist():
            if name.endswith(".json"):
                data = json.loads(zf.read(name))
                result = _extract_failure_count(data)
                if result is not None:
                    return result
    except Exception:
        return None

    return None


def _extract_from_nested_zip(zip_file) -> int | None:
    """Extract failure count from a single nested ZIP file."""
    import zipfile

    try:
        with zipfile.ZipFile(zip_file) as zf:
            # Try JSON files first (report.json with stats)
            for name in zf.namelist():
                if name.endswith(".json"):
                    data = json.loads(zf.read(name))
                    failures = _extract_failure_count(data)
                    if failures is not None:
                        return failures

            # Then try JSONL files (report.jsonl with events)
            for name in zf.namelist():
                if name.endswith(".jsonl"):
                    content = zf.read(name).decode()
                    failures = _extract_failure_count_from_jsonl(content)
                    if failures is not None:
                        return failures
    except Exception:  # noqa: S110 - intentionally silent, returns None
        pass
    return None


def _extract_from_html_file(html_file) -> int | None:
    """Extract failure count from a single HTML file."""
    try:
        content = html_file.read_text()
        return _extract_failure_count_from_html(content)
    except OSError:
        return None


def _extract_from_json_file(json_file) -> int | None:
    """Extract failure count from a single JSON file."""
    try:
        data = json.loads(json_file.read_text())
        return _extract_failure_count(data)
    except (json.JSONDecodeError, OSError):
        return None


def extract_failure_count_from_dir(dir_path) -> int | None:
    """Extract failure count from files in an extracted artifact directory.

    Handles Playwright report formats in priority order:
    1. Nested ZIPs (blob reports with JSON/JSONL)
    2. HTML reports with embedded base64 ZIP
    3. Direct JSON files in artifact root
    """
    from pathlib import Path

    dir_path = Path(dir_path)

    # Try nested ZIP files (blob reports)
    for zip_file in dir_path.glob("*.zip"):
        failures = _extract_from_nested_zip(zip_file)
        if failures is not None:
            return failures

    # Try HTML files (embedded base64 ZIP)
    for html_file in dir_path.glob("*.html"):
        failures = _extract_from_html_file(html_file)
        if failures is not None:
            return failures

    # Try direct JSON files
    for json_file in dir_path.rglob("*.json"):
        failures = _extract_from_json_file(json_file)
        if failures is not None:
            return failures

    return None


def download_and_check_failures(repo: str, artifact_name: str) -> int | None:
    """Download artifact and extract failure count.

    Uses optimized direct file reading instead of re-zipping.

    Returns:
        Number of failures found, or None if download/parsing failed.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        if not download_artifact_to_dir(repo, artifact_name, tmpdir):
            return None

        return extract_failure_count_from_dir(tmpdir)


def verify_has_failures(repo: str, artifact_name: str) -> bool:
    """Verify that an artifact contains actual test failures.

    Downloads the artifact and checks if it has non-zero failure count.
    """
    failure_count = download_and_check_failures(repo, artifact_name)
    return failure_count is not None and failure_count > 0


def verify_has_failures_cached(
    repo: str,
    run_id: str,
    artifact_name: str,
    cache: RunCache,
    run_created_at: str,
) -> bool:
    """Verify that an artifact contains actual test failures, using cache.

    Args:
        repo: Repository in owner/repo format
        run_id: Workflow run ID
        artifact_name: Name of the artifact to check
        cache: RunCache instance for caching results
        run_created_at: ISO timestamp of when the run was created on GitHub

    Returns:
        True if artifact has non-zero failure count.
    """
    # Check cache first
    cached_count = cache.get(run_id)
    if cached_count is not None:
        return cached_count > 0

    # Cache miss - download and verify
    failure_count = download_and_check_failures(repo, artifact_name)

    # Store result in cache (even if None or 0)
    if failure_count is not None:
        cache.set(run_id, failure_count, run_created_at)

    return failure_count is not None and failure_count > 0


def filter_expired_artifacts(artifacts: list[dict]) -> list[str]:
    """Filter out expired artifacts, return names of valid ones."""
    return [a["name"] for a in artifacts if not a.get("expired", False)]


def _artifact_sizes(artifacts: list[dict]) -> dict[str, int]:
    """Extract {name: size_in_bytes} for non-expired artifacts."""
    return {a["name"]: a.get("size_in_bytes", 0) for a in artifacts if not a.get("expired", False)}


def find_valid_artifacts(
    repo: str,
) -> tuple[str | None, str | None, list[str], str | None, dict[str, int]]:
    """Find valid (non-expired) Playwright artifacts from recent failed runs.

    Prioritizes runs with Playwright artifacts over runs with other artifacts.

    Returns:
        Tuple of (run_id, run_url, artifact_names, run_created_at, artifact_sizes)
        for first run with Playwright artifacts, or first run with any artifacts,
        or (first_run_id, first_run_url, [], run_created_at, {}) if none.
    """
    runs = get_failed_runs(repo)
    if not runs:
        return None, None, [], None, {}

    # First pass: look for runs with Playwright artifacts
    for run in runs:
        run_id = str(run["id"])
        run_url = run.get("html_url", "")
        run_created_at = run.get("created_at")

        artifacts = get_run_artifacts(repo, run_id)
        valid_names = filter_expired_artifacts(artifacts)
        playwright_names = [a for a in valid_names if is_playwright_artifact(a)]

        if playwright_names:
            return run_id, run_url, valid_names, run_created_at, _artifact_sizes(artifacts)

    # Second pass: return first run with any artifacts
    for run in runs:
        run_id = str(run["id"])
        run_url = run.get("html_url", "")
        run_created_at = run.get("created_at")

        artifacts = get_run_artifacts(repo, run_id)
        valid_names = filter_expired_artifacts(artifacts)

        if valid_names:
            return run_id, run_url, valid_names, run_created_at, _artifact_sizes(artifacts)

    # No artifacts found, return first run info
    first_run = runs[0]
    return str(first_run["id"]), first_run.get("html_url", ""), [], first_run.get("created_at"), {}


def determine_status(
    run_id: str | None,
    artifact_names: list[str],
    playwright_artifacts: list[str],
    failure_count: int | None = None,
) -> SourceStatus:
    """Determine the status of a source based on its data.

    Args:
        run_id: Workflow run ID
        artifact_names: All artifact names
        playwright_artifacts: Playwright-specific artifact names
        failure_count: Number of test failures (None = not verified)
    """
    if not run_id:
        return SourceStatus.NO_FAILED_RUNS
    if not artifact_names:
        return SourceStatus.NO_ARTIFACTS
    if not playwright_artifacts:
        return SourceStatus.HAS_ARTIFACTS
    # If failure_count was verified and is 0, mark as NO_FAILURES
    if failure_count is not None and failure_count == 0:
        return SourceStatus.NO_FAILURES
    return SourceStatus.COMPATIBLE


def _report_verification_stage(
    cache: RunCache | None,
    run_id: str,
    artifact_sizes: dict[str, int],
    artifact_name: str,
    report: Callable[[str], None],
) -> None:
    """Report the appropriate status message for verification stage."""
    if cache and cache.get(run_id):
        report("checking cache")
        return
    # Lazy import to avoid circular dependency
    from .ui import format_size

    size = artifact_sizes.get(artifact_name, 0)
    report(f"dl {format_size(size)}" if size > 0 else "downloading...")


def _verify_artifact_failures(
    repo: str,
    run_id: str,
    artifact_name: str,
    cache: RunCache | None,
    run_created_at: str | None,
) -> int:
    """Verify failures in artifact, using cache if available."""
    if cache and run_created_at:
        has_failures = verify_has_failures_cached(
            repo, run_id, artifact_name, cache, run_created_at
        )
    else:
        has_failures = verify_has_failures(repo, artifact_name)
    return 1 if has_failures else 0


def analyze_source_with_status(
    repo: str,
    stars: int | None = None,
    verify_failures: bool = False,
    on_status: Callable[[str], None] | None = None,
    cache: RunCache | None = None,
) -> ProjectSource:
    """Analyze a repository with status updates for each stage."""

    def report(stage: str) -> None:
        if on_status:
            on_status(stage)

    report("fetching info")
    if stars is None:
        stars = get_repo_stars(repo) or 0

    report("fetching runs")
    run_id, run_url, artifact_names, run_created_at, artifact_sizes = find_valid_artifacts(repo)
    playwright_artifacts = [a for a in artifact_names if is_playwright_artifact(a)]

    failure_count = None
    if verify_failures and playwright_artifacts and run_id:
        artifact_to_check = playwright_artifacts[0]
        _report_verification_stage(cache, run_id, artifact_sizes, artifact_to_check, report)
        failure_count = _verify_artifact_failures(
            repo, run_id, artifact_to_check, cache, run_created_at
        )

    status = determine_status(run_id, artifact_names, playwright_artifacts, failure_count)

    return ProjectSource(
        repo=repo,
        stars=stars,
        status=status,
        artifact_names=artifact_names,
        playwright_artifacts=playwright_artifacts,
        run_id=run_id,
        run_url=run_url,
    )


def analyze_source(
    repo: str,
    stars: int | None = None,
    verify_failures: bool = False,
) -> ProjectSource:
    """Analyze a repository as a source for testing.

    Args:
        repo: Repository in owner/repo format
        stars: Star count (fetched if None)
        verify_failures: If True, download artifact to verify it has failures
    """
    if stars is None:
        stars = get_repo_stars(repo) or 0

    run_id, run_url, artifact_names, _, _ = find_valid_artifacts(repo)
    playwright_artifacts = [a for a in artifact_names if is_playwright_artifact(a)]

    # Optionally verify that artifact has actual failures
    failure_count = None
    if verify_failures and playwright_artifacts and run_id:
        has_failures = verify_has_failures(repo, playwright_artifacts[0])
        failure_count = 1 if has_failures else 0

    status = determine_status(run_id, artifact_names, playwright_artifacts, failure_count)

    return ProjectSource(
        repo=repo,
        stars=stars,
        status=status,
        artifact_names=artifact_names,
        playwright_artifacts=playwright_artifacts,
        run_id=run_id,
        run_url=run_url,
    )


def filter_by_min_stars(sources: list[ProjectSource], min_stars: int = 100) -> list[ProjectSource]:
    """Filter sources by minimum star count."""
    return [c for c in sources if c.stars >= min_stars]


def sort_sources(sources: list[ProjectSource]) -> list[ProjectSource]:
    """Sort sources by compatibility (desc), then stars (desc)."""
    return sorted(sources, key=lambda c: (-c.compatible, -c.stars))
