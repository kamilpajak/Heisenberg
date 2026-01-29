"""E2E tests for GitHub API - requires real network access.

These tests are marked with @pytest.mark.e2e and are skipped by default.
To run them: pytest -m e2e --run-e2e

Requires GITHUB_TOKEN environment variable to be set.
"""

from __future__ import annotations

import os

import pytest

# Skip all tests in this module if no token or if e2e tests not requested
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not os.environ.get("GITHUB_TOKEN"),
        reason="GITHUB_TOKEN not set - skipping e2e tests",
    ),
]


class TestGitHubAPIConnection:
    """Test basic GitHub API connectivity."""

    @pytest.mark.asyncio
    async def test_can_connect_to_github_api(self):
        """Should successfully connect to GitHub API with valid token."""
        from heisenberg.integrations.github_artifacts import GitHubArtifactClient

        token = os.environ["GITHUB_TOKEN"]
        client = GitHubArtifactClient(token=token)

        # Test with a well-known public repo
        runs = await client.list_workflow_runs("octocat", "Hello-World", per_page=1)

        # Should return a list (may be empty, but should not error)
        assert isinstance(runs, list)

    @pytest.mark.asyncio
    async def test_invalid_token_raises_error(self):
        """Should raise error with invalid token."""
        from heisenberg.integrations.github_artifacts import GitHubAPIError, GitHubArtifactClient

        client = GitHubArtifactClient(token="invalid-token-12345")

        with pytest.raises(GitHubAPIError) as exc_info:
            await client.list_workflow_runs("octocat", "Hello-World")

        assert exc_info.value.status_code == 401


class TestWorkflowRunsListing:
    """Test listing workflow runs from real repositories."""

    @pytest.mark.asyncio
    async def test_list_runs_from_public_repo(self):
        """Should list workflow runs from a public repository."""
        from heisenberg.integrations.github_artifacts import GitHubArtifactClient

        token = os.environ["GITHUB_TOKEN"]
        client = GitHubArtifactClient(token=token)

        # Use playwright repo - always has workflow runs
        runs = await client.list_workflow_runs("microsoft", "playwright", per_page=5)

        assert len(runs) > 0
        assert all(hasattr(r, "id") for r in runs)
        assert all(hasattr(r, "status") for r in runs)
        assert all(hasattr(r, "conclusion") for r in runs)

    @pytest.mark.asyncio
    async def test_list_runs_returns_workflow_run_objects(self):
        """Should return proper WorkflowRun dataclass objects."""
        from heisenberg.integrations.github_artifacts import GitHubArtifactClient, WorkflowRun

        token = os.environ["GITHUB_TOKEN"]
        client = GitHubArtifactClient(token=token)

        runs = await client.list_workflow_runs("microsoft", "playwright", per_page=1)

        if runs:  # May be empty in rare cases
            assert isinstance(runs[0], WorkflowRun)
            assert isinstance(runs[0].id, int)
            assert isinstance(runs[0].html_url, str)
            assert runs[0].html_url.startswith("https://github.com")


class TestArtifactsListing:
    """Test listing artifacts from workflow runs."""

    @pytest.mark.asyncio
    async def test_list_artifacts_from_run(self):
        """Should list artifacts from a workflow run."""
        from heisenberg.integrations.github_artifacts import GitHubArtifactClient

        token = os.environ["GITHUB_TOKEN"]
        client = GitHubArtifactClient(token=token)

        # First get a recent run
        runs = await client.list_workflow_runs("microsoft", "playwright", per_page=10)
        completed_runs = [r for r in runs if r.status == "completed"]

        if not completed_runs:
            pytest.skip("No completed runs available")

        # Get artifacts for the first completed run
        artifacts = await client.get_artifacts(
            "microsoft", "playwright", run_id=completed_runs[0].id
        )

        # Should return a list (may be empty if artifacts expired)
        assert isinstance(artifacts, list)

    @pytest.mark.asyncio
    async def test_artifacts_have_required_fields(self):
        """Artifacts should have all required fields."""
        from heisenberg.integrations.github_artifacts import Artifact, GitHubArtifactClient

        token = os.environ["GITHUB_TOKEN"]
        client = GitHubArtifactClient(token=token)

        runs = await client.list_workflow_runs("microsoft", "playwright", per_page=10)
        completed_runs = [r for r in runs if r.status == "completed"]

        if not completed_runs:
            pytest.skip("No completed runs available")

        for run in completed_runs[:3]:  # Check up to 3 runs
            artifacts = await client.get_artifacts("microsoft", "playwright", run_id=run.id)
            if artifacts:
                artifact = artifacts[0]
                assert isinstance(artifact, Artifact)
                assert isinstance(artifact.id, int)
                assert isinstance(artifact.name, str)
                assert isinstance(artifact.size_in_bytes, int)
                assert isinstance(artifact.expired, bool)
                return

        pytest.skip("No artifacts found in recent runs")


class TestNonExistentRepository:
    """Test error handling for non-existent repositories."""

    @pytest.mark.asyncio
    async def test_nonexistent_repo_raises_404(self):
        """Should raise 404 error for non-existent repository."""
        from heisenberg.integrations.github_artifacts import GitHubAPIError, GitHubArtifactClient

        token = os.environ["GITHUB_TOKEN"]
        client = GitHubArtifactClient(token=token)

        with pytest.raises(GitHubAPIError) as exc_info:
            await client.list_workflow_runs(
                "this-owner-does-not-exist-12345",
                "neither-does-this-repo-67890",
            )

        assert exc_info.value.status_code == 404


class TestRateLimiting:
    """Test behavior under rate limiting scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_requests_succeed(self):
        """Should handle multiple sequential requests without rate limiting."""
        from heisenberg.integrations.github_artifacts import GitHubArtifactClient

        token = os.environ["GITHUB_TOKEN"]
        client = GitHubArtifactClient(token=token)

        # Make 5 sequential requests
        for _ in range(5):
            runs = await client.list_workflow_runs("octocat", "Hello-World", per_page=1)
            assert isinstance(runs, list)
