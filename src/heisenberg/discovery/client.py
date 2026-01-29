"""GitHub API communication via gh CLI."""

from __future__ import annotations

import json
import subprocess
import threading

from .models import (
    GH_MAX_CONCURRENT,
    GH_MAX_RETRIES,
    GH_RETRY_BASE_DELAY,
    MAX_RUNS_TO_CHECK,
    TIMEOUT_API,
    TIMEOUT_DOWNLOAD,
)

_gh_semaphore = threading.Semaphore(GH_MAX_CONCURRENT)


def _is_rate_limit_error(exc: subprocess.CalledProcessError) -> bool:
    """Check if a CalledProcessError is a GitHub rate limit error.

    Detects both primary rate limits ("rate limit") and secondary/abuse
    limits ("abuse detection") from gh CLI stderr output.
    """
    if not exc.stderr:
        return False
    stderr = exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode()
    lower = stderr.lower()
    return "rate limit" in lower or "abuse" in lower


def _gh_subprocess(
    cmd: list[str],
    timeout: int = TIMEOUT_API,
    capture_output: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess:
    """Run a gh CLI command with throttling and retry.

    Limits concurrent API calls via semaphore with jitter to prevent
    GitHub secondary rate limits, and retries with exponential backoff
    when rate limits are hit despite throttling.

    Args:
        cmd: Command and arguments for subprocess.run
        timeout: Timeout in seconds
        capture_output: Capture stdout/stderr
        text: Decode output as text

    Returns:
        CompletedProcess on success

    Raises:
        subprocess.CalledProcessError: On non-rate-limit errors or after max retries
        subprocess.TimeoutExpired: On timeout (not retried)
    """
    import random
    import time

    last_error = None
    for attempt in range(GH_MAX_RETRIES + 1):
        with _gh_semaphore:
            time.sleep(random.uniform(0.05, 0.5))  # noqa: S311 - backoff jitter
            try:
                return subprocess.run(
                    cmd,
                    capture_output=capture_output,
                    text=text,
                    check=True,
                    timeout=timeout,
                )
            except subprocess.CalledProcessError as e:
                if not _is_rate_limit_error(e) or attempt >= GH_MAX_RETRIES:
                    raise
                last_error = e
            # Note: TimeoutExpired is not caught - it propagates immediately (not retried)

        # Semaphore released — exponential backoff before retry
        delay = GH_RETRY_BASE_DELAY * (2**attempt) + random.uniform(0, 1)  # noqa: S311
        time.sleep(delay)

    raise last_error  # type: ignore[misc]


def gh_api(endpoint: str, params: dict | None = None) -> dict | list | None:
    """Call GitHub API via gh CLI."""
    cmd = ["gh", "api", endpoint]
    if params:
        for k, v in params.items():
            cmd.extend(["-f", f"{k}={v}"])
    try:
        result = _gh_subprocess(cmd, timeout=TIMEOUT_API)
        return json.loads(result.stdout) if result.stdout.strip() else None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
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
        result = _gh_subprocess(cmd, timeout=TIMEOUT_API)
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
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


def get_repo_stars(repo: str) -> int | None:
    """Get star count for a repository.

    Returns:
        int: Star count (0 or higher) on success
        None: If API call failed (timeout, rate limit, 404, etc.)
    """
    data = gh_api(f"/repos/{repo}")
    if isinstance(data, dict):
        return data.get("stargazers_count", 0)
    return None


def get_failed_runs(repo: str, limit: int = MAX_RUNS_TO_CHECK) -> list[dict]:
    """Get recent failed workflow runs for a repository."""
    cmd = ["gh", "api", "-X", "GET", f"/repos/{repo}/actions/runs?status=failure&per_page={limit}"]
    try:
        result = _gh_subprocess(cmd, timeout=TIMEOUT_API)
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []

    return data.get("workflow_runs", []) if data else []


def get_run_artifacts(repo: str, run_id: str) -> list[dict]:
    """Get artifacts for a specific workflow run."""
    data = gh_api(f"/repos/{repo}/actions/runs/{run_id}/artifacts")
    if not isinstance(data, dict):
        return []
    return data.get("artifacts", [])


def download_artifact_to_dir(repo: str, artifact_name: str, target_dir: str) -> bool:
    """Download and extract artifact directly to target directory.

    Args:
        repo: Repository in owner/repo format
        artifact_name: Name of the artifact to download
        target_dir: Directory to extract artifact contents to

    Returns:
        True if download succeeded, False otherwise.
    """
    cmd = ["gh", "run", "download", "-R", repo, "-n", artifact_name, "-D", target_dir]
    try:
        _gh_subprocess(cmd, timeout=TIMEOUT_DOWNLOAD, text=False)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
