"""GitHub Actions job logs fetcher.

This module provides functionality to fetch job logs from GitHub Actions
using the gh CLI tool.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class FailedJob:
    """Represents a failed GitHub Actions job."""

    id: int
    name: str
    conclusion: str


class GitHubLogsFetcher:
    """Fetches job logs from GitHub Actions."""

    def fetch_job_logs(
        self,
        repo: str,
        job_id: str,
    ) -> str | None:
        """Fetch logs for a specific job.

        Args:
            repo: Repository in owner/repo format.
            job_id: GitHub job ID.

        Returns:
            Log content as string, or None if fetch failed.
        """
        try:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    "-H",
                    "Accept: application/vnd.github+json",
                    f"/repos/{repo}/actions/jobs/{job_id}/logs",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return None

            return result.stdout

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def get_failed_jobs(
        self,
        repo: str,
        run_id: str,
    ) -> list[dict]:
        """Get list of failed jobs for a workflow run.

        Args:
            repo: Repository in owner/repo format.
            run_id: GitHub workflow run ID.

        Returns:
            List of failed job dictionaries with id, name, conclusion.
        """
        try:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    "-H",
                    "Accept: application/vnd.github+json",
                    f"/repos/{repo}/actions/runs/{run_id}/jobs",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return []

            data = json.loads(result.stdout)
            jobs = data.get("jobs", [])

            # Filter to failed jobs only
            failed_jobs = [job for job in jobs if job.get("conclusion") == "failure"]

            return failed_jobs

        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            return []

    def fetch_logs_for_run(
        self,
        repo: str,
        run_id: str,
    ) -> dict[str, str]:
        """Fetch logs for all failed jobs in a run.

        Args:
            repo: Repository in owner/repo format.
            run_id: GitHub workflow run ID.

        Returns:
            Dictionary mapping job name to log content.
        """
        failed_jobs = self.get_failed_jobs(repo, run_id)
        logs = {}

        for job in failed_jobs:
            job_id = job.get("id")
            job_name = job.get("name", f"job-{job_id}")

            log_content = self.fetch_job_logs(repo, str(job_id))
            if log_content:
                logs[job_name] = log_content

        return logs
