"""Tests for freeze_scenario module - TDD Red-Green-Refactor.

This module freezes GitHub Actions artifacts into local snapshots
for the Heisenberg playground demo.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import will fail until we implement the module
try:
    from heisenberg.freeze_scenario import (
        FreezeConfig,
        FrozenScenario,
        ScenarioFreezer,
        ScenarioMetadata,
    )
except ImportError:
    ScenarioFreezer = None
    FrozenScenario = None
    ScenarioMetadata = None
    FreezeConfig = None


pytestmark = pytest.mark.skipif(
    ScenarioFreezer is None, reason="freeze_scenario module not implemented yet"
)


# Helper classes for mocking (avoid MagicMock name attribute issues)
class MockWorkflowRun(NamedTuple):
    """Mock workflow run."""

    id: int
    conclusion: str
    html_url: str = ""


class MockArtifact(NamedTuple):
    """Mock artifact."""

    id: int
    name: str
    expired: bool = False


class TestFreezeConfigExists:
    """Verify FreezeConfig dataclass exists with correct fields."""

    def test_freeze_config_exists(self):
        """FreezeConfig should exist."""
        assert FreezeConfig is not None

    def test_freeze_config_has_required_fields(self):
        """FreezeConfig should have repo, output_dir, and optional run_id."""
        config = FreezeConfig(
            repo="owner/repo",
            output_dir=Path("/tmp/scenarios"),
        )
        assert config.repo == "owner/repo"
        assert config.output_dir == Path("/tmp/scenarios")
        assert config.run_id is None  # Optional, defaults to None

    def test_freeze_config_accepts_run_id(self):
        """FreezeConfig should accept optional run_id."""
        config = FreezeConfig(
            repo="owner/repo",
            output_dir=Path("/tmp/scenarios"),
            run_id=12345,
        )
        assert config.run_id == 12345

    def test_freeze_config_accepts_github_token(self):
        """FreezeConfig should accept github_token."""
        config = FreezeConfig(
            repo="owner/repo",
            output_dir=Path("/tmp/scenarios"),
            github_token="ghp_xxx",
        )
        assert config.github_token == "ghp_xxx"


class TestScenarioMetadataExists:
    """Verify ScenarioMetadata dataclass exists."""

    def test_scenario_metadata_exists(self):
        """ScenarioMetadata should exist."""
        assert ScenarioMetadata is not None

    def test_scenario_metadata_has_required_fields(self):
        """ScenarioMetadata should capture source information."""
        metadata = ScenarioMetadata(
            repo="owner/repo",
            repo_url="https://github.com/owner/repo",
            stars=1000,
            run_id=12345,
            run_url="https://github.com/owner/repo/actions/runs/12345",
            captured_at="2026-01-27T12:00:00Z",
            artifact_names=["playwright-report"],
        )
        assert metadata.repo == "owner/repo"
        assert metadata.stars == 1000
        assert metadata.run_id == 12345
        assert "playwright-report" in metadata.artifact_names


class TestFrozenScenarioExists:
    """Verify FrozenScenario dataclass exists."""

    def test_frozen_scenario_exists(self):
        """FrozenScenario should exist."""
        assert FrozenScenario is not None

    def test_frozen_scenario_has_required_fields(self):
        """FrozenScenario should contain paths to frozen assets."""
        scenario = FrozenScenario(
            id="owner-repo-12345",
            scenario_dir=Path("/tmp/scenarios/owner-repo-12345"),
            metadata_path=Path("/tmp/scenarios/owner-repo-12345/metadata.json"),
            report_path=Path("/tmp/scenarios/owner-repo-12345/report.json"),
            trace_path=None,  # Optional
            logs_path=None,  # Optional
        )
        assert scenario.id == "owner-repo-12345"
        assert scenario.scenario_dir.exists is not None  # Path object
        assert scenario.report_path is not None


class TestScenarioFreezerExists:
    """Verify ScenarioFreezer class exists with correct interface."""

    def test_freezer_class_exists(self):
        """ScenarioFreezer class should exist."""
        assert ScenarioFreezer is not None

    def test_freezer_requires_config(self):
        """Freezer should require FreezeConfig."""
        with pytest.raises(TypeError):
            ScenarioFreezer()  # No config provided

    def test_freezer_accepts_config(self):
        """Freezer should accept FreezeConfig."""
        config = FreezeConfig(
            repo="owner/repo",
            output_dir=Path("/tmp/scenarios"),
            github_token="test-token",
        )
        freezer = ScenarioFreezer(config)
        assert freezer is not None

    def test_freezer_has_freeze_method(self):
        """Freezer should have async freeze() method."""
        config = FreezeConfig(
            repo="owner/repo",
            output_dir=Path("/tmp/scenarios"),
            github_token="test-token",
        )
        freezer = ScenarioFreezer(config)
        assert hasattr(freezer, "freeze")
        assert callable(freezer.freeze)


class TestScenarioIdGeneration:
    """Test scenario ID generation from repo and run."""

    def test_generates_valid_id_from_repo(self):
        """Should generate filesystem-safe ID from repo name."""
        config = FreezeConfig(
            repo="TryGhost/Ghost",
            output_dir=Path("/tmp/scenarios"),
            github_token="test-token",
            run_id=12345,
        )
        freezer = ScenarioFreezer(config)

        scenario_id = freezer._generate_scenario_id()

        assert scenario_id is not None
        assert "/" not in scenario_id  # Filesystem safe
        assert "ghost" in scenario_id.lower()
        assert "12345" in scenario_id

    def test_generates_unique_ids_for_different_runs(self):
        """Different runs should produce different IDs."""
        config1 = FreezeConfig(
            repo="owner/repo",
            output_dir=Path("/tmp"),
            github_token="token",
            run_id=111,
        )
        config2 = FreezeConfig(
            repo="owner/repo",
            output_dir=Path("/tmp"),
            github_token="token",
            run_id=222,
        )

        freezer1 = ScenarioFreezer(config1)
        freezer2 = ScenarioFreezer(config2)

        assert freezer1._generate_scenario_id() != freezer2._generate_scenario_id()


class TestFreezeWorkflow:
    """Test the main freeze workflow."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary directory for test output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHubArtifactClient."""
        with patch("heisenberg.freeze_scenario.GitHubArtifactClient") as mock:
            client_instance = AsyncMock()
            # extract_playwright_report is a sync method, not async
            client_instance.extract_playwright_report = MagicMock()
            mock.return_value = client_instance
            yield client_instance

    @pytest.fixture
    def sample_report(self):
        """Sample Playwright report data."""
        return {
            "suites": [
                {
                    "title": "Login Tests",
                    "specs": [
                        {
                            "title": "should login",
                            "ok": False,
                            "tests": [{"status": "failed"}],
                        }
                    ],
                }
            ],
            "stats": {"expected": 5, "unexpected": 2, "flaky": 1, "skipped": 0},
        }

    @pytest.mark.asyncio
    async def test_freeze_creates_scenario_directory(
        self, temp_output_dir, mock_github_client, sample_report
    ):
        """freeze() should create scenario directory structure."""
        # Setup mocks using NamedTuple helpers
        mock_github_client.list_workflow_runs.return_value = [
            MockWorkflowRun(id=12345, conclusion="failure")
        ]
        mock_github_client.get_artifacts.return_value = [
            MockArtifact(id=67890, name="playwright-report", expired=False)
        ]
        mock_github_client.download_artifact.return_value = b"fake-zip"
        mock_github_client.extract_playwright_report.return_value = sample_report

        config = FreezeConfig(
            repo="owner/repo",
            output_dir=temp_output_dir,
            github_token="test-token",
        )
        freezer = ScenarioFreezer(config)

        result = await freezer.freeze()

        assert result is not None
        assert isinstance(result, FrozenScenario)
        assert result.scenario_dir.exists()

    @pytest.mark.asyncio
    async def test_freeze_saves_metadata_json(
        self, temp_output_dir, mock_github_client, sample_report
    ):
        """freeze() should save metadata.json with source info."""
        mock_github_client.list_workflow_runs.return_value = [
            MockWorkflowRun(
                id=12345,
                conclusion="failure",
                html_url="https://github.com/owner/repo/actions/runs/12345",
            )
        ]
        mock_github_client.get_artifacts.return_value = [
            MockArtifact(id=67890, name="playwright-report", expired=False)
        ]
        mock_github_client.download_artifact.return_value = b"fake-zip"
        mock_github_client.extract_playwright_report.return_value = sample_report

        # Mock repo info for stars
        with patch("heisenberg.freeze_scenario.get_repo_stars", return_value=5000):
            config = FreezeConfig(
                repo="owner/repo",
                output_dir=temp_output_dir,
                github_token="test-token",
            )
            freezer = ScenarioFreezer(config)

            result = await freezer.freeze()

        assert result.metadata_path.exists()
        metadata = json.loads(result.metadata_path.read_text())
        assert metadata["repo"] == "owner/repo"
        assert metadata["run_id"] == 12345
        assert "captured_at" in metadata

    @pytest.mark.asyncio
    async def test_freeze_saves_report_json(
        self, temp_output_dir, mock_github_client, sample_report
    ):
        """freeze() should save the Playwright report as report.json."""
        mock_github_client.list_workflow_runs.return_value = [
            MockWorkflowRun(id=12345, conclusion="failure")
        ]
        mock_github_client.get_artifacts.return_value = [
            MockArtifact(id=67890, name="playwright-report", expired=False)
        ]
        mock_github_client.download_artifact.return_value = b"fake-zip"
        mock_github_client.extract_playwright_report.return_value = sample_report

        config = FreezeConfig(
            repo="owner/repo",
            output_dir=temp_output_dir,
            github_token="test-token",
        )
        freezer = ScenarioFreezer(config)

        result = await freezer.freeze()

        assert result.report_path.exists()
        saved_report = json.loads(result.report_path.read_text())
        assert saved_report["stats"]["unexpected"] == 2

    @pytest.mark.asyncio
    async def test_freeze_uses_specified_run_id(
        self, temp_output_dir, mock_github_client, sample_report
    ):
        """freeze() should use specified run_id instead of finding latest."""
        mock_github_client.get_artifacts.return_value = [
            MockArtifact(id=67890, name="playwright-report", expired=False)
        ]
        mock_github_client.download_artifact.return_value = b"fake-zip"
        mock_github_client.extract_playwright_report.return_value = sample_report

        config = FreezeConfig(
            repo="owner/repo",
            output_dir=temp_output_dir,
            github_token="test-token",
            run_id=99999,  # Specific run ID
        )
        freezer = ScenarioFreezer(config)

        await freezer.freeze()

        # Should NOT call list_workflow_runs when run_id is provided
        mock_github_client.list_workflow_runs.assert_not_called()
        # Should call get_artifacts with the specified run_id
        mock_github_client.get_artifacts.assert_called_once()
        call_args = mock_github_client.get_artifacts.call_args
        assert call_args[1].get("run_id") == 99999 or 99999 in call_args[0]


class TestFreezeErrorHandling:
    """Test error handling in freeze workflow."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary directory for test output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_freeze_raises_on_no_failed_runs(self, temp_output_dir):
        """Should raise error when no failed runs found."""
        with patch("heisenberg.freeze_scenario.GitHubArtifactClient") as mock_client:
            mock_client.return_value.list_workflow_runs = AsyncMock(return_value=[])

            config = FreezeConfig(
                repo="owner/repo",
                output_dir=temp_output_dir,
                github_token="test-token",
            )
            freezer = ScenarioFreezer(config)

            with pytest.raises(ValueError, match="No failed.*runs"):
                await freezer.freeze()

    @pytest.mark.asyncio
    async def test_freeze_raises_on_no_playwright_artifacts(self, temp_output_dir):
        """Should raise error when no Playwright artifacts found."""
        with patch("heisenberg.freeze_scenario.GitHubArtifactClient") as mock_client:
            client = AsyncMock()
            mock_client.return_value = client
            client.list_workflow_runs.return_value = [
                MockWorkflowRun(id=12345, conclusion="failure")
            ]
            client.get_artifacts.return_value = [
                MockArtifact(id=1, name="coverage-report", expired=False)
            ]

            config = FreezeConfig(
                repo="owner/repo",
                output_dir=temp_output_dir,
                github_token="test-token",
            )
            freezer = ScenarioFreezer(config)

            with pytest.raises(ValueError, match="No Playwright.*artifacts"):
                await freezer.freeze()

    @pytest.mark.asyncio
    async def test_freeze_raises_on_expired_artifacts(self, temp_output_dir):
        """Should raise error when all Playwright artifacts are expired."""
        with patch("heisenberg.freeze_scenario.GitHubArtifactClient") as mock_client:
            client = AsyncMock()
            mock_client.return_value = client
            client.list_workflow_runs.return_value = [
                MockWorkflowRun(id=12345, conclusion="failure")
            ]
            client.get_artifacts.return_value = [
                MockArtifact(id=1, name="playwright-report", expired=True)
            ]

            config = FreezeConfig(
                repo="owner/repo",
                output_dir=temp_output_dir,
                github_token="test-token",
            )
            freezer = ScenarioFreezer(config)

            with pytest.raises(ValueError, match="expired"):
                await freezer.freeze()


class TestArtifactFiltering:
    """Test artifact name filtering logic."""

    def test_is_playwright_artifact_matches_common_names(self):
        """Should recognize common Playwright artifact names."""
        config = FreezeConfig(
            repo="owner/repo",
            output_dir=Path("/tmp"),
            github_token="token",
        )
        freezer = ScenarioFreezer(config)

        playwright_names = [
            "playwright-report",
            "playwright-report-ubuntu",
            "blob-report",
            "blob-report-1",
            "test-results",
            "e2e-report",
            "e2e-test-results",
        ]

        for name in playwright_names:
            assert freezer._is_playwright_artifact(name), f"Should match: {name}"

    def test_is_playwright_artifact_rejects_unrelated(self):
        """Should reject non-Playwright artifact names."""
        config = FreezeConfig(
            repo="owner/repo",
            output_dir=Path("/tmp"),
            github_token="token",
        )
        freezer = ScenarioFreezer(config)

        non_playwright_names = [
            "coverage-report",
            "build-artifacts",
            "docker-image",
            "npm-cache",
        ]

        for name in non_playwright_names:
            assert not freezer._is_playwright_artifact(name), f"Should not match: {name}"


class TestTraceHandling:
    """Test handling of Playwright trace files."""

    @pytest.fixture
    def temp_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_freeze_saves_trace_zip_if_present(self, temp_output_dir):
        """Should save trace.zip if trace artifact is found."""
        with patch("heisenberg.freeze_scenario.GitHubArtifactClient") as mock_client:
            client = AsyncMock()
            mock_client.return_value = client
            client.list_workflow_runs.return_value = [
                MockWorkflowRun(id=12345, conclusion="failure")
            ]
            client.get_artifacts.return_value = [
                MockArtifact(id=1, name="playwright-report", expired=False),
                MockArtifact(id=2, name="playwright-traces", expired=False),
            ]
            client.download_artifact.side_effect = [
                b"report-zip-content",
                b"trace-zip-content",
            ]
            # extract_playwright_report is sync, not async
            client.extract_playwright_report = MagicMock(
                return_value={
                    "suites": [],
                    "stats": {"expected": 1, "unexpected": 0},
                }
            )

            config = FreezeConfig(
                repo="owner/repo",
                output_dir=temp_output_dir,
                github_token="test-token",
            )
            freezer = ScenarioFreezer(config)

            result = await freezer.freeze()

            assert result.trace_path is not None
            assert result.trace_path.exists()
