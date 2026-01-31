"""Tests for the new Typer-based CLI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from heisenberg.cli.app import app, is_github_repo

runner = CliRunner()


class TestGitHubRepoDetection:
    """Tests for auto-detection of GitHub repo format."""

    @pytest.mark.parametrize(
        "target,expected",
        [
            ("owner/repo", True),
            ("microsoft/playwright", True),
            ("my-org/my-repo.js", True),
            ("owner/repo-name", True),
            ("Owner123/Repo_456", True),
            ("./report.json", False),
            ("/absolute/path/report.json", False),
            ("relative/path/to/file.json", False),  # Has 2 slashes
            ("owner/repo/extra", False),  # Too many parts
            ("justrepo", False),  # No slash
            ("", False),  # Empty
        ],
    )
    def test_is_github_repo(self, target: str, expected: bool) -> None:
        """Test GitHub repo pattern detection."""
        assert is_github_repo(target) == expected


class TestHelpCommands:
    """Tests for help output of all commands."""

    def test_main_help(self) -> None:
        """Test main app help shows all commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "analyze" in result.output
        assert "discover" in result.output
        assert "case" in result.output

    def test_analyze_help(self) -> None:
        """Test analyze command help."""
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "TARGET" in result.output
        assert "--ai-analysis" in result.output
        assert "--output-format" in result.output

    def test_discover_help(self) -> None:
        """Test discover command help."""
        result = runner.invoke(app, ["discover", "--help"])
        assert result.exit_code == 0
        assert "--repo" in result.output
        assert "--min-stars" in result.output
        assert "--limit" in result.output

    def test_case_help(self) -> None:
        """Test case subcommand group help."""
        result = runner.invoke(app, ["case", "--help"])
        assert result.exit_code == 0
        assert "freeze" in result.output
        assert "replay" in result.output
        assert "validate" in result.output
        assert "index" in result.output

    def test_case_freeze_help(self) -> None:
        """Test case freeze help."""
        result = runner.invoke(app, ["case", "freeze", "--help"])
        assert result.exit_code == 0
        assert "--repo" in result.output
        assert "--output" in result.output
        assert "--token" in result.output

    def test_case_replay_help(self) -> None:
        """Test case replay help."""
        result = runner.invoke(app, ["case", "replay", "--help"])
        assert result.exit_code == 0
        assert "CASE_DIR" in result.output
        assert "--provider" in result.output

    def test_case_validate_help(self) -> None:
        """Test case validate help."""
        result = runner.invoke(app, ["case", "validate", "--help"])
        assert result.exit_code == 0
        assert "CASES_DIR" in result.output
        assert "--max-age" in result.output
        assert "--json" in result.output

    def test_case_index_help(self) -> None:
        """Test case index help."""
        result = runner.invoke(app, ["case", "index", "--help"])
        assert result.exit_code == 0
        assert "CASES_DIR" in result.output
        assert "--output" in result.output
        assert "--include-pending" in result.output


class TestDiscoverCommand:
    """Tests for discover command."""

    @patch("heisenberg.cli.commands.run_discover")
    def test_discover_single_repo(self, mock_run_discover: MagicMock) -> None:
        """Test discover with --repo flag."""
        mock_run_discover.return_value = 0

        result = runner.invoke(app, ["discover", "--repo", "owner/repo"])

        assert result.exit_code == 0
        mock_run_discover.assert_called_once()
        args = mock_run_discover.call_args[0][0]
        assert args.repo == "owner/repo"

    @patch("heisenberg.cli.commands.run_discover")
    def test_discover_search_mode(self, mock_run_discover: MagicMock) -> None:
        """Test discover in search mode."""
        mock_run_discover.return_value = 0

        result = runner.invoke(app, ["discover", "--min-stars", "500", "--limit", "10"])

        assert result.exit_code == 0
        args = mock_run_discover.call_args[0][0]
        assert args.min_stars == 500
        assert args.limit == 10
        assert args.repo is None

    @patch("heisenberg.cli.commands.run_discover")
    def test_discover_with_cache_flags(self, mock_run_discover: MagicMock) -> None:
        """Test discover with caching flags."""
        mock_run_discover.return_value = 0

        result = runner.invoke(app, ["discover", "--no-cache", "--fresh"])

        assert result.exit_code == 0
        args = mock_run_discover.call_args[0][0]
        assert args.no_cache is True
        assert args.fresh is True

    @patch("heisenberg.cli.commands.run_discover")
    def test_discover_json_output(self, mock_run_discover: MagicMock) -> None:
        """Test discover with JSON output."""
        mock_run_discover.return_value = 0

        result = runner.invoke(app, ["discover", "--json"])

        assert result.exit_code == 0
        args = mock_run_discover.call_args[0][0]
        assert args.json_output is True


class TestAnalyzeCommand:
    """Tests for analyze command with auto-detection."""

    @patch("heisenberg.cli.commands.run_analyze")
    def test_analyze_local_file(self, mock_run_analyze: MagicMock) -> None:
        """Test analyze with local file path."""
        mock_run_analyze.return_value = 0

        result = runner.invoke(app, ["analyze", "./report.json"])

        assert result.exit_code == 0
        mock_run_analyze.assert_called_once()
        args = mock_run_analyze.call_args[0][0]
        assert args.report == Path("./report.json")

    @patch("heisenberg.cli.commands.run_fetch_github")
    def test_analyze_github_repo(self, mock_run_fetch: AsyncMock) -> None:
        """Test analyze with GitHub repo auto-detection."""
        mock_run_fetch.return_value = 0

        result = runner.invoke(app, ["analyze", "owner/repo"])

        assert result.exit_code == 0
        mock_run_fetch.assert_called_once()
        args = mock_run_fetch.call_args[0][0]
        assert args.repo == "owner/repo"

    @patch("heisenberg.cli.commands.run_analyze")
    def test_analyze_with_ai_analysis(self, mock_run_analyze: MagicMock) -> None:
        """Test analyze with AI analysis enabled."""
        mock_run_analyze.return_value = 0

        result = runner.invoke(
            app,
            ["analyze", "./report.json", "--ai-analysis", "--provider", "anthropic"],
        )

        assert result.exit_code == 0
        args = mock_run_analyze.call_args[0][0]
        assert args.ai_analysis is True
        assert args.provider == "anthropic"

    @patch("heisenberg.cli.commands.run_fetch_github")
    def test_analyze_github_with_options(self, mock_run_fetch: AsyncMock) -> None:
        """Test analyze GitHub with additional options."""
        mock_run_fetch.return_value = 0

        result = runner.invoke(
            app,
            [
                "analyze",
                "owner/repo",
                "--merge-blobs",
                "--include-logs",
                "--ai-analysis",
            ],
        )

        assert result.exit_code == 0
        args = mock_run_fetch.call_args[0][0]
        assert args.merge_blobs is True
        assert args.include_logs is True
        assert args.ai_analysis is True


class TestCaseCommands:
    """Tests for case subcommand group."""

    @patch("heisenberg.cli.commands.run_freeze")
    def test_case_freeze(self, mock_run_freeze: AsyncMock) -> None:
        """Test case freeze command."""
        mock_run_freeze.return_value = 0

        result = runner.invoke(
            app, ["case", "freeze", "--repo", "owner/repo", "--output", "./my-cases"]
        )

        assert result.exit_code == 0
        mock_run_freeze.assert_called_once()
        args = mock_run_freeze.call_args[0][0]
        assert args.repo == "owner/repo"
        assert args.output == Path("./my-cases")

    @patch("heisenberg.cli.commands.run_analyze_case")
    def test_case_replay(self, mock_run_analyze: MagicMock) -> None:
        """Test case replay command."""
        mock_run_analyze.return_value = 0

        result = runner.invoke(app, ["case", "replay", "./cases/some-case", "--provider", "openai"])

        assert result.exit_code == 0
        mock_run_analyze.assert_called_once()
        args = mock_run_analyze.call_args[0][0]
        assert args.case_dir == Path("./cases/some-case")
        assert args.provider == "openai"

    @patch("heisenberg.cli.commands.run_validate_cases")
    def test_case_validate(self, mock_run_validate: MagicMock) -> None:
        """Test case validate command."""
        mock_run_validate.return_value = 0

        result = runner.invoke(app, ["case", "validate", "./cases", "--max-age", "30", "--json"])

        assert result.exit_code == 0
        mock_run_validate.assert_called_once()
        args = mock_run_validate.call_args[0][0]
        assert args.cases_dir == Path("./cases")
        assert args.max_age == 30
        assert args.json is True

    @patch("heisenberg.cli.commands.run_generate_manifest")
    def test_case_index(self, mock_run_manifest: MagicMock) -> None:
        """Test case index command."""
        mock_run_manifest.return_value = 0

        result = runner.invoke(
            app,
            ["case", "index", "./cases", "--output", "./manifest.json", "--include-pending"],
        )

        assert result.exit_code == 0
        mock_run_manifest.assert_called_once()
        args = mock_run_manifest.call_args[0][0]
        assert args.cases_dir == Path("./cases")
        assert args.output == Path("./manifest.json")
        assert args.include_pending is True


class TestExitCodes:
    """Tests for correct exit code propagation."""

    @patch("heisenberg.cli.commands.run_analyze")
    def test_analyze_failure_exit_code(self, mock_run_analyze: MagicMock) -> None:
        """Test that failure exit code is propagated."""
        mock_run_analyze.return_value = 1

        result = runner.invoke(app, ["analyze", "./report.json"])

        assert result.exit_code == 1

    @patch("heisenberg.cli.commands.run_discover")
    def test_discover_incompatible_exit_code(self, mock_run_discover: MagicMock) -> None:
        """Test that incompatible repo returns exit code 1."""
        mock_run_discover.return_value = 1

        result = runner.invoke(app, ["discover", "--repo", "owner/repo"])

        assert result.exit_code == 1

    @patch("heisenberg.cli.commands.run_validate_cases")
    def test_validate_issues_exit_code(self, mock_run_validate: MagicMock) -> None:
        """Test that validation issues return exit code 1."""
        mock_run_validate.return_value = 1

        result = runner.invoke(app, ["case", "validate", "./cases"])

        assert result.exit_code == 1
