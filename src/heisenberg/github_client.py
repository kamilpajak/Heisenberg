"""GitHub API client for posting PR comments."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import requests

HEISENBERG_MARKER = "## Heisenberg Test Analysis"


@dataclass
class GitHubContext:
    """Context information from GitHub Actions environment."""

    owner: str
    repo: str
    sha: str
    pr_number: int | None
    event_name: str

    @property
    def is_pull_request(self) -> bool:
        """Check if running in PR context."""
        return self.pr_number is not None and self.event_name in (
            "pull_request",
            "pull_request_target",
        )

    @classmethod
    def from_environment(cls) -> GitHubContext:
        """
        Create context from GitHub Actions environment variables.

        Returns:
            GitHubContext with parsed values.
        """
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        parts = repository.split("/")
        owner = parts[0] if len(parts) > 0 else ""
        repo = parts[1] if len(parts) > 1 else ""

        sha = os.environ.get("GITHUB_SHA", "")
        ref = os.environ.get("GITHUB_REF", "")
        event_name = os.environ.get("GITHUB_EVENT_NAME", "")

        # Extract PR number from ref (refs/pull/123/merge)
        pr_number = None
        pr_match = re.match(r"refs/pull/(\d+)/", ref)
        if pr_match:
            pr_number = int(pr_match.group(1))

        return cls(
            owner=owner,
            repo=repo,
            sha=sha,
            pr_number=pr_number,
            event_name=event_name,
        )


class GitHubClient:
    """Client for GitHub API interactions."""

    API_BASE = "https://api.github.com"

    def __init__(self, token: str):
        """
        Initialize client with GitHub token.

        Args:
            token: GitHub personal access token or GITHUB_TOKEN.
        """
        self.token = token

    @classmethod
    def from_environment(cls) -> GitHubClient:
        """
        Create client from GITHUB_TOKEN environment variable.

        Returns:
            GitHubClient instance.

        Raises:
            ValueError: If GITHUB_TOKEN is not set.
        """
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise ValueError(
                "GITHUB_TOKEN environment variable is not set. "
                "Please provide a GitHub token for API access."
            )
        return cls(token=token)

    def _headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def post_pr_comment(self, context: GitHubContext, body: str) -> dict[str, Any]:
        """
        Post a comment to a pull request.

        Args:
            context: GitHub context with repo and PR info.
            body: Comment body in Markdown.

        Returns:
            API response with comment details.

        Raises:
            Exception: If API request fails.
        """
        url = (
            f"{self.API_BASE}/repos/{context.owner}/{context.repo}"
            f"/issues/{context.pr_number}/comments"
        )

        response = requests.post(
            url,
            headers=self._headers(),
            json={"body": body},
            timeout=30,
        )

        if response.status_code not in (200, 201):
            raise Exception(
                f"Failed to post comment: {response.status_code} - "
                f"{response.json().get('message', 'Unknown error')}"
            )

        return response.json()

    def _get_existing_comments(self, context: GitHubContext) -> list[dict[str, Any]]:
        """Get existing comments on a PR."""
        url = (
            f"{self.API_BASE}/repos/{context.owner}/{context.repo}"
            f"/issues/{context.pr_number}/comments"
        )

        response = requests.get(
            url,
            headers=self._headers(),
            timeout=30,
        )

        if response.status_code != 200:
            return []

        return response.json()

    def _update_comment(self, context: GitHubContext, comment_id: int, body: str) -> dict[str, Any]:
        """Update an existing comment."""
        url = f"{self.API_BASE}/repos/{context.owner}/{context.repo}/issues/comments/{comment_id}"

        response = requests.patch(
            url,
            headers=self._headers(),
            json={"body": body},
            timeout=30,
        )

        if response.status_code != 200:
            raise Exception(
                f"Failed to update comment: {response.status_code} - "
                f"{response.json().get('message', 'Unknown error')}"
            )

        return response.json()

    def _find_heisenberg_comment(self, context: GitHubContext) -> int | None:
        """Find existing Heisenberg comment on PR."""
        comments = self._get_existing_comments(context)

        for comment in comments:
            if HEISENBERG_MARKER in comment.get("body", ""):
                return comment["id"]

        return None

    def post_or_update_comment(self, context: GitHubContext, body: str) -> dict[str, Any]:
        """
        Post a new comment or update existing Heisenberg comment.

        Args:
            context: GitHub context with repo and PR info.
            body: Comment body in Markdown.

        Returns:
            API response with comment details.
        """
        existing_id = self._find_heisenberg_comment(context)

        if existing_id:
            return self._update_comment(context, existing_id, body)
        else:
            return self.post_pr_comment(context, body)


def post_pr_comment(body: str) -> dict[str, Any] | None:
    """
    Convenience function to post a PR comment from GitHub Actions.

    Args:
        body: Comment body in Markdown.

    Returns:
        API response if posted, None if not in PR context.
    """
    context = GitHubContext.from_environment()

    if not context.is_pull_request:
        return None

    client = GitHubClient.from_environment()
    return client.post_or_update_comment(context, body)
