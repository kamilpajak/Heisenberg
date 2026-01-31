"""Tests for the freeze CLI command."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# --- Test Fixtures ---


class MockFrozenCase(NamedTuple):
    """Mock for FrozenCase result."""

    id: str
    case_dir: Path
    metadata_path: Path
    report_path: Path
    trace_path: Path | None = None
    logs_path: Path | None = None


@pytest.fixture
def mock_freezer():
    """Create a mock CaseFreezer."""
    with patch("heisenberg.cli.commands.CaseFreezer") as MockFreezer:
        instance = MagicMock()
        MockFreezer.return_value = instance
        yield MockFreezer, instance


@pytest.fixture
def mock_gh_token():
    """Mock gh auth token command."""
    with patch("heisenberg.playground.freeze.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="ghp_test_token\n", returncode=0)
        yield mock_run


# --- Command Handler Tests ---


class TestRunFreeze:
    """Tests for run_freeze command handler."""

    @pytest.mark.asyncio
    async def test_run_freeze_creates_freezer_with_config(self, tmp_path):
        """run_freeze should create CaseFreezer with correct config."""
        from heisenberg.cli.commands import run_freeze
        from heisenberg.playground.freeze import FreezeConfig

        args = argparse.Namespace(
            repo="TryGhost/Ghost",
            run_id=12345,
            output=tmp_path,
            token="ghp_test",
        )

        frozen = MockFrozenCase(
            id="tryghost-ghost-12345",
            case_dir=tmp_path / "tryghost-ghost-12345",
            metadata_path=tmp_path / "tryghost-ghost-12345" / "metadata.json",
            report_path=tmp_path / "tryghost-ghost-12345" / "report.json",
        )

        with patch("heisenberg.cli.commands.CaseFreezer") as MockFreezer:
            instance = MagicMock()
            instance.freeze = AsyncMock(return_value=frozen)
            MockFreezer.return_value = instance

            await run_freeze(args)

            MockFreezer.assert_called_once()
            config = MockFreezer.call_args[0][0]
            assert isinstance(config, FreezeConfig)
            assert config.repo == "TryGhost/Ghost"
            assert config.run_id == 12345
            assert config.output_dir == tmp_path
            assert config.github_token == "ghp_test"

    @pytest.mark.asyncio
    async def test_run_freeze_calls_freeze_method(self, tmp_path):
        """run_freeze should call freezer.freeze()."""
        from heisenberg.cli.commands import run_freeze

        args = argparse.Namespace(
            repo="owner/repo",
            run_id=None,
            output=tmp_path,
            token="ghp_test",
        )

        frozen = MockFrozenCase(
            id="owner-repo-latest",
            case_dir=tmp_path / "owner-repo-latest",
            metadata_path=tmp_path / "owner-repo-latest" / "metadata.json",
            report_path=tmp_path / "owner-repo-latest" / "report.json",
        )

        with patch("heisenberg.cli.commands.CaseFreezer") as MockFreezer:
            instance = MagicMock()
            instance.freeze = AsyncMock(return_value=frozen)
            MockFreezer.return_value = instance

            await run_freeze(args)

            instance.freeze.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_freeze_returns_zero_on_success(self, tmp_path):
        """run_freeze should return 0 on successful freeze."""
        from heisenberg.cli.commands import run_freeze

        args = argparse.Namespace(
            repo="owner/repo",
            run_id=12345,
            output=tmp_path,
            token="ghp_test",
        )

        frozen = MockFrozenCase(
            id="owner-repo-12345",
            case_dir=tmp_path / "owner-repo-12345",
            metadata_path=tmp_path / "owner-repo-12345" / "metadata.json",
            report_path=tmp_path / "owner-repo-12345" / "report.json",
        )

        with patch("heisenberg.cli.commands.CaseFreezer") as MockFreezer:
            instance = MagicMock()
            instance.freeze = AsyncMock(return_value=frozen)
            MockFreezer.return_value = instance

            result = await run_freeze(args)

            assert result == 0

    @pytest.mark.asyncio
    async def test_run_freeze_returns_one_on_error(self, tmp_path, capsys):
        """run_freeze should return 1 on error."""
        from heisenberg.cli.commands import run_freeze

        args = argparse.Namespace(
            repo="owner/repo",
            run_id=12345,
            output=tmp_path,
            token="ghp_test",
        )

        with patch("heisenberg.cli.commands.CaseFreezer") as MockFreezer:
            instance = MagicMock()
            instance.freeze = AsyncMock(side_effect=ValueError("No artifacts found"))
            MockFreezer.return_value = instance

            result = await run_freeze(args)

            assert result == 1
            captured = capsys.readouterr()
            assert "No artifacts found" in captured.err

    @pytest.mark.asyncio
    async def test_run_freeze_prints_success_message(self, tmp_path, capsys):
        """run_freeze should print success message with scenario ID."""
        from heisenberg.cli.commands import run_freeze

        args = argparse.Namespace(
            repo="TryGhost/Ghost",
            run_id=12345,
            output=tmp_path,
            token="ghp_test",
        )

        frozen = MockFrozenCase(
            id="tryghost-ghost-12345",
            case_dir=tmp_path / "tryghost-ghost-12345",
            metadata_path=tmp_path / "tryghost-ghost-12345" / "metadata.json",
            report_path=tmp_path / "tryghost-ghost-12345" / "report.json",
        )

        with patch("heisenberg.cli.commands.CaseFreezer") as MockFreezer:
            instance = MagicMock()
            instance.freeze = AsyncMock(return_value=frozen)
            MockFreezer.return_value = instance

            await run_freeze(args)

            captured = capsys.readouterr()
            assert "tryghost-ghost-12345" in captured.out
            assert "frozen successfully" in captured.out.lower() or "Frozen" in captured.out

    @pytest.mark.asyncio
    async def test_run_freeze_prints_case_dir_path(self, tmp_path, capsys):
        """run_freeze should print the scenario directory path."""
        from heisenberg.cli.commands import run_freeze

        args = argparse.Namespace(
            repo="owner/repo",
            run_id=999,
            output=tmp_path,
            token="ghp_test",
        )

        case_dir = tmp_path / "owner-repo-999"
        frozen = MockFrozenCase(
            id="owner-repo-999",
            case_dir=case_dir,
            metadata_path=case_dir / "metadata.json",
            report_path=case_dir / "report.json",
        )

        with patch("heisenberg.cli.commands.CaseFreezer") as MockFreezer:
            instance = MagicMock()
            instance.freeze = AsyncMock(return_value=frozen)
            MockFreezer.return_value = instance

            await run_freeze(args)

            captured = capsys.readouterr()
            assert str(case_dir) in captured.out

    @pytest.mark.asyncio
    async def test_run_freeze_uses_env_token_when_not_provided(self, tmp_path):
        """run_freeze should use GITHUB_TOKEN env var when --token not provided."""
        import os

        from heisenberg.cli.commands import run_freeze

        args = argparse.Namespace(
            repo="owner/repo",
            run_id=12345,
            output=tmp_path,
            token=None,
        )

        frozen = MockFrozenCase(
            id="owner-repo-12345",
            case_dir=tmp_path / "owner-repo-12345",
            metadata_path=tmp_path / "owner-repo-12345" / "metadata.json",
            report_path=tmp_path / "owner-repo-12345" / "report.json",
        )

        with patch.dict(os.environ, {"GITHUB_TOKEN": "env_token"}):
            with patch("heisenberg.cli.commands.CaseFreezer") as MockFreezer:
                instance = MagicMock()
                instance.freeze = AsyncMock(return_value=frozen)
                MockFreezer.return_value = instance

                await run_freeze(args)

                config = MockFreezer.call_args[0][0]
                assert config.github_token == "env_token"

    @pytest.mark.asyncio
    async def test_run_freeze_token_flag_overrides_env(self, tmp_path):
        """--token flag should override GITHUB_TOKEN env var."""
        import os

        from heisenberg.cli.commands import run_freeze

        args = argparse.Namespace(
            repo="owner/repo",
            run_id=12345,
            output=tmp_path,
            token="flag_token",
        )

        frozen = MockFrozenCase(
            id="owner-repo-12345",
            case_dir=tmp_path / "owner-repo-12345",
            metadata_path=tmp_path / "owner-repo-12345" / "metadata.json",
            report_path=tmp_path / "owner-repo-12345" / "report.json",
        )

        with patch.dict(os.environ, {"GITHUB_TOKEN": "env_token"}):
            with patch("heisenberg.cli.commands.CaseFreezer") as MockFreezer:
                instance = MagicMock()
                instance.freeze = AsyncMock(return_value=frozen)
                MockFreezer.return_value = instance

                await run_freeze(args)

                config = MockFreezer.call_args[0][0]
                assert config.github_token == "flag_token"


# --- CLI Integration Tests ---


class TestFreezeMainIntegration:
    """Tests for freeze command integration with main()."""

    def test_main_dispatches_to_freeze(self, tmp_path):
        """CLI should dispatch case freeze command to run_freeze."""
        from unittest.mock import patch

        from typer.testing import CliRunner

        from heisenberg.cli.app import app

        runner = CliRunner()

        with patch("heisenberg.cli.commands.run_freeze") as mock_run:
            mock_run.return_value = 0

            # Test the new `case freeze` command
            result = runner.invoke(
                app,
                ["case", "freeze", "--repo", "owner/repo", "--token", "ghp_x"],
            )

            assert result.exit_code == 0
            mock_run.assert_called_once()
