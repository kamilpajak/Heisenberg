"""Tests for freeze_case module - TDD Red-Green-Refactor.

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
    from heisenberg.playground.freeze import (
        CaseFreezer,
        CaseMetadata,
        FreezeConfig,
        FrozenCase,
    )
except ImportError:
    CaseFreezer = None
    FrozenCase = None
    CaseMetadata = None
    FreezeConfig = None


pytestmark = pytest.mark.skipif(
    CaseFreezer is None, reason="freeze_case module not implemented yet"
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


class TestCaseMetadataExists:
    """Verify CaseMetadata dataclass exists."""

    def test_scenario_metadata_exists(self):
        """CaseMetadata should exist."""
        assert CaseMetadata is not None

    def test_scenario_metadata_has_required_fields(self):
        """CaseMetadata should capture source information."""
        metadata = CaseMetadata(
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


class TestFrozenCaseExists:
    """Verify FrozenCase dataclass exists."""

    def test_frozen_scenario_exists(self):
        """FrozenCase should exist."""
        assert FrozenCase is not None

    def test_frozen_scenario_has_required_fields(self):
        """FrozenCase should contain paths to frozen assets."""
        scenario = FrozenCase(
            id="owner-repo-12345",
            case_dir=Path("/tmp/scenarios/owner-repo-12345"),
            metadata_path=Path("/tmp/scenarios/owner-repo-12345/metadata.json"),
            report_path=Path("/tmp/scenarios/owner-repo-12345/report.json"),
            trace_path=None,  # Optional
            logs_path=None,  # Optional
        )
        assert scenario.id == "owner-repo-12345"
        assert scenario.case_dir.exists is not None  # Path object
        assert scenario.report_path is not None


class TestCaseFreezerExists:
    """Verify CaseFreezer class exists with correct interface."""

    def test_freezer_class_exists(self):
        """CaseFreezer class should exist."""
        assert CaseFreezer is not None

    def test_freezer_requires_config(self):
        """Freezer should require FreezeConfig."""
        with pytest.raises(TypeError):
            CaseFreezer()  # No config provided

    def test_freezer_accepts_config(self):
        """Freezer should accept FreezeConfig."""
        config = FreezeConfig(
            repo="owner/repo",
            output_dir=Path("/tmp/scenarios"),
            github_token="test-token",
        )
        freezer = CaseFreezer(config)
        assert freezer is not None

    def test_freezer_has_freeze_method(self):
        """Freezer should have async freeze() method."""
        config = FreezeConfig(
            repo="owner/repo",
            output_dir=Path("/tmp/scenarios"),
            github_token="test-token",
        )
        freezer = CaseFreezer(config)
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
        freezer = CaseFreezer(config)

        case_id = freezer._generate_case_id()

        assert case_id is not None
        assert "/" not in case_id  # Filesystem safe
        assert "ghost" in case_id.lower()
        assert "12345" in case_id

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

        freezer1 = CaseFreezer(config1)
        freezer2 = CaseFreezer(config2)

        assert freezer1._generate_case_id() != freezer2._generate_case_id()


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
        with patch("heisenberg.playground.freeze.GitHubArtifactClient") as mock:
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

    @pytest.fixture
    def sample_report_zip(self, sample_report):
        """Sample Playwright report as a valid ZIP file."""
        import io
        import zipfile

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("report.json", json.dumps(sample_report))
        return zip_buffer.getvalue()

    @pytest.mark.asyncio
    async def test_freeze_creates_case_directory(
        self, temp_output_dir, mock_github_client, sample_report_zip
    ):
        """freeze() should create scenario directory structure."""
        # Setup mocks using NamedTuple helpers
        mock_github_client.list_workflow_runs.return_value = [
            MockWorkflowRun(id=12345, conclusion="failure")
        ]
        mock_github_client.get_artifacts.return_value = [
            MockArtifact(id=67890, name="playwright-report", expired=False)
        ]
        mock_github_client.download_artifact.return_value = sample_report_zip

        config = FreezeConfig(
            repo="owner/repo",
            output_dir=temp_output_dir,
            github_token="test-token",
        )
        freezer = CaseFreezer(config)

        result = await freezer.freeze()

        assert result is not None
        assert isinstance(result, FrozenCase)
        assert result.case_dir.exists()

    @pytest.mark.asyncio
    async def test_freeze_saves_metadata_json(
        self, temp_output_dir, mock_github_client, sample_report_zip
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
        mock_github_client.download_artifact.return_value = sample_report_zip

        # Mock repo info for stars
        with patch("heisenberg.playground.freeze.get_repo_stars", return_value=5000):
            config = FreezeConfig(
                repo="owner/repo",
                output_dir=temp_output_dir,
                github_token="test-token",
            )
            freezer = CaseFreezer(config)

            result = await freezer.freeze()

        assert result.metadata_path.exists()
        metadata = json.loads(result.metadata_path.read_text())
        assert metadata["repo"] == "owner/repo"
        assert metadata["run_id"] == 12345
        assert "captured_at" in metadata

    @pytest.mark.asyncio
    async def test_freeze_saves_report_json(
        self, temp_output_dir, mock_github_client, sample_report_zip
    ):
        """freeze() should save the Playwright report as report.json."""
        mock_github_client.list_workflow_runs.return_value = [
            MockWorkflowRun(id=12345, conclusion="failure")
        ]
        mock_github_client.get_artifacts.return_value = [
            MockArtifact(id=67890, name="playwright-report", expired=False)
        ]
        mock_github_client.download_artifact.return_value = sample_report_zip

        config = FreezeConfig(
            repo="owner/repo",
            output_dir=temp_output_dir,
            github_token="test-token",
        )
        freezer = CaseFreezer(config)

        result = await freezer.freeze()

        assert result.report_path.exists()
        saved_report = json.loads(result.report_path.read_text())
        assert saved_report["stats"]["unexpected"] == 2

    @pytest.mark.asyncio
    async def test_freeze_uses_specified_run_id(
        self, temp_output_dir, mock_github_client, sample_report_zip
    ):
        """freeze() should use specified run_id instead of finding latest."""
        mock_github_client.get_artifacts.return_value = [
            MockArtifact(id=67890, name="playwright-report", expired=False)
        ]
        mock_github_client.download_artifact.return_value = sample_report_zip

        config = FreezeConfig(
            repo="owner/repo",
            output_dir=temp_output_dir,
            github_token="test-token",
            run_id=99999,  # Specific run ID
        )
        freezer = CaseFreezer(config)

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
        with patch("heisenberg.playground.freeze.GitHubArtifactClient") as mock_client:
            mock_client.return_value.list_workflow_runs = AsyncMock(return_value=[])

            config = FreezeConfig(
                repo="owner/repo",
                output_dir=temp_output_dir,
                github_token="test-token",
            )
            freezer = CaseFreezer(config)

            with pytest.raises(ValueError, match="No failed.*runs"):
                await freezer.freeze()

    @pytest.mark.asyncio
    async def test_freeze_raises_on_no_playwright_artifacts(self, temp_output_dir):
        """Should raise error when no Playwright artifacts found."""
        with patch("heisenberg.playground.freeze.GitHubArtifactClient") as mock_client:
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
            freezer = CaseFreezer(config)

            with pytest.raises(ValueError, match="No Playwright.*artifacts"):
                await freezer.freeze()

    @pytest.mark.asyncio
    async def test_freeze_raises_on_expired_artifacts(self, temp_output_dir):
        """Should raise error when all Playwright artifacts are expired."""
        with patch("heisenberg.playground.freeze.GitHubArtifactClient") as mock_client:
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
            freezer = CaseFreezer(config)

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
        freezer = CaseFreezer(config)

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
        freezer = CaseFreezer(config)

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
        import io
        import zipfile

        # Create a valid Playwright report ZIP with at least one failure
        report_data = {"suites": [], "stats": {"expected": 1, "unexpected": 1}}
        report_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(report_zip_buffer, "w") as zf:
            zf.writestr("report.json", json.dumps(report_data))
        report_zip = report_zip_buffer.getvalue()

        with patch("heisenberg.playground.freeze.GitHubArtifactClient") as mock_client:
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
                report_zip,
                b"trace-zip-content",
            ]

            config = FreezeConfig(
                repo="owner/repo",
                output_dir=temp_output_dir,
                github_token="test-token",
            )
            freezer = CaseFreezer(config)

            result = await freezer.freeze()

            assert result.trace_path is not None
            assert result.trace_path.exists()


class TestFailureFiltering:
    """Test filtering scenarios based on failure count."""

    @pytest.fixture
    def temp_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def _create_report_zip(self, stats: dict) -> bytes:
        """Helper to create a Playwright report ZIP with given stats."""
        import io
        import zipfile

        report_data = {"suites": [], "stats": stats}
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("report.json", json.dumps(report_data))
        return zip_buffer.getvalue()

    @pytest.mark.asyncio
    async def test_freeze_raises_on_zero_failures(self, temp_output_dir):
        """Should raise error when report has no test failures."""
        # Report with all tests passed (unexpected=0)
        report_zip = self._create_report_zip(
            {"expected": 10, "unexpected": 0, "flaky": 0, "skipped": 0}
        )

        with patch("heisenberg.playground.freeze.GitHubArtifactClient") as mock_client:
            client = AsyncMock()
            mock_client.return_value = client
            client.list_workflow_runs.return_value = [
                MockWorkflowRun(id=12345, conclusion="failure")
            ]
            client.get_artifacts.return_value = [
                MockArtifact(id=1, name="playwright-report", expired=False),
            ]
            client.download_artifact.return_value = report_zip

            config = FreezeConfig(
                repo="owner/repo",
                output_dir=temp_output_dir,
                github_token="test-token",
            )
            freezer = CaseFreezer(config)

            with pytest.raises(ValueError, match="no.*failures"):
                await freezer.freeze()

    @pytest.mark.asyncio
    async def test_freeze_raises_on_all_skipped(self, temp_output_dir):
        """Should raise error when all tests are skipped."""
        # Report with all tests skipped
        report_zip = self._create_report_zip(
            {"expected": 0, "unexpected": 0, "flaky": 0, "skipped": 8}
        )

        with patch("heisenberg.playground.freeze.GitHubArtifactClient") as mock_client:
            client = AsyncMock()
            mock_client.return_value = client
            client.list_workflow_runs.return_value = [
                MockWorkflowRun(id=12345, conclusion="failure")
            ]
            client.get_artifacts.return_value = [
                MockArtifact(id=1, name="playwright-report", expired=False),
            ]
            client.download_artifact.return_value = report_zip

            config = FreezeConfig(
                repo="owner/repo",
                output_dir=temp_output_dir,
                github_token="test-token",
            )
            freezer = CaseFreezer(config)

            with pytest.raises(ValueError, match="no.*failures"):
                await freezer.freeze()

    @pytest.mark.asyncio
    async def test_freeze_raises_on_visual_only_report(self, temp_output_dir):
        """Should raise error when report is visual-only (not analyzable)."""
        import io
        import zipfile

        # Create HTML report structure (visual_only)
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("index.html", "<html>Report</html>")
            zf.writestr("data/abc123.zip", b"binary blob data")
        html_report_zip = zip_buffer.getvalue()

        with patch("heisenberg.playground.freeze.GitHubArtifactClient") as mock_client:
            client = AsyncMock()
            mock_client.return_value = client
            client.list_workflow_runs.return_value = [
                MockWorkflowRun(id=12345, conclusion="failure")
            ]
            client.get_artifacts.return_value = [
                MockArtifact(id=1, name="playwright-report", expired=False),
            ]
            client.download_artifact.return_value = html_report_zip

            config = FreezeConfig(
                repo="owner/repo",
                output_dir=temp_output_dir,
                github_token="test-token",
            )
            freezer = CaseFreezer(config)

            with pytest.raises(ValueError, match="visual.only|not analyzable"):
                await freezer.freeze()

    @pytest.mark.asyncio
    async def test_freeze_accepts_report_with_failures(self, temp_output_dir):
        """Should accept report with actual test failures."""
        # Report with failures (unexpected > 0)
        report_zip = self._create_report_zip(
            {"expected": 8, "unexpected": 2, "flaky": 0, "skipped": 0}
        )

        with patch("heisenberg.playground.freeze.GitHubArtifactClient") as mock_client:
            client = AsyncMock()
            mock_client.return_value = client
            client.list_workflow_runs.return_value = [
                MockWorkflowRun(id=12345, conclusion="failure")
            ]
            client.get_artifacts.return_value = [
                MockArtifact(id=1, name="playwright-report", expired=False),
            ]
            client.download_artifact.return_value = report_zip

            config = FreezeConfig(
                repo="owner/repo",
                output_dir=temp_output_dir,
                github_token="test-token",
            )
            freezer = CaseFreezer(config)

            result = await freezer.freeze()

            # Should succeed and create scenario
            assert result is not None
            assert result.case_dir.exists()

    @pytest.mark.asyncio
    async def test_freeze_cleans_up_on_no_failures(self, temp_output_dir):
        """Should clean up created directory if filtering fails."""
        report_zip = self._create_report_zip(
            {"expected": 10, "unexpected": 0, "flaky": 0, "skipped": 0}
        )

        with patch("heisenberg.playground.freeze.GitHubArtifactClient") as mock_client:
            client = AsyncMock()
            mock_client.return_value = client
            client.list_workflow_runs.return_value = [
                MockWorkflowRun(id=12345, conclusion="failure")
            ]
            client.get_artifacts.return_value = [
                MockArtifact(id=1, name="playwright-report", expired=False),
            ]
            client.download_artifact.return_value = report_zip

            config = FreezeConfig(
                repo="owner/repo",
                output_dir=temp_output_dir,
                github_token="test-token",
            )
            freezer = CaseFreezer(config)

            with pytest.raises(ValueError):
                await freezer.freeze()

            # Directory should be cleaned up
            case_dirs = list(temp_output_dir.iterdir())
            assert len(case_dirs) == 0
