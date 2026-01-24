"""GitHub Artifacts client for fetching Playwright reports from GitHub Actions.

This module provides functionality to:
- List workflow runs for a repository
- Get artifacts from a specific run
- Download and extract Playwright JSON reports
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from typing import Any

import httpx


class GitHubAPIError(Exception):
    """Exception raised for GitHub API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.status_code:
            return f"GitHub API Error ({self.status_code}): {self.message}"
        return f"GitHub API Error: {self.message}"


@dataclass
class WorkflowRun:
    """Represents a GitHub Actions workflow run."""

    id: int
    name: str
    status: str
    conclusion: str | None
    created_at: str
    html_url: str


@dataclass
class Artifact:
    """Represents a GitHub Actions artifact."""

    id: int
    name: str
    size_in_bytes: int
    expired: bool
    archive_download_url: str


class GitHubArtifactClient:
    """Client for fetching artifacts from GitHub Actions.

    Usage:
        client = GitHubArtifactClient(token="ghp_xxx")
        runs = await client.list_workflow_runs("owner", "repo", status="failure")
        artifacts = await client.get_artifacts("owner", "repo", run_id=runs[0].id)
        zip_data = await client.download_artifact("owner", "repo", artifact_id=artifacts[0].id)
        report = client.extract_playwright_report(zip_data)
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        """Initialize the client with a GitHub token.

        Args:
            token: GitHub personal access token or GITHUB_TOKEN
        """
        if not token:
            raise ValueError("GitHub token is required")
        self.token = token
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to the GitHub API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., /repos/owner/repo/actions/runs)
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            GitHubAPIError: On API errors
        """
        url = f"{self.BASE_URL}{endpoint}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method,
                    url,
                    headers=self._headers,
                    params=params,
                    timeout=30.0,
                )

                if response.status_code == 401:
                    raise GitHubAPIError("Unauthorized - check your token", status_code=401)
                elif response.status_code == 403:
                    raise GitHubAPIError("Rate limit exceeded or forbidden", status_code=403)
                elif response.status_code == 404:
                    raise GitHubAPIError("Not found", status_code=404)
                elif response.status_code >= 400:
                    raise GitHubAPIError(
                        f"Request failed: {response.text}",
                        status_code=response.status_code,
                    )

                return response.json()

            except httpx.RequestError as e:
                raise GitHubAPIError(f"Request failed: {e}") from e

    async def _download(self, url: str) -> bytes:
        """Download binary content from a URL.

        Args:
            url: Full URL to download from

        Returns:
            Binary content

        Raises:
            GitHubAPIError: On download errors
        """
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(
                    url,
                    headers=self._headers,
                    timeout=60.0,
                )

                if response.status_code >= 400:
                    raise GitHubAPIError(
                        f"Download failed: {response.status_code}",
                        status_code=response.status_code,
                    )

                return response.content

            except httpx.RequestError as e:
                raise GitHubAPIError(f"Download failed: {e}") from e

    async def list_workflow_runs(
        self,
        owner: str,
        repo: str,
        status: str | None = None,
        per_page: int = 30,
    ) -> list[WorkflowRun]:
        """List workflow runs for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            status: Filter by status (queued, in_progress, completed)
            per_page: Number of results per page (max 100)

        Returns:
            List of WorkflowRun objects
        """
        params: dict[str, Any] = {"per_page": per_page}
        if status:
            params["status"] = status

        data = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/actions/runs",
            params=params,
        )

        return [
            WorkflowRun(
                id=run["id"],
                name=run.get("name", ""),
                status=run["status"],
                conclusion=run.get("conclusion"),
                created_at=run["created_at"],
                html_url=run["html_url"],
            )
            for run in data.get("workflow_runs", [])
        ]

    async def get_artifacts(
        self,
        owner: str,
        repo: str,
        run_id: int,
        include_expired: bool = True,
    ) -> list[Artifact]:
        """Get artifacts for a specific workflow run.

        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID
            include_expired: Whether to include expired artifacts

        Returns:
            List of Artifact objects
        """
        data = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts",
        )

        artifacts = []
        for artifact in data.get("artifacts", []):
            a = Artifact(
                id=artifact["id"],
                name=artifact["name"],
                size_in_bytes=artifact["size_in_bytes"],
                expired=artifact["expired"],
                archive_download_url=artifact["archive_download_url"],
            )
            if include_expired or not a.expired:
                artifacts.append(a)

        return artifacts

    async def download_artifact(
        self,
        owner: str,
        repo: str,
        artifact_id: int,
    ) -> bytes:
        """Download an artifact as a zip file.

        Args:
            owner: Repository owner
            repo: Repository name
            artifact_id: Artifact ID

        Returns:
            Zip file content as bytes
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/artifacts/{artifact_id}/zip"
        return await self._download(url)

    @staticmethod
    def _is_playwright_report(data: Any) -> bool:
        """Check if data looks like a Playwright report."""
        return isinstance(data, dict) and ("suites" in data or "stats" in data)

    @staticmethod
    def _try_parse_json_file(zf: zipfile.ZipFile, filename: str) -> dict | None:
        """Try to parse a JSON file and check if it's a Playwright report."""
        try:
            content = zf.read(filename)
            data = json.loads(content)
            if GitHubArtifactClient._is_playwright_report(data):
                return data
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    @staticmethod
    def _get_prioritized_json_files(json_files: list[str]) -> list[str]:
        """Get JSON files ordered by priority (report/results files first)."""
        priority_files = [f for f in json_files if "report" in f.lower() or "results" in f.lower()]
        other_files = [f for f in json_files if f not in priority_files]
        return priority_files + other_files

    def extract_playwright_report(self, zip_content: bytes) -> dict | None:
        """Extract Playwright JSON report from a zip file.

        Searches for JSON files that look like Playwright reports
        (contain 'suites' and 'stats' keys).

        Args:
            zip_content: Zip file content as bytes

        Returns:
            Parsed JSON report or None if not found
        """
        try:
            zip_buffer = io.BytesIO(zip_content)
            with zipfile.ZipFile(zip_buffer, "r") as zf:
                json_files = [name for name in zf.namelist() if name.endswith(".json")]
                if not json_files:
                    return None

                for json_file in self._get_prioritized_json_files(json_files):
                    report = self._try_parse_json_file(zf, json_file)
                    if report:
                        return report

                return None
        except zipfile.BadZipFile:
            return None

    async def fetch_latest_report(
        self,
        owner: str,
        repo: str,
        workflow_name: str | None = None,
        conclusion: str = "failure",
        artifact_name_pattern: str = "playwright",
    ) -> dict | None:
        """Convenience method to fetch the latest Playwright report.

        Args:
            owner: Repository owner
            repo: Repository name
            workflow_name: Filter by workflow name (optional)
            conclusion: Filter by conclusion (failure, success, etc.)
            artifact_name_pattern: Pattern to match artifact names

        Returns:
            Parsed Playwright report or None if not found
        """
        # Get recent runs with the specified conclusion
        runs = await self.list_workflow_runs(owner, repo)

        # Filter by conclusion and optionally by name
        matching_runs = [
            r
            for r in runs
            if r.conclusion == conclusion
            and (workflow_name is None or workflow_name.lower() in r.name.lower())
        ]

        if not matching_runs:
            return None

        # Try to find an artifact with Playwright report
        for run in matching_runs[:5]:  # Check up to 5 most recent runs
            artifacts = await self.get_artifacts(owner, repo, run.id, include_expired=False)

            # Find artifact matching the pattern
            matching_artifacts = [
                a for a in artifacts if artifact_name_pattern.lower() in a.name.lower()
            ]

            for artifact in matching_artifacts:
                zip_data = await self.download_artifact(owner, repo, artifact.id)
                report = self.extract_playwright_report(zip_data)
                if report:
                    return report

        return None
