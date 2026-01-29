"""Tests for CLI fetch-github command - TDD Red-Green-Refactor."""

import asyncio
import subprocess
import sys
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from heisenberg.cli.commands import (
    _analyze_report_data,
    convert_to_unified,
)
from heisenberg.cli.commands import (
    run_fetch_github as run_fetch_github_async,
)
from heisenberg.cli.formatters import format_size
from heisenberg.cli.github_fetch import (
    _analyze_traces_from_zip,
    fetch_and_analyze_screenshots,
    fetch_and_analyze_traces,
    fetch_and_merge_blobs,
    fetch_and_process_job_logs,
    fetch_report_from_run,
    list_artifacts,
)


# Sync wrapper for tests
def run_fetch_github(args):
    """Sync wrapper for run_fetch_github."""
    return asyncio.run(run_fetch_github_async(args))


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

    @pytest.mark.asyncio
    async def test_no_artifacts_message_includes_local_hint(self):
        """No artifacts message should hint at local workflow."""
        with patch("heisenberg.integrations.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.list_workflow_runs = AsyncMock(return_value=[])
            client_instance.get_artifacts = AsyncMock(return_value=[])

            output = StringIO()
            await list_artifacts(
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
        from heisenberg.integrations.github_artifacts import Artifact

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
        from heisenberg.integrations.github_artifacts import WorkflowRun

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
        with patch("heisenberg.integrations.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.list_workflow_runs = AsyncMock(return_value=mock_runs)
            client_instance.get_artifacts = AsyncMock(return_value=mock_artifacts)

            output = StringIO()
            await list_artifacts(
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
        with patch("heisenberg.integrations.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.list_workflow_runs = AsyncMock(return_value=mock_runs)
            client_instance.get_artifacts = AsyncMock(return_value=mock_artifacts)

            output = StringIO()
            await list_artifacts(
                token="test-token",
                owner="owner",
                repo="repo",
                run_id=None,
                output=output,
            )

            output_text = output.getvalue()
            # Assert exact formatted sizes for the mock artifacts
            assert "1000.0 KB" in output_text  # 1024000 bytes
            assert "5.0 MB" in output_text  # 5242880 bytes
            assert "500.0 KB" in output_text  # 512000 bytes

    @pytest.mark.asyncio
    async def test_list_artifacts_shows_expired_status(self, mock_artifacts, mock_runs):
        """--list-artifacts should indicate expired artifacts."""
        with patch("heisenberg.integrations.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.list_workflow_runs = AsyncMock(return_value=mock_runs)
            client_instance.get_artifacts = AsyncMock(return_value=mock_artifacts)

            output = StringIO()
            await list_artifacts(
                token="test-token",
                owner="owner",
                repo="repo",
                run_id=None,
                output=output,
            )

            output_text = output.getvalue()
            # Should indicate expired status with specific marker
            assert "[EXPIRED]" in output_text

    @pytest.mark.asyncio
    async def test_list_artifacts_with_specific_run_id(self, mock_artifacts):
        """--list-artifacts should work with specific --run-id."""
        with patch("heisenberg.integrations.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.get_artifacts = AsyncMock(return_value=mock_artifacts)

            output = StringIO()
            await list_artifacts(
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
        with patch("heisenberg.integrations.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.list_workflow_runs = AsyncMock(return_value=mock_runs)
            client_instance.get_artifacts = AsyncMock(return_value=mock_artifacts)

            output = StringIO()
            result = await list_artifacts(
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
        with patch("heisenberg.integrations.github_artifacts.GitHubArtifactClient") as MockClient:
            client_instance = MockClient.return_value
            client_instance.list_workflow_runs = AsyncMock(return_value=mock_runs)
            client_instance.get_artifacts = AsyncMock(return_value=[])

            output = StringIO()
            await list_artifacts(
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
        from pathlib import Path

        from heisenberg.utils.merging import merge_blob_reports

        # Track calls for assertion
        called_args = []

        # Mock asyncio.create_subprocess_exec to write output file
        async def mock_create_subprocess(*args, **kwargs):
            called_args.append(args)
            cwd = kwargs.get("cwd")
            if cwd:
                output_file = Path(cwd) / "merged-report.json"
                output_file.write_text(json.dumps(merged_report_json))

            class MockProcess:
                returncode = 0

                async def communicate(self):
                    return b"", b""

            return MockProcess()

        with patch(
            "asyncio.create_subprocess_exec", side_effect=mock_create_subprocess
        ) as mock_exec:
            await merge_blob_reports(
                blob_files=[b"blob1.jsonl content"],
                output_format="json",
            )

            # Should have called npx playwright merge-reports
            mock_exec.assert_called_once()
            assert "playwright" in str(called_args)
            assert "merge-reports" in str(called_args)

    @pytest.mark.asyncio
    async def test_merge_blobs_returns_parsed_json(self, merged_report_json):
        """merge_blob_reports should return parsed JSON report."""
        import json
        from pathlib import Path

        from heisenberg.utils.merging import merge_blob_reports

        # Mock asyncio.create_subprocess_exec to write output file
        async def mock_create_subprocess(*args, **kwargs):
            cwd = kwargs.get("cwd")
            if cwd:
                output_file = Path(cwd) / "merged-report.json"
                output_file.write_text(json.dumps(merged_report_json))

            class MockProcess:
                returncode = 0

                async def communicate(self):
                    return b"", b""

            return MockProcess()

        with patch("asyncio.create_subprocess_exec", side_effect=mock_create_subprocess):
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
        from heisenberg.utils.merging import BlobMergeError, merge_blob_reports

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = FileNotFoundError("npx not found")

            with pytest.raises(BlobMergeError) as exc_info:
                await merge_blob_reports(blob_files=[b"blob"])

            assert (
                "npx" in str(exc_info.value).lower() or "playwright" in str(exc_info.value).lower()
            )

    @pytest.mark.asyncio
    async def test_merge_blobs_handles_merge_failure(self):
        """Should raise error when merge-reports fails."""
        from heisenberg.utils.merging import BlobMergeError, merge_blob_reports

        async def mock_create_subprocess(*args, **kwargs):
            class MockProcess:
                returncode = 1

                async def communicate(self):
                    return b"", b"Error: No blob reports found"

            return MockProcess()

        with patch("asyncio.create_subprocess_exec", side_effect=mock_create_subprocess):
            with pytest.raises(BlobMergeError) as exc_info:
                await merge_blob_reports(blob_files=[b"blob"])

            assert "merge" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()


class TestExtractBlobFiles:
    """Test extraction of blob files from artifacts."""

    def test_extract_blob_files_from_nested_zip(self):
        """Should extract .jsonl files from nested ZIP structure."""
        import io
        import zipfile

        from heisenberg.utils.merging import extract_blob_files

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

    def test_extract_multiple_shard_blobs(self):
        """Should extract blobs from multiple shards."""
        import io
        import zipfile

        from heisenberg.utils.merging import extract_blob_files

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


class TestFormatSizeFunction:
    """Tests for format_size function."""

    @pytest.mark.parametrize(
        "size_bytes, expected",
        [
            (0, "0 B"),
            (512, "512 B"),
            (1024, "1.0 KB"),
            (2560, "2.5 KB"),
            (1024 * 1024, "1.0 MB"),
            (5 * 1024 * 1024, "5.0 MB"),
        ],
    )
    def testformat_size(self, size_bytes, expected):
        """Should format size in bytes to human-readable format."""
        assert format_size(size_bytes) == expected


class TestFetchReportFromRun:
    """Tests for fetch_report_from_run function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_matching_artifacts(self):
        """Should return None when no artifacts match."""
        mock_client = MagicMock()
        mock_client.get_artifacts = AsyncMock(return_value=[])

        result = await fetch_report_from_run(mock_client, "owner", "repo", 123, "playwright")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetches_matching_artifact(self):
        """Should fetch and extract matching artifact."""
        mock_artifact = MagicMock()
        mock_artifact.name = "playwright-report"
        mock_artifact.id = 456

        mock_client = MagicMock()
        mock_client.get_artifacts = AsyncMock(return_value=[mock_artifact])
        mock_client.download_artifact = AsyncMock(return_value=b"zip_data")
        mock_client.extract_playwright_report = MagicMock(return_value={"tests": []})

        result = await fetch_report_from_run(mock_client, "owner", "repo", 123, "playwright")

        assert result == {"tests": []}
        mock_client.download_artifact.assert_called_once_with("owner", "repo", 456)


class TestFetchAndProcessJobLogs:
    """Tests for fetch_and_process_job_logs function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_run_id_found(self):
        """Should return None when no failed run found."""
        with patch(
            "heisenberg.integrations.github_artifacts.GitHubArtifactClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.list_workflow_runs = AsyncMock(return_value=[])
            mock_client_cls.return_value = mock_client

            result = await fetch_and_process_job_logs("token", "owner", "repo", None)

            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_fetcher_returns_empty(self):
        """Should return None when no logs found."""
        with patch("heisenberg.integrations.github_logs.GitHubLogsFetcher") as mock_fetcher_cls:
            mock_fetcher = MagicMock()
            mock_fetcher.fetch_logs_for_run.return_value = {}
            mock_fetcher_cls.return_value = mock_fetcher

            result = await fetch_and_process_job_logs("token", "owner", "repo", 123)

            assert result is None

    @pytest.mark.asyncio
    async def test_returns_formatted_snippets(self, capsys):
        """Should return formatted log snippets."""
        with (
            patch("heisenberg.integrations.github_logs.GitHubLogsFetcher") as mock_fetcher_cls,
            patch("heisenberg.parsers.job_logs.JobLogsProcessor") as mock_processor_cls,
        ):
            mock_fetcher = MagicMock()
            mock_fetcher.fetch_logs_for_run.return_value = {"job1": "log content"}
            mock_fetcher_cls.return_value = mock_fetcher

            mock_processor = MagicMock()
            mock_processor.extract_snippets.return_value = ["snippet1", "snippet2"]
            mock_processor.format_for_prompt.return_value = "formatted logs"
            mock_processor_cls.return_value = mock_processor

            result = await fetch_and_process_job_logs("token", "owner", "repo", 123)

            assert result == "formatted logs"
            captured = capsys.readouterr()
            assert "2 relevant log snippet" in captured.err

    @pytest.mark.asyncio
    async def test_returns_none_when_no_snippets_extracted(self, capsys):
        """Should return None when no error snippets found."""
        with (
            patch("heisenberg.integrations.github_logs.GitHubLogsFetcher") as mock_fetcher_cls,
            patch("heisenberg.parsers.job_logs.JobLogsProcessor") as mock_processor_cls,
        ):
            mock_fetcher = MagicMock()
            mock_fetcher.fetch_logs_for_run.return_value = {"job1": "log content"}
            mock_fetcher_cls.return_value = mock_fetcher

            mock_processor = MagicMock()
            mock_processor.extract_snippets.return_value = []
            mock_processor_cls.return_value = mock_processor

            result = await fetch_and_process_job_logs("token", "owner", "repo", 123)

            assert result is None
            captured = capsys.readouterr()
            assert "No error snippets" in captured.err


class TestFetchAndAnalyzeScreenshots:
    """Tests for fetch_and_analyze_screenshots function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_screenshots(self, capsys):
        """Should return None when no screenshots found."""
        with patch(
            "heisenberg.integrations.github_artifacts.GitHubArtifactClient"
        ) as mock_client_cls:
            mock_artifact = MagicMock()
            mock_artifact.name = "playwright-report"
            mock_artifact.id = 1

            mock_client = MagicMock()
            mock_client.list_workflow_runs = AsyncMock(return_value=[])
            mock_client.get_artifacts = AsyncMock(return_value=[mock_artifact])
            mock_client.download_artifact = AsyncMock(return_value=b"zip_data")
            mock_client_cls.return_value = mock_client

            with patch(
                "heisenberg.llm.vision.extract_screenshots_from_artifact",
                return_value=[],
            ):
                result = await fetch_and_analyze_screenshots(
                    "token", "owner", "repo", 123, "playwright"
                )

            assert result is None
            captured = capsys.readouterr()
            assert "No screenshots found" in captured.err

    @pytest.mark.asyncio
    async def test_returns_formatted_analysis(self, capsys):
        """Should return formatted screenshot analysis."""
        with patch(
            "heisenberg.integrations.github_artifacts.GitHubArtifactClient"
        ) as mock_client_cls:
            mock_artifact = MagicMock()
            mock_artifact.name = "playwright-report"
            mock_artifact.id = 1

            mock_client = MagicMock()
            mock_client.get_artifacts = AsyncMock(return_value=[mock_artifact])
            mock_client.download_artifact = AsyncMock(return_value=b"zip_data")
            mock_client_cls.return_value = mock_client

            mock_screenshot = MagicMock()

            with (
                patch(
                    "heisenberg.llm.vision.extract_screenshots_from_artifact",
                    return_value=[mock_screenshot],
                ),
                patch("heisenberg.llm.vision.ScreenshotAnalyzer") as mock_analyzer_cls,
                patch(
                    "heisenberg.llm.vision.format_screenshots_for_prompt",
                    return_value="screenshot analysis",
                ),
            ):
                mock_analyzer = MagicMock()
                mock_analyzer.analyze_batch.return_value = [mock_screenshot]
                mock_analyzer_cls.return_value = mock_analyzer

                result = await fetch_and_analyze_screenshots(
                    "token", "owner", "repo", 123, "playwright"
                )

            assert result == "screenshot analysis"
            captured = capsys.readouterr()
            assert "1 screenshot" in captured.err

    @pytest.mark.asyncio
    async def test_handles_fetch_error(self, capsys):
        """Should handle fetch errors gracefully."""
        with patch(
            "heisenberg.integrations.github_artifacts.GitHubArtifactClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get_artifacts = AsyncMock(side_effect=Exception("API error"))
            mock_client_cls.return_value = mock_client

            result = await fetch_and_analyze_screenshots(
                "token", "owner", "repo", 123, "playwright"
            )

            assert result is None
            captured = capsys.readouterr()
            assert "Failed to fetch screenshots" in captured.err


class TestFetchAndAnalyzeTraces:
    """Tests for fetch_and_analyze_traces function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_traces(self, capsys):
        """Should return None when no traces found."""
        with patch(
            "heisenberg.integrations.github_artifacts.GitHubArtifactClient"
        ) as mock_client_cls:
            mock_artifact = MagicMock()
            mock_artifact.name = "playwright-report"
            mock_artifact.id = 1

            mock_client = MagicMock()
            mock_client.get_artifacts = AsyncMock(return_value=[mock_artifact])
            mock_client.download_artifact = AsyncMock(return_value=b"zip_data")
            mock_client_cls.return_value = mock_client

            with patch("heisenberg.parsers.traces.extract_trace_from_artifact", return_value=[]):
                result = await fetch_and_analyze_traces("token", "owner", "repo", 123, "playwright")

            assert result is None
            captured = capsys.readouterr()
            assert "No trace" in captured.err

    @pytest.mark.asyncio
    async def test_handles_fetch_error(self, capsys):
        """Should handle fetch errors gracefully."""
        with patch(
            "heisenberg.integrations.github_artifacts.GitHubArtifactClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get_artifacts = AsyncMock(side_effect=Exception("API error"))
            mock_client_cls.return_value = mock_client

            result = await fetch_and_analyze_traces("token", "owner", "repo", 123, "playwright")

            assert result is None
            captured = capsys.readouterr()
            assert "Failed to fetch traces" in captured.err

    @pytest.mark.asyncio
    async def test_returns_none_when_no_matching_artifacts(self, capsys):
        """Should return None when no matching artifacts."""
        with patch(
            "heisenberg.integrations.github_artifacts.GitHubArtifactClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get_artifacts = AsyncMock(return_value=[])
            mock_client_cls.return_value = mock_client

            result = await fetch_and_analyze_traces("token", "owner", "repo", 123, "playwright")

            assert result is None


class TestFetchAndMergeBlobs:
    """Tests for fetch_and_merge_blobs function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_failed_runs(self):
        """Should return None when no failed runs found."""
        with patch(
            "heisenberg.integrations.github_artifacts.GitHubArtifactClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.list_workflow_runs = AsyncMock(return_value=[])
            mock_client_cls.return_value = mock_client

            result = await fetch_and_merge_blobs("token", "owner", "repo", None, "playwright")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_matching_artifacts(self):
        """Should return None when no matching artifacts."""
        mock_run = MagicMock()
        mock_run.id = 123
        mock_run.conclusion = "failure"

        with patch(
            "heisenberg.integrations.github_artifacts.GitHubArtifactClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.list_workflow_runs = AsyncMock(return_value=[mock_run])
            mock_client.get_artifacts = AsyncMock(return_value=[])
            mock_client_cls.return_value = mock_client

            result = await fetch_and_merge_blobs("token", "owner", "repo", None, "playwright")

        assert result is None

    @pytest.mark.asyncio
    async def test_raises_when_no_blob_zips_found(self, capsys):
        """Should raise BlobMergeError when no blob zips found."""
        from heisenberg.utils.merging import BlobMergeError

        mock_artifact = MagicMock()
        mock_artifact.name = "playwright-report"
        mock_artifact.id = 1

        with patch(
            "heisenberg.integrations.github_artifacts.GitHubArtifactClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get_artifacts = AsyncMock(return_value=[mock_artifact])
            mock_client.download_artifact = AsyncMock(return_value=b"zip_data")
            mock_client_cls.return_value = mock_client

            with patch("heisenberg.utils.merging.extract_blob_zips", return_value=[]):
                with pytest.raises(BlobMergeError) as exc_info:
                    await fetch_and_merge_blobs("token", "owner", "repo", 123, "playwright")

                assert "No blob ZIP files" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_merges_blob_reports(self, capsys):
        """Should merge blob reports successfully."""
        mock_artifact = MagicMock()
        mock_artifact.name = "playwright-report"
        mock_artifact.id = 1

        with patch(
            "heisenberg.integrations.github_artifacts.GitHubArtifactClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get_artifacts = AsyncMock(return_value=[mock_artifact])
            mock_client.download_artifact = AsyncMock(return_value=b"zip_data")
            mock_client_cls.return_value = mock_client

            with (
                patch(
                    "heisenberg.utils.merging.extract_blob_zips",
                    return_value=[b"blob1", b"blob2"],
                ),
                patch(
                    "heisenberg.utils.merging.merge_blob_reports",
                    new_callable=AsyncMock,
                    return_value={"tests": []},
                ),
            ):
                result = await fetch_and_merge_blobs("token", "owner", "repo", 123, "playwright")

        assert result == {"tests": []}
        captured = capsys.readouterr()
        assert "Merging 2 blob report" in captured.err


class TestRunFetchGithubCommand:
    """Tests for run_fetch_github function."""

    def test_returns_error_when_no_token(self, capsys):
        """Should return 1 when no token provided."""
        import argparse

        args = argparse.Namespace(
            repo="owner/repo",
            token=None,
            run_id=None,
            output=None,
            artifact_name="playwright",
            ai_analysis=False,
            provider="anthropic",
            list_artifacts=False,
            merge_blobs=False,
            include_logs=False,
            include_screenshots=False,
            include_traces=False,
        )

        with patch.dict("os.environ", {}, clear=True):
            result = run_fetch_github(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "GitHub token required" in captured.err

    def test_returns_error_for_invalid_repo_format(self, capsys, monkeypatch):
        """Should return 1 for invalid repo format."""
        import argparse

        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        args = argparse.Namespace(
            repo="invalid-repo",
            token=None,
            run_id=None,
            output=None,
            artifact_name="playwright",
            ai_analysis=False,
            provider="anthropic",
            list_artifacts=False,
            merge_blobs=False,
            include_logs=False,
            include_screenshots=False,
            include_traces=False,
        )

        result = run_fetch_github(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid repo format" in captured.err

    def test_list_artifacts_flag(self, monkeypatch):
        """Should call list_artifacts when flag set."""
        import argparse

        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        args = argparse.Namespace(
            repo="owner/repo",
            token=None,
            run_id=123,
            output=None,
            artifact_name="playwright",
            ai_analysis=False,
            provider="anthropic",
            list_artifacts=True,
            merge_blobs=False,
            include_logs=False,
            include_screenshots=False,
            include_traces=False,
        )

        with patch("heisenberg.cli.github_fetch.list_artifacts", new_callable=AsyncMock) as mock:
            mock.return_value = 0
            result = run_fetch_github(args)

        assert result == 0
        mock.assert_called_once()

    def test_returns_error_on_github_api_error(self, capsys, monkeypatch):
        """Should return 1 on GitHub API error."""
        import argparse

        from heisenberg.integrations.github_artifacts import GitHubAPIError

        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        args = argparse.Namespace(
            repo="owner/repo",
            token=None,
            run_id=123,
            output=None,
            artifact_name="playwright",
            ai_analysis=False,
            provider="anthropic",
            list_artifacts=True,
            merge_blobs=False,
            include_logs=False,
            include_screenshots=False,
            include_traces=False,
        )

        with patch("heisenberg.cli.github_fetch.list_artifacts", new_callable=AsyncMock) as mock:
            mock.side_effect = GitHubAPIError("API error")
            result = run_fetch_github(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "GitHub API error" in captured.err

    def test_saves_report_to_file(self, tmp_path, monkeypatch):
        """Should save report to file when output specified."""
        import argparse
        import json

        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        output_file = tmp_path / "report.json"

        args = argparse.Namespace(
            repo="owner/repo",
            token=None,
            run_id=123,
            output=output_file,
            artifact_name="playwright",
            ai_analysis=False,
            provider="anthropic",
            list_artifacts=False,
            merge_blobs=False,
            include_logs=False,
            include_screenshots=False,
            include_traces=False,
        )

        with patch(
            "heisenberg.cli.commands.github_fetch.fetch_report_from_run",
            new_callable=AsyncMock,
            return_value={"tests": []},
        ):
            result = run_fetch_github(args)

        assert result == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data == {"tests": []}

    def test_returns_error_when_no_report_found(self, capsys, monkeypatch):
        """Should return 1 when no report found."""
        import argparse

        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        args = argparse.Namespace(
            repo="owner/repo",
            token=None,
            run_id=123,
            output=None,
            artifact_name="playwright",
            ai_analysis=False,
            provider="anthropic",
            list_artifacts=False,
            merge_blobs=False,
            include_logs=False,
            include_screenshots=False,
            include_traces=False,
        )

        with patch(
            "heisenberg.cli.commands.github_fetch.fetch_report_from_run",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = run_fetch_github(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "No artifacts matching" in captured.err
        assert "Tip: Use --list-artifacts" in captured.err

    def test_includes_job_logs_when_flag_set(self, monkeypatch, capsys):
        """Should include job logs when include_logs flag set."""
        import argparse

        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        args = argparse.Namespace(
            repo="owner/repo",
            token=None,
            run_id=123,
            output=None,
            artifact_name="playwright",
            ai_analysis=False,
            provider="anthropic",
            list_artifacts=False,
            merge_blobs=False,
            include_logs=True,
            include_screenshots=False,
            include_traces=False,
        )

        with (
            patch(
                "heisenberg.cli.commands.github_fetch.fetch_report_from_run",
                new_callable=AsyncMock,
                return_value={"tests": []},
            ),
            patch(
                "heisenberg.cli.github_fetch.fetch_and_process_job_logs",
                new_callable=AsyncMock,
                return_value="job logs context",
            ) as mock_logs,
            patch("heisenberg.cli.commands._analyze_report_data", return_value=0) as mock_analyze,
        ):
            run_fetch_github(args)

        mock_logs.assert_called_once()
        mock_analyze.assert_called_once()
        call_args = mock_analyze.call_args
        assert call_args[0][2] == "job logs context"  # job_logs_context

    def test_merge_blobs_error_handling(self, capsys, monkeypatch):
        """Should handle blob merge errors gracefully."""
        import argparse

        from heisenberg.utils.merging import BlobMergeError

        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        args = argparse.Namespace(
            repo="owner/repo",
            token=None,
            run_id=123,
            output=None,
            artifact_name="playwright",
            ai_analysis=False,
            provider="anthropic",
            list_artifacts=False,
            merge_blobs=True,
            include_logs=False,
            include_screenshots=False,
            include_traces=False,
        )

        with patch(
            "heisenberg.cli.github_fetch.fetch_and_merge_blobs", new_callable=AsyncMock
        ) as mock:
            mock.side_effect = BlobMergeError("No blobs found")
            result = run_fetch_github(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "Blob merge error" in captured.err

    def test_includes_screenshots_when_flag_set(self, monkeypatch, capsys):
        """Should include screenshots when include_screenshots flag set."""
        import argparse

        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        args = argparse.Namespace(
            repo="owner/repo",
            token=None,
            run_id=123,
            output=None,
            artifact_name="playwright",
            ai_analysis=False,
            provider="anthropic",
            list_artifacts=False,
            merge_blobs=False,
            include_logs=False,
            include_screenshots=True,
            include_traces=False,
        )

        with (
            patch(
                "heisenberg.cli.commands.github_fetch.fetch_report_from_run",
                new_callable=AsyncMock,
                return_value={"tests": []},
            ),
            patch(
                "heisenberg.cli.github_fetch.fetch_and_analyze_screenshots",
                new_callable=AsyncMock,
                return_value="screenshot context",
            ) as mock_screenshots,
            patch("heisenberg.cli.commands._analyze_report_data", return_value=0) as mock_analyze,
        ):
            run_fetch_github(args)

        mock_screenshots.assert_called_once()
        mock_analyze.assert_called_once()
        call_args = mock_analyze.call_args
        assert call_args[0][3] == "screenshot context"  # screenshot_context

    def test_includes_traces_when_flag_set(self, monkeypatch, capsys):
        """Should include traces when include_traces flag set."""
        import argparse

        monkeypatch.setenv("GITHUB_TOKEN", "test-token")

        args = argparse.Namespace(
            repo="owner/repo",
            token=None,
            run_id=123,
            output=None,
            artifact_name="playwright",
            ai_analysis=False,
            provider="anthropic",
            list_artifacts=False,
            merge_blobs=False,
            include_logs=False,
            include_screenshots=False,
            include_traces=True,
        )

        with (
            patch(
                "heisenberg.cli.commands.github_fetch.fetch_report_from_run",
                new_callable=AsyncMock,
                return_value={"tests": []},
            ),
            patch(
                "heisenberg.cli.github_fetch.fetch_and_analyze_traces",
                new_callable=AsyncMock,
                return_value="trace context",
            ) as mock_traces,
            patch("heisenberg.cli.commands._analyze_report_data", return_value=0) as mock_analyze,
        ):
            run_fetch_github(args)

        mock_traces.assert_called_once()
        mock_analyze.assert_called_once()
        call_args = mock_analyze.call_args
        assert call_args[0][4] == "trace context"  # trace_context


class TestAnalyzeReportData:
    """Tests for _analyze_report_data function."""

    def test_analyzes_report_and_prints_result(self, tmp_path, capsys):
        """Should analyze report and print formatted result."""
        import argparse

        # Create a valid Playwright report
        report_data = {
            "suites": [
                {
                    "title": "test.spec.ts",
                    "specs": [
                        {
                            "title": "test case",
                            "tests": [
                                {
                                    "status": "passed",
                                    "results": [{"status": "passed", "duration": 100}],
                                }
                            ],
                        }
                    ],
                }
            ],
            "stats": {"total": 1, "passed": 1, "failed": 0},
        }

        args = argparse.Namespace(
            ai_analysis=False,
            provider="anthropic",
            model=None,
        )

        with patch("heisenberg.cli.commands.run_analysis") as mock_analysis:
            mock_result = MagicMock()
            mock_result.has_failures = False
            mock_result.summary = "1 passed"
            mock_result.report = MagicMock()
            mock_result.report.failed_tests = []
            mock_result.container_logs = None
            mock_analysis.return_value = mock_result

            result = _analyze_report_data(report_data, args)

        assert result == 0
        captured = capsys.readouterr()
        assert "Heisenberg" in captured.out

    def test_returns_one_when_failures(self, tmp_path, capsys):
        """Should return 1 when tests have failures."""
        import argparse

        report_data = {"suites": [], "stats": {"failed": 1}}

        args = argparse.Namespace(
            ai_analysis=False,
            provider="anthropic",
            model=None,
        )

        with patch("heisenberg.cli.commands.run_analysis") as mock_analysis:
            mock_result = MagicMock()
            mock_result.has_failures = True
            mock_result.summary = "1 failed"
            mock_result.report = MagicMock()
            mock_result.report.failed_tests = [MagicMock()]
            mock_result.container_logs = None
            mock_analysis.return_value = mock_result

            result = _analyze_report_data(report_data, args)

        assert result == 1

    def test_runs_ai_analysis_with_context(self, tmp_path, capsys):
        """Should run AI analysis with provided context."""
        import argparse

        report_data = {"suites": [], "stats": {}}

        args = argparse.Namespace(
            ai_analysis=True,
            provider="anthropic",
            model=None,
        )

        with (
            patch("heisenberg.cli.commands.run_analysis") as mock_analysis,
            patch("heisenberg.cli.commands.convert_to_unified") as mock_convert,
            patch("heisenberg.cli.commands.analyze_unified_run") as mock_ai,
        ):
            mock_result = MagicMock()
            mock_result.has_failures = True
            mock_result.summary = "1 failed"
            mock_result.report = MagicMock()
            mock_result.report.failed_tests = [MagicMock()]
            mock_result.container_logs = None
            mock_analysis.return_value = mock_result

            mock_unified = MagicMock()
            mock_convert.return_value = mock_unified

            mock_ai_result = MagicMock()
            mock_ai_result.diagnosis = MagicMock()
            mock_ai_result.diagnosis.root_cause = "Test failure"
            mock_ai_result.diagnosis.evidence = []
            mock_ai_result.diagnosis.suggested_fix = "Fix it"
            mock_ai_result.diagnosis.confidence = MagicMock(value="HIGH")
            mock_ai_result.diagnosis.confidence_explanation = "Clear"
            mock_ai_result.total_tokens = 100
            mock_ai_result.estimated_cost = 0.01
            mock_ai.return_value = mock_ai_result

            _analyze_report_data(
                report_data,
                args,
                job_logs_context="error logs",
                screenshot_context="screenshot info",
                trace_context="trace info",
            )

        mock_ai.assert_called_once()
        call_kwargs = mock_ai.call_args[1]
        assert call_kwargs["job_logs_context"] == "error logs"
        assert call_kwargs["screenshot_context"] == "screenshot info"
        assert call_kwargs["trace_context"] == "trace info"

    def test_handles_ai_analysis_failure(self, tmp_path, capsys):
        """Should handle AI analysis failure gracefully."""
        import argparse

        report_data = {"suites": [], "stats": {}}

        args = argparse.Namespace(
            ai_analysis=True,
            provider="anthropic",
            model=None,
        )

        with (
            patch("heisenberg.cli.commands.run_analysis") as mock_analysis,
            patch("heisenberg.cli.commands.analyze_with_ai") as mock_ai,
        ):
            mock_result = MagicMock()
            mock_result.has_failures = True
            mock_result.summary = "1 failed"
            mock_result.report = MagicMock()
            mock_result.report.failed_tests = [MagicMock()]
            mock_result.container_logs = None
            mock_analysis.return_value = mock_result

            mock_ai.side_effect = Exception("API error")

            result = _analyze_report_data(report_data, args)

        assert result == 1
        captured = capsys.readouterr()
        assert "AI analysis failed" in captured.err


class TestConvertToUnified:
    """Tests for convert_to_unified function."""

    def test_converts_playwright_report(self):
        """Should convert Playwright report to UnifiedTestRun."""
        mock_report = MagicMock()
        mock_report.total_passed = 5
        mock_report.total_failed = 1
        mock_report.total_skipped = 0
        mock_report.total_flaky = 0
        mock_report.failed_tests = []

        result = convert_to_unified(
            mock_report,
            run_id="run-123",
            repository="owner/repo",
            branch="main",
        )

        assert result.run_id == "run-123"
        assert result.repository == "owner/repo"
        assert result.branch == "main"
        assert result.total_tests == 6
        assert result.passed_tests == 5


class TestAnalyzeTracesFromZip:
    """Tests for _analyze_traces_from_zip helper function."""

    def test_returns_empty_list_for_empty_zip(self):
        """Should return empty list when zip has no trace files."""
        import io
        import zipfile

        # Create empty zip
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("readme.txt", "no traces here")
        zip_data = buffer.getvalue()

        mock_analyzer = MagicMock()
        result = _analyze_traces_from_zip(zip_data, mock_analyzer)

        assert result == []
        mock_analyzer.analyze.assert_not_called()

    def test_processes_trace_zip_files(self):
        """Should process files ending with trace.zip."""
        import io
        import zipfile

        # Create zip with a trace.zip file
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            # Create inner trace zip
            inner_buffer = io.BytesIO()
            with zipfile.ZipFile(inner_buffer, "w") as inner_zf:
                inner_zf.writestr("trace.json", "{}")
            zf.writestr("test-name/trace.zip", inner_buffer.getvalue())
        zip_data = buffer.getvalue()

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = {"test": "result"}

        result = _analyze_traces_from_zip(zip_data, mock_analyzer)

        assert len(result) == 1
        mock_analyzer.analyze.assert_called_once()

    def test_extracts_test_name_from_path(self):
        """Should extract test name from parent directory."""
        import io
        import zipfile

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            inner_buffer = io.BytesIO()
            with zipfile.ZipFile(inner_buffer, "w") as inner_zf:
                inner_zf.writestr("trace.json", "{}")
            zf.writestr("my-test-case/trace.zip", inner_buffer.getvalue())
        zip_data = buffer.getvalue()

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = {"test": "result"}

        _analyze_traces_from_zip(zip_data, mock_analyzer)

        # Verify test_name was extracted from path
        call_args = mock_analyzer.analyze.call_args
        assert call_args[0][1] == "my-test-case"  # test_name argument

    def test_limits_to_five_traces(self):
        """Should process at most 5 trace files."""
        import io
        import zipfile

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            for i in range(10):
                inner_buffer = io.BytesIO()
                with zipfile.ZipFile(inner_buffer, "w") as inner_zf:
                    inner_zf.writestr("trace.json", "{}")
                zf.writestr(f"test-{i}/trace.zip", inner_buffer.getvalue())
        zip_data = buffer.getvalue()

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = {"test": "result"}

        result = _analyze_traces_from_zip(zip_data, mock_analyzer)

        assert len(result) == 5
        assert mock_analyzer.analyze.call_count == 5

    def test_handles_analysis_errors_gracefully(self, capsys):
        """Should handle errors during trace analysis."""
        import io
        import zipfile

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            inner_buffer = io.BytesIO()
            with zipfile.ZipFile(inner_buffer, "w") as inner_zf:
                inner_zf.writestr("trace.json", "{}")
            zf.writestr("test/trace.zip", inner_buffer.getvalue())
        zip_data = buffer.getvalue()

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = Exception("Analysis failed")

        result = _analyze_traces_from_zip(zip_data, mock_analyzer)

        # Should return empty list on error but not crash
        assert result == []
        captured = capsys.readouterr()
        assert "Error analyzing traces" in captured.err
