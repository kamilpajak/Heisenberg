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
    from heisenberg.integrations.github_artifacts import (
        Artifact,
        GitHubAPIError,
        GitHubArtifactClient,
        Job,
        WorkflowRun,
    )
except ImportError:
    GitHubArtifactClient = None
    WorkflowRun = None
    Artifact = None
    GitHubAPIError = None
    Job = None


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
        assert not artifact.expired


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


class TestJobDataclass:
    """Test Job dataclass."""

    def test_job_exists(self):
        """Job dataclass should exist."""
        assert Job is not None

    def test_job_has_required_fields(self):
        """Job should have id, name, status, conclusion."""
        job = Job(
            id=123456,
            name="e2e-web (ubuntu-latest)",
            status="completed",
            conclusion="failure",
        )
        assert job.id == 123456
        assert job.name == "e2e-web (ubuntu-latest)"
        assert job.status == "completed"
        assert job.conclusion == "failure"

    def test_job_conclusion_can_be_none(self):
        """Job conclusion should be None for in-progress jobs."""
        job = Job(
            id=123456,
            name="e2e-web",
            status="in_progress",
            conclusion=None,
        )
        assert job.conclusion is None


class TestGetJobs:
    """Test get_jobs method."""

    @pytest.fixture
    def mock_jobs_response(self):
        """Sample API response for workflow run jobs."""
        return {
            "total_count": 3,
            "jobs": [
                {
                    "id": 111,
                    "name": "e2e-web (ubuntu-latest)",
                    "status": "completed",
                    "conclusion": "failure",
                },
                {
                    "id": 222,
                    "name": "e2e-desktop (ubuntu-latest) [1/4]",
                    "status": "completed",
                    "conclusion": "success",
                },
                {
                    "id": 333,
                    "name": "npm audit (ubuntu-latest)",
                    "status": "completed",
                    "conclusion": "failure",
                },
            ],
        }

    def test_client_has_get_jobs_method(self):
        """Client should have get_jobs method."""
        client = GitHubArtifactClient(token="test-token")
        assert hasattr(client, "get_jobs")
        assert callable(client.get_jobs)

    @pytest.mark.asyncio
    async def test_get_jobs_returns_list(self, mock_jobs_response):
        """get_jobs should return a list of Job objects."""
        client = GitHubArtifactClient(token="test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_jobs_response

            jobs = await client.get_jobs("owner", "repo", run_id=12345)

            assert isinstance(jobs, list)
            assert len(jobs) == 3
            assert all(isinstance(j, Job) for j in jobs)

    @pytest.mark.asyncio
    async def test_get_jobs_parses_job_fields(self, mock_jobs_response):
        """get_jobs should correctly parse job fields."""
        client = GitHubArtifactClient(token="test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_jobs_response

            jobs = await client.get_jobs("owner", "repo", run_id=12345)

            # Check first job (failed e2e-web)
            assert jobs[0].id == 111
            assert jobs[0].name == "e2e-web (ubuntu-latest)"
            assert jobs[0].status == "completed"
            assert jobs[0].conclusion == "failure"

    @pytest.mark.asyncio
    async def test_get_jobs_calls_correct_endpoint(self, mock_jobs_response):
        """get_jobs should call the correct GitHub API endpoint."""
        client = GitHubArtifactClient(token="test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_jobs_response

            await client.get_jobs("owner", "repo", run_id=12345)

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "GET"
            assert "/repos/owner/repo/actions/runs/12345/jobs" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_jobs_handles_empty_response(self):
        """get_jobs should return empty list when no jobs found."""
        client = GitHubArtifactClient(token="test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"total_count": 0, "jobs": []}

            jobs = await client.get_jobs("owner", "repo", run_id=12345)

            assert jobs == []

    @pytest.mark.asyncio
    async def test_get_jobs_handles_api_error(self):
        """get_jobs should propagate API errors."""
        client = GitHubArtifactClient(token="test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = GitHubAPIError("Not found", status_code=404)

            with pytest.raises(GitHubAPIError) as exc_info:
                await client.get_jobs("owner", "repo", run_id=99999)

            assert exc_info.value.status_code == 404


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


class TestBlobReportExtraction:
    """Test extraction of blob reports (nested ZIP files from sharded Playwright runs).

    Blob reports are used by Playwright when running tests in shards. The structure is:
    artifact.zip
    └── report-shard-1.zip
        └── report.json
    """

    def _create_nested_zip(self, inner_filename: str, report_data: dict) -> bytes:
        """Helper to create a nested ZIP structure (blob report format)."""
        # Create inner ZIP with report
        inner_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(inner_zip_buffer, "w") as inner_zf:
            inner_zf.writestr("report.json", json.dumps(report_data))
        inner_zip_content = inner_zip_buffer.getvalue()

        # Create outer ZIP containing the inner ZIP
        outer_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(outer_zip_buffer, "w") as outer_zf:
            outer_zf.writestr(inner_filename, inner_zip_content)

        return outer_zip_buffer.getvalue()

    def test_extracts_report_from_nested_zip(self):
        """Should extract Playwright report from nested ZIP (blob report)."""
        client = GitHubArtifactClient(token="test-token")

        report_data = {
            "suites": [{"title": "test suite"}],
            "stats": {"expected": 10, "unexpected": 2, "flaky": 1, "skipped": 0},
        }

        nested_zip = self._create_nested_zip("report-chromium-shard-1.zip", report_data)

        result = client.extract_playwright_report(nested_zip)

        assert result is not None
        assert "suites" in result
        assert result["stats"]["unexpected"] == 2

    def test_extracts_report_from_deeply_nested_zip(self):
        """Should handle multiple levels of nesting if needed."""
        client = GitHubArtifactClient(token="test-token")

        report_data = {
            "suites": [],
            "stats": {"expected": 5, "unexpected": 0, "flaky": 0, "skipped": 1},
        }

        # Create double-nested ZIP
        inner_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(inner_zip_buffer, "w") as zf:
            zf.writestr("results.json", json.dumps(report_data))
        inner_zip = inner_zip_buffer.getvalue()

        middle_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(middle_zip_buffer, "w") as zf:
            zf.writestr("shard-report.zip", inner_zip)
        middle_zip = middle_zip_buffer.getvalue()

        outer_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(outer_zip_buffer, "w") as zf:
            zf.writestr("blob-report.zip", middle_zip)
        outer_zip = outer_zip_buffer.getvalue()

        result = client.extract_playwright_report(outer_zip)

        assert result is not None
        assert result["stats"]["skipped"] == 1

    def test_prefers_json_over_nested_zip_when_both_present(self):
        """When both JSON and nested ZIP exist, should prefer direct JSON."""
        client = GitHubArtifactClient(token="test-token")

        direct_report = {
            "suites": [],
            "stats": {"expected": 100, "unexpected": 0, "flaky": 0, "skipped": 0},
        }
        nested_report = {
            "suites": [],
            "stats": {"expected": 50, "unexpected": 5, "flaky": 0, "skipped": 0},
        }

        # Create inner ZIP
        inner_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(inner_zip_buffer, "w") as zf:
            zf.writestr("report.json", json.dumps(nested_report))
        inner_zip = inner_zip_buffer.getvalue()

        # Create outer ZIP with both direct JSON and nested ZIP
        outer_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(outer_zip_buffer, "w") as zf:
            zf.writestr("test-results.json", json.dumps(direct_report))
            zf.writestr("blob-report.zip", inner_zip)
        outer_zip = outer_zip_buffer.getvalue()

        result = client.extract_playwright_report(outer_zip)

        assert result is not None
        # Should get the direct JSON (100 expected), not nested (50 expected)
        assert result["stats"]["expected"] == 100

    def test_handles_multiple_nested_zips(self):
        """Should handle artifact with multiple shard ZIPs (picks first valid one)."""
        client = GitHubArtifactClient(token="test-token")

        report1 = {"suites": [], "stats": {"expected": 10, "unexpected": 1}}
        report2 = {"suites": [], "stats": {"expected": 20, "unexpected": 2}}

        # Create two inner ZIPs
        inner1_buffer = io.BytesIO()
        with zipfile.ZipFile(inner1_buffer, "w") as zf:
            zf.writestr("report.json", json.dumps(report1))

        inner2_buffer = io.BytesIO()
        with zipfile.ZipFile(inner2_buffer, "w") as zf:
            zf.writestr("report.json", json.dumps(report2))

        # Create outer ZIP with multiple shard ZIPs
        outer_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(outer_zip_buffer, "w") as zf:
            zf.writestr("report-shard-1.zip", inner1_buffer.getvalue())
            zf.writestr("report-shard-2.zip", inner2_buffer.getvalue())
        outer_zip = outer_zip_buffer.getvalue()

        result = client.extract_playwright_report(outer_zip)

        assert result is not None
        assert "stats" in result
        # Should get one of the reports (implementation may vary on which)
        assert result["stats"]["unexpected"] in [1, 2]

    def test_returns_none_when_nested_zip_has_no_report(self):
        """Should return None if nested ZIP doesn't contain a Playwright report."""
        client = GitHubArtifactClient(token="test-token")

        # Create inner ZIP without valid report
        inner_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(inner_zip_buffer, "w") as zf:
            zf.writestr("config.json", '{"not": "a report"}')
        inner_zip = inner_zip_buffer.getvalue()

        outer_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(outer_zip_buffer, "w") as zf:
            zf.writestr("blob-report.zip", inner_zip)
        outer_zip = outer_zip_buffer.getvalue()

        result = client.extract_playwright_report(outer_zip)

        assert result is None

    def test_handles_corrupted_nested_zip(self):
        """Should gracefully handle corrupted nested ZIP files."""
        client = GitHubArtifactClient(token="test-token")

        outer_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(outer_zip_buffer, "w") as zf:
            zf.writestr("corrupted.zip", b"not a valid zip file content")
        outer_zip = outer_zip_buffer.getvalue()

        # Should not raise, just return None
        result = client.extract_playwright_report(outer_zip)

        assert result is None

    def test_blob_report_naming_patterns(self):
        """Should recognize common blob report naming patterns."""
        client = GitHubArtifactClient(token="test-token")

        report_data = {"suites": [], "stats": {"expected": 1, "unexpected": 0}}

        # Test various naming patterns used by Playwright blob reports
        patterns = [
            "report-chromium-ubuntu-22.04-node20-0.zip",
            "blob-report-firefox.zip",
            "shard-1-of-4.zip",
            "test-results-webkit.zip",
        ]

        for pattern in patterns:
            nested_zip = self._create_nested_zip(pattern, report_data)
            result = client.extract_playwright_report(nested_zip)

            assert result is not None, f"Failed to extract from pattern: {pattern}"
            assert "suites" in result

    def test_respects_max_depth_limit(self):
        """Should stop recursion when max_depth is reached."""
        client = GitHubArtifactClient(token="test-token")

        report_data = {"suites": [], "stats": {"expected": 1, "unexpected": 0}}

        # Create triple-nested ZIP (depth 3)
        level3 = io.BytesIO()
        with zipfile.ZipFile(level3, "w") as zf:
            zf.writestr("report.json", json.dumps(report_data))

        level2 = io.BytesIO()
        with zipfile.ZipFile(level2, "w") as zf:
            zf.writestr("inner.zip", level3.getvalue())

        level1 = io.BytesIO()
        with zipfile.ZipFile(level1, "w") as zf:
            zf.writestr("outer.zip", level2.getvalue())

        outer_zip = level1.getvalue()

        # With max_depth=3 (default), should find it
        result = client.extract_playwright_report(outer_zip, max_depth=3)
        assert result is not None

        # With max_depth=2, should NOT find it (too shallow)
        result = client.extract_playwright_report(outer_zip, max_depth=2)
        assert result is None

    def test_empty_nested_zip(self):
        """Should handle empty nested ZIP files gracefully."""
        client = GitHubArtifactClient(token="test-token")

        # Create empty inner ZIP
        inner_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(inner_zip_buffer, "w"):
            pass  # Empty ZIP

        outer_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(outer_zip_buffer, "w") as zf:
            zf.writestr("empty.zip", inner_zip_buffer.getvalue())

        result = client.extract_playwright_report(outer_zip_buffer.getvalue())

        assert result is None


class TestJsonlReportExtraction:
    """Test extraction of JSONL format reports (Playwright blob report format).

    Playwright blob reports use JSONL (JSON Lines) format where each line
    is a separate JSON object containing different parts of the report.
    """

    def _create_jsonl_content(self, objects: list[dict]) -> str:
        """Create JSONL content from list of objects."""
        return "\n".join(json.dumps(obj) for obj in objects)

    def test_extracts_report_from_jsonl_file(self):
        """Should extract Playwright report from JSONL file in nested ZIP."""
        client = GitHubArtifactClient(token="test-token")

        # JSONL format: multiple JSON objects, one per line
        # First object typically contains metadata, subsequent contain test results
        jsonl_objects = [
            {"metadata": {"version": 1}},
            {"suites": [{"title": "test"}], "stats": {"expected": 5, "unexpected": 1}},
        ]

        inner_zip = io.BytesIO()
        with zipfile.ZipFile(inner_zip, "w") as zf:
            zf.writestr("report.jsonl", self._create_jsonl_content(jsonl_objects))

        outer_zip = io.BytesIO()
        with zipfile.ZipFile(outer_zip, "w") as zf:
            zf.writestr("blob-report.zip", inner_zip.getvalue())

        result = client.extract_playwright_report(outer_zip.getvalue())

        assert result is not None
        assert "suites" in result or "stats" in result

    def test_finds_jsonl_in_flat_zip(self):
        """Should find JSONL file even in flat ZIP structure."""
        client = GitHubArtifactClient(token="test-token")

        jsonl_objects = [
            {"stats": {"expected": 10, "unexpected": 2, "flaky": 0, "skipped": 1}},
        ]

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("test-results.jsonl", self._create_jsonl_content(jsonl_objects))

        result = client.extract_playwright_report(zip_buffer.getvalue())

        assert result is not None
        assert result["stats"]["unexpected"] == 2

    def test_prefers_json_over_jsonl(self):
        """Should prefer .json over .jsonl when both exist."""
        client = GitHubArtifactClient(token="test-token")

        json_report = {"suites": [], "stats": {"expected": 100, "unexpected": 0}}
        jsonl_report = [{"stats": {"expected": 50, "unexpected": 5}}]

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("report.json", json.dumps(json_report))
            zf.writestr("report.jsonl", self._create_jsonl_content(jsonl_report))

        result = client.extract_playwright_report(zip_buffer.getvalue())

        assert result is not None
        # Should get JSON (100 expected), not JSONL (50 expected)
        assert result["stats"]["expected"] == 100

    def test_handles_empty_jsonl(self):
        """Should handle empty JSONL file gracefully."""
        client = GitHubArtifactClient(token="test-token")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("report.jsonl", "")

        result = client.extract_playwright_report(zip_buffer.getvalue())

        assert result is None

    def test_handles_jsonl_with_only_metadata(self):
        """Should return None if JSONL only contains metadata, no report data."""
        client = GitHubArtifactClient(token="test-token")

        jsonl_objects = [
            {"metadata": {"version": 1}},
            {"config": {"timeout": 30000}},
        ]

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("report.jsonl", self._create_jsonl_content(jsonl_objects))

        result = client.extract_playwright_report(zip_buffer.getvalue())

        assert result is None


class TestHtmlReportDetection:
    """Test detection of HTML reports (unsupported format).

    Playwright HTML reports contain:
    - index.html (bundled web app)
    - data/*.zip (trace files)
    - data/*.md (accessibility snapshots)

    These cannot be parsed - we need JSON reporter output.
    """

    def _create_html_report_zip(self, extra_files: dict[str, bytes] | None = None) -> bytes:
        """Create a ZIP that mimics Playwright HTML report structure."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            # Minimal HTML report structure
            zf.writestr("index.html", "<html><body>Playwright Report</body></html>")
            zf.writestr("data/trace-abc123.zip", b"fake trace data")
            zf.writestr("data/snapshot.md", "# Page snapshot\n```yaml\n- button\n```")
            if extra_files:
                for name, content in extra_files.items():
                    zf.writestr(name, content)
        return zip_buffer.getvalue()

    def test_detects_html_report_and_raises_specific_error(self):
        """Should raise HtmlReportNotSupported when HTML report detected."""
        from heisenberg.integrations.github_artifacts import HtmlReportNotSupported

        client = GitHubArtifactClient(token="test-token")
        html_zip = self._create_html_report_zip()

        with pytest.raises(HtmlReportNotSupported) as exc_info:
            client.extract_playwright_report(html_zip)

        assert "HTML report" in str(exc_info.value)
        assert "JSON reporter" in str(exc_info.value)

    def test_html_report_error_includes_fix_suggestion(self):
        """Error message should include how to fix the issue."""
        from heisenberg.integrations.github_artifacts import HtmlReportNotSupported

        client = GitHubArtifactClient(token="test-token")
        html_zip = self._create_html_report_zip()

        with pytest.raises(HtmlReportNotSupported) as exc_info:
            client.extract_playwright_report(html_zip)

        error_msg = str(exc_info.value)
        # Should suggest using JSON reporter
        assert "reporter" in error_msg.lower()

    def test_html_report_not_confused_with_json_report(self):
        """ZIP with both index.html AND valid JSON should return JSON (not error)."""
        client = GitHubArtifactClient(token="test-token")

        # HTML report structure BUT also has valid JSON
        report_data = {"suites": [], "stats": {"expected": 5, "unexpected": 1}}
        html_zip = self._create_html_report_zip(
            extra_files={"report.json": json.dumps(report_data).encode()}
        )

        # Should NOT raise - JSON takes precedence
        result = client.extract_playwright_report(html_zip)

        assert result is not None
        assert result["stats"]["unexpected"] == 1

    def test_plain_html_file_without_data_dir_returns_none(self):
        """ZIP with only HTML file (no data/ dir) should return None, not error."""
        client = GitHubArtifactClient(token="test-token")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("index.html", "<html>not a playwright report</html>")

        # Should return None (not a Playwright report at all)
        result = client.extract_playwright_report(zip_buffer.getvalue())
        assert result is None

    def test_html_report_detection_checks_data_directory(self):
        """HTML report detection requires index.html + data/ directory pattern."""
        from heisenberg.integrations.github_artifacts import HtmlReportNotSupported

        client = GitHubArtifactClient(token="test-token")

        # Has index.html + data/ with zip files = HTML report pattern
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("index.html", "<html>Playwright</html>")
            zf.writestr("data/trace.zip", b"trace data")

        with pytest.raises(HtmlReportNotSupported):
            client.extract_playwright_report(zip_buffer.getvalue())
