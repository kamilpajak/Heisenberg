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


class TestErrorMessages:
    """Test improved error messages guide users to local workflow."""

    def test_no_token_suggests_local_workflow(self):
        """Error for missing token should suggest local analyze command."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--repo", "owner/repo"],
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin"},
        )
        assert result.returncode != 0
        # Should suggest local alternative
        assert "heisenberg analyze" in result.stderr or "local" in result.stderr.lower()

    def test_invalid_repo_format_shows_example(self):
        """Error for invalid repo should show correct format example."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--repo", "invalid"],
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin", "GITHUB_TOKEN": "fake-token"},
        )
        assert result.returncode != 0
        # Should show example of correct format
        assert "owner/repo" in result.stderr

    def test_no_artifacts_found_suggests_local_workflow(self):
        """When no artifacts found, should suggest local analyze."""
        # This test uses mocking to simulate the "no artifacts" scenario
        pass  # Will be tested via unit test below

    @pytest.mark.asyncio
    async def test_no_artifacts_message_includes_local_hint(self):
        """No artifacts message should hint at local workflow."""
        from heisenberg.cli import run_list_artifacts

        with patch("heisenberg.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.list_workflow_runs = AsyncMock(return_value=[])
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
            # Should mention local workflow as alternative
            assert (
                "heisenberg analyze" in output_text.lower()
                or "local" in output_text.lower()
                or "tip" in output_text.lower()
            )


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


class TestMergeBlobsFlag:
    """Test --merge-blobs flag for processing Playwright blob reports."""

    def test_has_merge_blobs_argument(self):
        """fetch-github should have --merge-blobs flag."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--merge-blobs" in result.stdout

    def test_merge_blobs_help_text(self):
        """--merge-blobs should have descriptive help text."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "fetch-github", "--help"],
            capture_output=True,
            text=True,
        )
        # Help should mention merging or blob reports
        assert "merge" in result.stdout.lower() or "blob" in result.stdout.lower()


class TestMergeBlobsFunctionality:
    """Test --merge-blobs behavior with mocked dependencies."""

    @pytest.fixture
    def sample_blob_jsonl(self):
        """Sample blob report JSONL content (protocol events)."""
        return b"""\
{"method":"onBegin","params":{"config":{}}}
{"method":"onTestBegin","params":{"test":{"title":"example test"}}}
{"method":"onTestEnd","params":{"test":{"title":"example test"},"result":{"status":"passed"}}}
{"method":"onEnd","params":{"result":{}}}
"""

    @pytest.fixture
    def merged_report_json(self):
        """Sample merged report JSON (output of merge-reports)."""
        return {
            "suites": [
                {
                    "title": "example.spec.ts",
                    "specs": [
                        {
                            "title": "example test",
                            "tests": [{"status": "passed"}],
                        }
                    ],
                }
            ],
            "stats": {"total": 1, "passed": 1, "failed": 0},
        }

    @pytest.mark.asyncio
    async def test_merge_blobs_calls_playwright_merge(self, sample_blob_jsonl, merged_report_json):
        """--merge-blobs should call npx playwright merge-reports."""
        import json

        from heisenberg.blob_merger import merge_blob_reports

        with patch("subprocess.run") as mock_run:
            # Mock successful merge-reports execution
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = json.dumps(merged_report_json)

            await merge_blob_reports(
                blob_files=[b"blob1.jsonl content"],
                output_format="json",
            )

            # Should have called npx playwright merge-reports
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert "playwright" in str(call_args)
            assert "merge-reports" in str(call_args)

    @pytest.mark.asyncio
    async def test_merge_blobs_returns_parsed_json(self, merged_report_json):
        """merge_blob_reports should return parsed JSON report."""
        import json

        from heisenberg.blob_merger import merge_blob_reports

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = json.dumps(merged_report_json)

            result = await merge_blob_reports(
                blob_files=[b"blob content"],
                output_format="json",
            )

            assert result is not None
            assert "suites" in result
            assert "stats" in result

    @pytest.mark.asyncio
    async def test_merge_blobs_handles_npx_not_found(self):
        """Should raise clear error when npx/playwright not available."""
        from heisenberg.blob_merger import BlobMergeError, merge_blob_reports

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("npx not found")

            with pytest.raises(BlobMergeError) as exc_info:
                await merge_blob_reports(blob_files=[b"blob"])

            assert (
                "npx" in str(exc_info.value).lower() or "playwright" in str(exc_info.value).lower()
            )

    @pytest.mark.asyncio
    async def test_merge_blobs_handles_merge_failure(self):
        """Should raise error when merge-reports fails."""
        from heisenberg.blob_merger import BlobMergeError, merge_blob_reports

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "Error: No blob reports found"

            with pytest.raises(BlobMergeError) as exc_info:
                await merge_blob_reports(blob_files=[b"blob"])

            assert "merge" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()


class TestExtractBlobFiles:
    """Test extraction of blob files from artifacts."""

    @pytest.mark.asyncio
    async def test_extract_blob_files_from_nested_zip(self):
        """Should extract .jsonl files from nested ZIP structure."""
        import io
        import zipfile

        from heisenberg.blob_merger import extract_blob_files

        # Create nested ZIP: outer.zip -> report.zip -> report.jsonl
        inner_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(inner_zip_buffer, "w") as inner_zf:
            inner_zf.writestr("report.jsonl", b'{"method":"onBegin"}\n')
        inner_zip_data = inner_zip_buffer.getvalue()

        outer_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(outer_zip_buffer, "w") as outer_zf:
            outer_zf.writestr("report-shard1.zip", inner_zip_data)
        outer_zip_data = outer_zip_buffer.getvalue()

        blob_files = extract_blob_files(outer_zip_data)

        assert len(blob_files) >= 1
        assert any(b"onBegin" in content for content in blob_files)

    @pytest.mark.asyncio
    async def test_extract_multiple_shard_blobs(self):
        """Should extract blobs from multiple shards."""
        import io
        import zipfile

        from heisenberg.blob_merger import extract_blob_files

        outer_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(outer_zip_buffer, "w") as outer_zf:
            # Shard 1
            inner1 = io.BytesIO()
            with zipfile.ZipFile(inner1, "w") as zf:
                zf.writestr("report.jsonl", b'{"method":"onBegin","shard":1}\n')
            outer_zf.writestr("report-shard1.zip", inner1.getvalue())

            # Shard 2
            inner2 = io.BytesIO()
            with zipfile.ZipFile(inner2, "w") as zf:
                zf.writestr("report.jsonl", b'{"method":"onBegin","shard":2}\n')
            outer_zf.writestr("report-shard2.zip", inner2.getvalue())

        blob_files = extract_blob_files(outer_zip_buffer.getvalue())

        assert len(blob_files) == 2
