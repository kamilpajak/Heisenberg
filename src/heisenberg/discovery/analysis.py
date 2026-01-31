"""Artifact analysis, source verification, and status determination."""

from __future__ import annotations

import json
from collections.abc import Callable

from heisenberg.core.artifact_selection import (
    is_playwright_artifact,
    select_best_artifact,
)
from heisenberg.core.exceptions import HtmlReportNotSupported

from .cache import RunCache
from .client import (
    download_artifact_by_id,
    download_artifact_to_dir,
    get_failed_jobs,
    get_failed_runs,
    get_repo_stars,
    get_run_artifacts,
)
from .models import (
    GitHubRateLimitError,
    ProjectSource,
    SourceStatus,
)


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
    except Exception:  # noqa: S110  # NOSONAR - intentionally silent, returns None
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


def _is_html_report_dir(dir_path) -> bool:
    """Check if directory contains a modern Playwright HTML report (unsupported).

    Modern HTML reports have:
    - index.html at root (bundled JavaScript app)
    - data/ directory with trace ZIPs or snapshot files
    """
    from pathlib import Path

    dir_path = Path(dir_path)
    has_index_html = (dir_path / "index.html").exists()
    data_dir = dir_path / "data"
    has_data_content = data_dir.is_dir() and next(data_dir.iterdir(), None) is not None
    return has_index_html and has_data_content


def extract_failure_count_from_dir(dir_path) -> int | None:
    """Extract failure count from files in an extracted artifact directory.

    Handles Playwright report formats in priority order:
    1. Nested ZIPs (blob reports with JSON/JSONL)
    2. Direct JSON files in artifact root
    3. HTML reports with embedded base64 ZIP (legacy single-file format)

    Raises:
        HtmlReportNotSupported: If directory contains modern HTML report
            (index.html + data/ structure) without usable JSON data.
    """
    from pathlib import Path

    dir_path = Path(dir_path)
    is_html_report = _is_html_report_dir(dir_path)

    # Try nested ZIP files (blob reports)
    for zip_file in dir_path.glob("*.zip"):
        failures = _extract_from_nested_zip(zip_file)
        if failures is not None:
            return failures

    # Try direct JSON files (check BEFORE HTML to support dual-reporter setups)
    for json_file in dir_path.rglob("*.json"):
        failures = _extract_from_json_file(json_file)
        if failures is not None:
            return failures

    # If it's a modern HTML report directory without JSON, reject it
    # Must check BEFORE trying HTML extraction because modern HTML reports have
    # embedded base64 data in index.html that _extract_from_html_file can parse
    if is_html_report:
        raise HtmlReportNotSupported()

    # Try HTML files (embedded base64 ZIP - legacy single-file format only)
    for html_file in dir_path.glob("*.html"):
        failures = _extract_from_html_file(html_file)
        if failures is not None:
            return failures

    return None


def download_and_check_failures(
    repo: str, artifact_name: str, artifact_id: int | None = None
) -> int | None:
    """Download artifact and extract failure count.

    Uses direct S3 download when artifact_id is provided (1 API call),
    otherwise falls back to gh CLI download (~100+ API calls).

    Args:
        repo: Repository in owner/repo format
        artifact_name: Name of the artifact
        artifact_id: Optional artifact ID for direct S3 download

    Returns:
        Number of failures found, or None if download/parsing failed.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Use direct S3 download when artifact_id is available (1 API call)
        if artifact_id is not None:
            if not download_artifact_by_id(artifact_id, tmpdir, repo=repo):
                return None
        else:
            # Fallback to old method (~100+ API calls)
            if not download_artifact_to_dir(repo, artifact_name, tmpdir):
                return None

        return extract_failure_count_from_dir(tmpdir)


def verify_has_failures(repo: str, artifact_name: str, artifact_id: int | None = None) -> bool:
    """Verify that an artifact contains actual test failures.

    Downloads the artifact and checks if it has non-zero failure count.
    Uses direct S3 download when artifact_id is provided.
    """
    failure_count = download_and_check_failures(repo, artifact_name, artifact_id)
    return failure_count is not None and failure_count > 0


def verify_has_failures_cached(
    repo: str,
    run_id: str,
    artifact_name: str,
    cache: RunCache,
    run_created_at: str,
    artifact_id: int | None = None,
) -> bool:
    """Verify that an artifact contains actual test failures, using cache.

    Args:
        repo: Repository in owner/repo format
        run_id: Workflow run ID
        artifact_name: Name of the artifact to check
        cache: RunCache instance for caching results
        run_created_at: ISO timestamp of when the run was created on GitHub
        artifact_id: Optional artifact ID for direct S3 download

    Returns:
        True if artifact has non-zero failure count.
    """
    # Check cache first
    cached_count = cache.get(run_id)
    if cached_count is not None:
        return cached_count > 0

    # Cache miss - download and verify (uses direct S3 if artifact_id provided)
    failure_count = download_and_check_failures(repo, artifact_name, artifact_id)

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


def _artifact_ids(artifacts: list[dict]) -> dict[str, int]:
    """Extract {name: id} for non-expired artifacts."""
    return {a["name"]: a["id"] for a in artifacts if not a.get("expired", False)}


def find_valid_artifacts(
    repo: str,
) -> tuple[str | None, str | None, list[str], str | None, dict[str, int], dict[str, int]]:
    """Find valid (non-expired) Playwright artifacts from recent failed runs.

    Prioritizes runs with Playwright artifacts over runs with other artifacts.

    Returns:
        Tuple of (run_id, run_url, artifact_names, run_created_at, artifact_sizes, artifact_ids)
        for first run with Playwright artifacts, or first run with any artifacts,
        or (first_run_id, first_run_url, [], run_created_at, {}, {}) if none.
    """
    runs = get_failed_runs(repo)
    if not runs:
        return None, None, [], None, {}, {}

    # First pass: look for runs with Playwright artifacts
    for run in runs:
        run_id = str(run["id"])
        run_url = run.get("html_url", "")
        run_created_at = run.get("created_at")

        artifacts = get_run_artifacts(repo, run_id)
        valid_names = filter_expired_artifacts(artifacts)
        playwright_names = [a for a in valid_names if is_playwright_artifact(a)]

        if playwright_names:
            return (
                run_id,
                run_url,
                valid_names,
                run_created_at,
                _artifact_sizes(artifacts),
                _artifact_ids(artifacts),
            )

    # Second pass: return first run with any artifacts
    for run in runs:
        run_id = str(run["id"])
        run_url = run.get("html_url", "")
        run_created_at = run.get("created_at")

        artifacts = get_run_artifacts(repo, run_id)
        valid_names = filter_expired_artifacts(artifacts)

        if valid_names:
            return (
                run_id,
                run_url,
                valid_names,
                run_created_at,
                _artifact_sizes(artifacts),
                _artifact_ids(artifacts),
            )

    # No artifacts found, return first run info
    first_run = runs[0]
    return (
        str(first_run["id"]),
        first_run.get("html_url", ""),
        [],
        first_run.get("created_at"),
        {},
        {},
    )


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
    artifact_id: int | None = None,
) -> int:
    """Verify failures in artifact, using cache if available.

    Uses direct S3 download when artifact_id is provided (1 API call),
    otherwise falls back to gh CLI download (~100+ API calls).
    """
    if cache and run_created_at:
        has_failures = verify_has_failures_cached(
            repo, run_id, artifact_name, cache, run_created_at, artifact_id
        )
    else:
        has_failures = verify_has_failures(repo, artifact_name, artifact_id)
    return 1 if has_failures else 0


def analyze_source_with_status(
    repo: str,
    stars: int | None = None,
    verify_failures: bool = True,
    on_status: Callable[[str], None] | None = None,
    cache: RunCache | None = None,
) -> ProjectSource:
    """Analyze a repository with status updates for each stage."""

    def report(stage: str) -> None:
        if on_status:
            on_status(stage)

    try:
        report("fetching info")
        if stars is None:
            stars = get_repo_stars(repo) or 0

        report("fetching runs")
        run_id, run_url, artifact_names, run_created_at, artifact_sizes, artifact_ids = (
            find_valid_artifacts(repo)
        )
        playwright_artifacts = [a for a in artifact_names if is_playwright_artifact(a)]

        failure_count = None
        if verify_failures and artifact_names and run_id:
            # Use job-aware artifact selection for better accuracy
            report("checking jobs")
            failed_jobs = get_failed_jobs(repo, run_id)

            # Build artifact list with metadata for selection
            artifacts_with_meta = [
                {"name": name, "size_in_bytes": artifact_sizes.get(name, 0)}
                for name in artifact_names
            ]

            # Select best artifact based on failed jobs and naming patterns
            best_artifact = select_best_artifact(artifacts_with_meta, failed_jobs)
            artifact_to_check = best_artifact["name"] if best_artifact else None

            # Fallback to first playwright artifact if job-aware selection fails
            if not artifact_to_check and playwright_artifacts:
                artifact_to_check = playwright_artifacts[0]

            if artifact_to_check:
                _report_verification_stage(cache, run_id, artifact_sizes, artifact_to_check, report)
                artifact_id = artifact_ids.get(artifact_to_check)
                try:
                    failure_count = _verify_artifact_failures(
                        repo, run_id, artifact_to_check, cache, run_created_at, artifact_id
                    )
                except HtmlReportNotSupported:
                    return ProjectSource(
                        repo=repo,
                        stars=stars,
                        status=SourceStatus.UNSUPPORTED_FORMAT,
                        artifact_names=artifact_names,
                        playwright_artifacts=playwright_artifacts,
                        run_id=run_id,
                        run_url=run_url,
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
    except GitHubRateLimitError:
        return ProjectSource(
            repo=repo,
            stars=stars or 0,
            status=SourceStatus.RATE_LIMITED,
        )


def analyze_source(
    repo: str,
    stars: int | None = None,
    verify_failures: bool = True,
) -> ProjectSource:
    """Analyze a repository as a source for testing.

    Args:
        repo: Repository in owner/repo format
        stars: Star count (fetched if None)
        verify_failures: Download artifact to verify it has failures (default: True)
    """
    try:
        if stars is None:
            stars = get_repo_stars(repo) or 0

        run_id, run_url, artifact_names, _, _, artifact_ids = find_valid_artifacts(repo)
        playwright_artifacts = [a for a in artifact_names if is_playwright_artifact(a)]

        # Optionally verify that artifact has actual failures
        failure_count = None
        if verify_failures and playwright_artifacts and run_id:
            artifact_name = playwright_artifacts[0]
            artifact_id = artifact_ids.get(artifact_name)
            try:
                has_failures = verify_has_failures(repo, artifact_name, artifact_id)
                failure_count = 1 if has_failures else 0
            except HtmlReportNotSupported:
                return ProjectSource(
                    repo=repo,
                    stars=stars,
                    status=SourceStatus.UNSUPPORTED_FORMAT,
                    artifact_names=artifact_names,
                    playwright_artifacts=playwright_artifacts,
                    run_id=run_id,
                    run_url=run_url,
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
    except GitHubRateLimitError:
        return ProjectSource(
            repo=repo,
            stars=stars or 0,
            status=SourceStatus.RATE_LIMITED,
        )


def sort_sources(sources: list[ProjectSource]) -> list[ProjectSource]:
    """Sort sources by compatibility (desc), then stars (desc)."""
    return sorted(sources, key=lambda c: (-c.compatible, -c.stars))
