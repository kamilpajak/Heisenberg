"""Tests for GitHub Artifacts client - TDD Red-Green-Refactor.

These tests validate the GitHubArtifactClient which fetches
Playwright reports from GitHub Actions artifacts.
"""

import io
import json
import zipfile
from unittest.mock import AsyncMock, patch

import pytest

# Import will fail until we implement the module
try:
    from heisenberg.github_artifacts import (
        Artifact,
        GitHubAPIError,
        GitHubArtifactClient,
        WorkflowRun,
    )
except ImportError:
    GitHubArtifactClient = None
    WorkflowRun = None
    Artifact = None
    GitHubAPIError = None


pytestmark = pytest.mark.skipif(
    GitHubArtifactClient is None, reason="github_artifacts module not implemented yet"
)


class TestGitHubArtifactClientExists:
    """Verify the GitHubArtifactClient class exists and has correct interface."""

    def test_client_class_exists(self):
        """GitHubArtifactClient class should exist."""
        assert GitHubArtifactClient is not None

    def test_client_requires_token(self):
        """Client should require a token for authentication."""
        with pytest.raises(TypeError):
            GitHubArtifactClient()  # No token provided

    def test_client_accepts_token(self):
        """Client should accept a token parameter."""
        client = GitHubArtifactClient(token="test-token")
        assert client is not None

    def test_client_has_list_workflow_runs_method(self):
        """Client should have list_workflow_runs method."""
        client = GitHubArtifactClient(token="test-token")
        assert hasattr(client, "list_workflow_runs")
        assert callable(client.list_workflow_runs)

    def test_client_has_get_artifacts_method(self):
        """Client should have get_artifacts method."""
        client = GitHubArtifactClient(token="test-token")
        assert hasattr(client, "get_artifacts")
        assert callable(client.get_artifacts)

    def test_client_has_download_artifact_method(self):
        """Client should have download_artifact method."""
        client = GitHubArtifactClient(token="test-token")
        assert hasattr(client, "download_artifact")
        assert callable(client.download_artifact)

    def test_client_has_extract_playwright_report_method(self):
        """Client should have extract_playwright_report method."""
        client = GitHubArtifactClient(token="test-token")
        assert hasattr(client, "extract_playwright_report")
        assert callable(client.extract_playwright_report)


class TestWorkflowRunDataclass:
    """Test WorkflowRun dataclass."""

    def test_workflow_run_exists(self):
        """WorkflowRun dataclass should exist."""
        assert WorkflowRun is not None

    def test_workflow_run_has_required_fields(self):
        """WorkflowRun should have id, status, conclusion, created_at, html_url."""
        run = WorkflowRun(
            id=12345,
            name="E2E Tests",
            status="completed",
            conclusion="failure",
            created_at="2024-01-20T10:00:00Z",
            html_url="https://github.com/owner/repo/actions/runs/12345",
        )
        assert run.id == 12345
        assert run.name == "E2E Tests"
        assert run.status == "completed"
        assert run.conclusion == "failure"
        assert run.created_at == "2024-01-20T10:00:00Z"
        assert "github.com" in run.html_url


class TestArtifactDataclass:
    """Test Artifact dataclass."""

    def test_artifact_exists(self):
        """Artifact dataclass should exist."""
        assert Artifact is not None

    def test_artifact_has_required_fields(self):
        """Artifact should have id, name, size_in_bytes, expired."""
        artifact = Artifact(
            id=67890,
            name="playwright-report",
            size_in_bytes=1024000,
            expired=False,
            archive_download_url="https://api.github.com/...",
        )
        assert artifact.id == 67890
        assert artifact.name == "playwright-report"
        assert artifact.size_in_bytes == 1024000
        assert artifact.expired is False


class TestListWorkflowRuns:
    """Test list_workflow_runs method."""

    @pytest.fixture
    def mock_response_data(self):
        """Sample API response for workflow runs."""
        return {
            "total_count": 2,
            "workflow_runs": [
                {
                    "id": 12345,
                    "name": "E2E Tests",
                    "status": "completed",
                    "conclusion": "failure",
                    "created_at": "2024-01-20T10:00:00Z",
                    "html_url": "https://github.com/owner/repo/actions/runs/12345",
                },
                {
                    "id": 12344,
                    "name": "E2E Tests",
                    "status": "completed",
                    "conclusion": "success",
                    "created_at": "2024-01-19T10:00:00Z",
                    "html_url": "https://github.com/owner/repo/actions/runs/12344",
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_list_workflow_runs_returns_list(self, mock_response_data):
        """list_workflow_runs should return a list of WorkflowRun objects."""
        client = GitHubArtifactClient(token="test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response_data

            runs = await client.list_workflow_runs("owner", "repo")

            assert isinstance(runs, list)
            assert len(runs) == 2
            assert all(isinstance(r, WorkflowRun) for r in runs)

    @pytest.mark.asyncio
    async def test_list_workflow_runs_filters_by_status(self, mock_response_data):
        """list_workflow_runs should filter by status when provided."""
        client = GitHubArtifactClient(token="test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response_data

            await client.list_workflow_runs("owner", "repo", status="failure")

            # Verify the request included status parameter
            call_args = mock_request.call_args
            assert (
                "status=failure" in str(call_args)
                or call_args[1].get("params", {}).get("status") == "failure"
            )


class TestGetArtifacts:
    """Test get_artifacts method."""

    @pytest.fixture
    def mock_artifacts_response(self):
        """Sample API response for artifacts."""
        return {
            "total_count": 2,
            "artifacts": [
                {
                    "id": 67890,
                    "name": "playwright-report",
                    "size_in_bytes": 1024000,
                    "expired": False,
                    "archive_download_url": "https://api.github.com/repos/owner/repo/actions/artifacts/67890/zip",
                },
                {
                    "id": 67891,
                    "name": "test-results",
                    "size_in_bytes": 512000,
                    "expired": False,
                    "archive_download_url": "https://api.github.com/repos/owner/repo/actions/artifacts/67891/zip",
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_get_artifacts_returns_list(self, mock_artifacts_response):
        """get_artifacts should return a list of Artifact objects."""
        client = GitHubArtifactClient(token="test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_artifacts_response

            artifacts = await client.get_artifacts("owner", "repo", run_id=12345)

            assert isinstance(artifacts, list)
            assert len(artifacts) == 2
            assert all(isinstance(a, Artifact) for a in artifacts)

    @pytest.mark.asyncio
    async def test_get_artifacts_filters_expired(self, mock_artifacts_response):
        """get_artifacts should be able to filter out expired artifacts."""
        mock_artifacts_response["artifacts"][0]["expired"] = True
        client = GitHubArtifactClient(token="test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_artifacts_response

            artifacts = await client.get_artifacts(
                "owner", "repo", run_id=12345, include_expired=False
            )

            assert len(artifacts) == 1
            assert artifacts[0].name == "test-results"


class TestDownloadArtifact:
    """Test download_artifact method."""

    @pytest.mark.asyncio
    async def test_download_artifact_returns_bytes(self):
        """download_artifact should return artifact content as bytes."""
        client = GitHubArtifactClient(token="test-token")

        # Create a mock zip file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("report.json", '{"test": "data"}')
        zip_content = zip_buffer.getvalue()

        with patch.object(client, "_download", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = zip_content

            result = await client.download_artifact("owner", "repo", artifact_id=67890)

            assert isinstance(result, bytes)
            assert len(result) > 0


class TestExtractPlaywrightReport:
    """Test extract_playwright_report method."""

    def test_extracts_json_from_zip(self):
        """extract_playwright_report should extract JSON from zip file."""
        client = GitHubArtifactClient(token="test-token")

        # Create a mock zip with a Playwright report
        report_data = {"suites": [], "stats": {"expected": 0, "unexpected": 0}}
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("playwright-report/results.json", json.dumps(report_data))
        zip_content = zip_buffer.getvalue()

        result = client.extract_playwright_report(zip_content)

        assert result is not None
        assert "suites" in result
        assert "stats" in result

    def test_finds_json_in_nested_directory(self):
        """Should find JSON report even in nested directories."""
        client = GitHubArtifactClient(token="test-token")

        report_data = {"suites": [], "stats": {"expected": 1, "unexpected": 0}}
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("artifacts/test-results/report.json", json.dumps(report_data))
        zip_content = zip_buffer.getvalue()

        result = client.extract_playwright_report(zip_content)

        assert result is not None
        assert result["stats"]["expected"] == 1

    def test_returns_none_for_no_json(self):
        """Should return None if no JSON file found in zip."""
        client = GitHubArtifactClient(token="test-token")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("readme.txt", "No JSON here")
        zip_content = zip_buffer.getvalue()

        result = client.extract_playwright_report(zip_content)

        assert result is None

    def test_handles_multiple_json_files(self):
        """Should prefer files with 'report' or 'results' in name."""
        client = GitHubArtifactClient(token="test-token")

        report_data = {"suites": [], "stats": {"expected": 5, "unexpected": 2}}
        other_data = {"not": "a report"}

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("config.json", json.dumps(other_data))
            zf.writestr("test-results.json", json.dumps(report_data))
        zip_content = zip_buffer.getvalue()

        result = client.extract_playwright_report(zip_content)

        assert result is not None
        assert result["stats"]["unexpected"] == 2


class TestGitHubAPIErrors:
    """Test error handling for GitHub API."""

    def test_github_api_error_exists(self):
        """GitHubAPIError exception should exist."""
        assert GitHubAPIError is not None

    @pytest.mark.asyncio
    async def test_handles_rate_limit_error(self):
        """Should raise appropriate error on rate limit (403)."""
        client = GitHubArtifactClient(token="test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = GitHubAPIError("Rate limit exceeded", status_code=403)

            with pytest.raises(GitHubAPIError) as exc_info:
                await client.list_workflow_runs("owner", "repo")

            assert exc_info.value.status_code == 403
            assert "rate limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_handles_not_found_error(self):
        """Should raise appropriate error when repo not found (404)."""
        client = GitHubArtifactClient(token="test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = GitHubAPIError("Not found", status_code=404)

            with pytest.raises(GitHubAPIError) as exc_info:
                await client.list_workflow_runs("owner", "nonexistent")

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_handles_unauthorized_error(self):
        """Should raise appropriate error on invalid token (401)."""
        client = GitHubArtifactClient(token="invalid-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = GitHubAPIError("Unauthorized", status_code=401)

            with pytest.raises(GitHubAPIError) as exc_info:
                await client.list_workflow_runs("owner", "repo")

            assert exc_info.value.status_code == 401


class TestFetchAndAnalyzeIntegration:
    """Test the full fetch-and-analyze workflow."""

    @pytest.mark.asyncio
    async def test_fetch_report_from_failed_run(self):
        """Should be able to fetch report from a failed workflow run."""
        client = GitHubArtifactClient(token="test-token")

        # Mock the full workflow
        mock_runs = [
            WorkflowRun(
                id=12345,
                name="E2E Tests",
                status="completed",
                conclusion="failure",
                created_at="2024-01-20T10:00:00Z",
                html_url="https://github.com/owner/repo/actions/runs/12345",
            )
        ]
        mock_artifacts = [
            Artifact(
                id=67890,
                name="playwright-report",
                size_in_bytes=1024,
                expired=False,
                archive_download_url="https://api.github.com/...",
            )
        ]

        report_data = {
            "suites": [],
            "stats": {"expected": 5, "unexpected": 2, "flaky": 0, "skipped": 0},
        }
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("results.json", json.dumps(report_data))
        zip_content = zip_buffer.getvalue()

        with patch.object(client, "list_workflow_runs", new_callable=AsyncMock) as mock_list:
            with patch.object(client, "get_artifacts", new_callable=AsyncMock) as mock_get:
                with patch.object(
                    client, "download_artifact", new_callable=AsyncMock
                ) as mock_download:
                    mock_list.return_value = mock_runs
                    mock_get.return_value = mock_artifacts
                    mock_download.return_value = zip_content

                    # Fetch report
                    runs = await client.list_workflow_runs("owner", "repo", status="failure")
                    assert len(runs) == 1

                    artifacts = await client.get_artifacts("owner", "repo", run_id=runs[0].id)
                    assert len(artifacts) == 1

                    zip_data = await client.download_artifact(
                        "owner", "repo", artifact_id=artifacts[0].id
                    )
                    report = client.extract_playwright_report(zip_data)

                    assert report is not None
                    assert report["stats"]["unexpected"] == 2
