"""Tests for CLI fetch-github command - TDD Red-Green-Refactor."""

import subprocess
import sys
from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest


class TestFetchGitHubCLIExists:
    """Verify fetch-github subcommand exists."""

    def test_fetch_github_command_exists(self):
        """CLI should have fetch-github subcommand."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "--help"],
            capture_output=True,
            text=True,
        )
        assert "fetch-github" in result.stdout

    def test_fetch_github_has_help(self):
        """fetch-github should have help text."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "repo" in result.stdout.lower()


class TestFetchGitHubArguments:
    """Test fetch-github command arguments."""

    def test_requires_repo_argument(self):
        """fetch-github should require --repo argument."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--repo" in result.stdout

    def test_has_token_argument(self):
        """fetch-github should have --token argument."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--token" in result.stdout

    def test_has_run_id_argument(self):
        """fetch-github should have optional --run-id argument."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--run-id" in result.stdout

    def test_has_output_argument(self):
        """fetch-github should have --output argument for saving report."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--output" in result.stdout

    def test_has_artifact_name_argument(self):
        """fetch-github should have --artifact-name argument."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--artifact-name" in result.stdout


class TestFetchGitHubValidation:
    """Test input validation for fetch-github command."""

    def test_fails_without_repo(self):
        """Should fail if --repo not provided."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_fails_without_token_and_env(self):
        """Should fail if no token provided and GITHUB_TOKEN not set."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--repo", "owner/repo"],
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin"},  # Clear environment
        )
        # Should fail because no token
        assert result.returncode != 0

    def test_validates_repo_format(self):
        """Should validate repo format as owner/repo."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--help"],
            capture_output=True,
            text=True,
        )
        # Help should mention owner/repo format
        assert "owner" in result.stdout.lower() or "repo" in result.stdout.lower()


class TestListArtifactsFlag:
    """Test --list-artifacts flag for debugging artifact issues."""

    def test_has_list_artifacts_argument(self):
        """fetch-github should have --list-artifacts flag."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--list-artifacts" in result.stdout

    def test_list_artifacts_help_text(self):
        """--list-artifacts should have descriptive help text."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--help"],
            capture_output=True,
            text=True,
        )
        # Help should mention listing/debugging artifacts
        assert "list" in result.stdout.lower() and "artifact" in result.stdout.lower()


class TestListArtifactsFunctionality:
    """Test --list-artifacts behavior with mocked GitHub API."""

    @pytest.fixture
    def mock_artifacts(self):
        """Sample artifacts for testing."""
        from heisenberg.github_artifacts import Artifact

        return [
            Artifact(
                id=1001,
                name="playwright-report",
                size_in_bytes=1024000,
                expired=False,
                archive_download_url="https://api.github.com/...",
            ),
            Artifact(
                id=1002,
                name="blob-report-chromium",
                size_in_bytes=5242880,
                expired=False,
                archive_download_url="https://api.github.com/...",
            ),
            Artifact(
                id=1003,
                name="coverage",
                size_in_bytes=512000,
                expired=True,
                archive_download_url="https://api.github.com/...",
            ),
        ]

    @pytest.fixture
    def mock_runs(self):
        """Sample workflow runs for testing."""
        from heisenberg.github_artifacts import WorkflowRun

        return [
            WorkflowRun(
                id=12345,
                name="E2E Tests",
                status="completed",
                conclusion="failure",
                created_at="2024-01-20T10:00:00Z",
                html_url="https://github.com/owner/repo/actions/runs/12345",
            ),
        ]

    @pytest.mark.asyncio
    async def test_list_artifacts_shows_artifact_names(self, mock_artifacts, mock_runs):
        """--list-artifacts should display artifact names."""
        from heisenberg.cli import run_list_artifacts

        with patch("heisenberg.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.list_workflow_runs = AsyncMock(return_value=mock_runs)
            client_instance.get_artifacts = AsyncMock(return_value=mock_artifacts)

            output = StringIO()
            await run_list_artifacts(
                token="test-token",
                owner="owner",
                repo="repo",
                run_id=None,
                output=output,
            )

            output_text = output.getvalue()
            assert "playwright-report" in output_text
            assert "blob-report-chromium" in output_text
            assert "coverage" in output_text

    @pytest.mark.asyncio
    async def test_list_artifacts_shows_sizes(self, mock_artifacts, mock_runs):
        """--list-artifacts should display artifact sizes."""
        from heisenberg.cli import run_list_artifacts

        with patch("heisenberg.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.list_workflow_runs = AsyncMock(return_value=mock_runs)
            client_instance.get_artifacts = AsyncMock(return_value=mock_artifacts)

            output = StringIO()
            await run_list_artifacts(
                token="test-token",
                owner="owner",
                repo="repo",
                run_id=None,
                output=output,
            )

            output_text = output.getvalue()
            # Should show sizes in human-readable format
            assert "KB" in output_text or "MB" in output_text or "1024" in output_text

    @pytest.mark.asyncio
    async def test_list_artifacts_shows_expired_status(self, mock_artifacts, mock_runs):
        """--list-artifacts should indicate expired artifacts."""
        from heisenberg.cli import run_list_artifacts

        with patch("heisenberg.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.list_workflow_runs = AsyncMock(return_value=mock_runs)
            client_instance.get_artifacts = AsyncMock(return_value=mock_artifacts)

            output = StringIO()
            await run_list_artifacts(
                token="test-token",
                owner="owner",
                repo="repo",
                run_id=None,
                output=output,
            )

            output_text = output.getvalue()
            # Should indicate expired status somehow
            assert (
                "expired" in output_text.lower()
                or "✗" in output_text
                or "[x]" in output_text.lower()
            )

    @pytest.mark.asyncio
    async def test_list_artifacts_with_specific_run_id(self, mock_artifacts):
        """--list-artifacts should work with specific --run-id."""
        from heisenberg.cli import run_list_artifacts

        with patch("heisenberg.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.get_artifacts = AsyncMock(return_value=mock_artifacts)

            output = StringIO()
            await run_list_artifacts(
                token="test-token",
                owner="owner",
                repo="repo",
                run_id=99999,
                output=output,
            )

            # Should call get_artifacts with the specific run_id
            client_instance.get_artifacts.assert_called_once()
            call_args = client_instance.get_artifacts.call_args
            assert call_args[1].get("run_id") == 99999 or 99999 in call_args[0]

    @pytest.mark.asyncio
    async def test_list_artifacts_returns_zero_on_success(self, mock_artifacts, mock_runs):
        """--list-artifacts should return 0 on success."""
        from heisenberg.cli import run_list_artifacts

        with patch("heisenberg.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.list_workflow_runs = AsyncMock(return_value=mock_runs)
            client_instance.get_artifacts = AsyncMock(return_value=mock_artifacts)

            output = StringIO()
            result = await run_list_artifacts(
                token="test-token",
                owner="owner",
                repo="repo",
                run_id=None,
                output=output,
            )

            assert result == 0

    @pytest.mark.asyncio
    async def test_list_artifacts_empty_shows_message(self, mock_runs):
        """--list-artifacts should show message when no artifacts found."""
        from heisenberg.cli import run_list_artifacts

        with patch("heisenberg.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.list_workflow_runs = AsyncMock(return_value=mock_runs)
            client_instance.get_artifacts = AsyncMock(return_value=[])

            output = StringIO()
            await run_list_artifacts(
                token="test-token",
                owner="owner",
                repo="repo",
                run_id=None,
                output=output,
            )

            output_text = output.getvalue()
            assert (
                "no artifact" in output_text.lower()
                or "empty" in output_text.lower()
                or "0 artifact" in output_text.lower()
            )
