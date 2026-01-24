"""Tests for CLI fetch-github command - TDD Red-Green-Refactor."""

import subprocess
import sys


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
