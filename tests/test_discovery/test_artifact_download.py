"""Tests for direct artifact download (S3 bypass)."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import MagicMock, patch

from heisenberg.discovery.analysis import download_and_check_failures

# =============================================================================
# DOWNLOAD ARTIFACT BY ID - Core functionality
# =============================================================================


class TestDownloadArtifactById:
    """Tests for download_artifact_by_id function - direct blob storage download."""

    @patch("heisenberg.discovery.client.requests.get")
    @patch("heisenberg.discovery.client._get_gh_token")
    def test_downloads_and_extracts_zip_on_success(self, mock_token, mock_get, tmp_path):
        """Should download from blob storage URL and extract to target directory."""
        from heisenberg.discovery.client import download_artifact_by_id

        mock_token.return_value = "test-token"

        # Create a valid zip file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("test.txt", "content")
        zip_content = zip_buffer.getvalue()

        # First call: redirect response
        redirect_response = MagicMock()
        redirect_response.status_code = 302
        redirect_response.headers = {"Location": "https://blob.example.com/artifact.zip"}

        # Second call: actual download
        download_response = MagicMock()
        download_response.status_code = 200
        download_response.iter_content = lambda chunk_size: [zip_content]
        download_response.__enter__ = lambda s: download_response
        download_response.__exit__ = MagicMock(return_value=False)

        mock_get.side_effect = [redirect_response, download_response]

        target_dir = tmp_path / "extracted"
        target_dir.mkdir()

        result = download_artifact_by_id(12345, str(target_dir), repo="owner/repo")

        assert result is True
        assert (target_dir / "test.txt").exists()
        assert (target_dir / "test.txt").read_text() == "content"

    @patch("heisenberg.discovery.client._get_gh_token")
    def test_returns_false_when_no_token(self, mock_token, tmp_path):
        """Should return False when GitHub token is not available."""
        from heisenberg.discovery.client import download_artifact_by_id

        mock_token.return_value = None

        result = download_artifact_by_id(12345, str(tmp_path), repo="owner/repo")

        assert result is False

    @patch("heisenberg.discovery.client.requests.get")
    @patch("heisenberg.discovery.client._get_gh_token")
    def test_returns_false_when_not_redirect(self, mock_token, mock_get, tmp_path):
        """Should return False when API doesn't return 302 redirect."""
        from heisenberg.discovery.client import download_artifact_by_id

        mock_token.return_value = "test-token"

        response = MagicMock()
        response.status_code = 404
        mock_get.return_value = response

        result = download_artifact_by_id(12345, str(tmp_path), repo="owner/repo")

        assert result is False

    @patch("heisenberg.discovery.client.requests.get")
    @patch("heisenberg.discovery.client._get_gh_token")
    def test_calls_correct_api_url(self, mock_token, mock_get, tmp_path):
        """Should call GitHub API with correct artifact download URL."""
        from heisenberg.discovery.client import download_artifact_by_id

        mock_token.return_value = "test-token"

        response = MagicMock()
        response.status_code = 404
        mock_get.return_value = response

        download_artifact_by_id(99999, str(tmp_path), repo="owner/project")

        call_args = mock_get.call_args_list[0]
        assert (
            call_args[0][0]
            == "https://api.github.com/repos/owner/project/actions/artifacts/99999/zip"
        )

    def test_returns_false_without_repo(self, tmp_path):
        """Should return False when repo is not provided."""
        from heisenberg.discovery.client import download_artifact_by_id

        result = download_artifact_by_id(12345, str(tmp_path))

        assert result is False


# =============================================================================
# DOWNLOAD ARTIFACT BY ID - Error handling
# =============================================================================


class TestDownloadArtifactByIdErrorHandling:
    """Tests for error handling in direct artifact download."""

    @patch("heisenberg.discovery.client.requests.get")
    @patch("heisenberg.discovery.client._get_gh_token")
    def test_returns_false_on_invalid_zip(self, mock_token, mock_get, tmp_path):
        """Should return False when downloaded content is not a valid zip."""
        from heisenberg.discovery.client import download_artifact_by_id

        mock_token.return_value = "test-token"

        redirect_response = MagicMock()
        redirect_response.status_code = 302
        redirect_response.headers = {"Location": "https://blob.example.com/artifact.zip"}

        download_response = MagicMock()
        download_response.status_code = 200
        download_response.iter_content = lambda chunk_size: [b"not a zip file"]
        download_response.__enter__ = lambda s: download_response
        download_response.__exit__ = MagicMock(return_value=False)

        mock_get.side_effect = [redirect_response, download_response]

        result = download_artifact_by_id(12345, str(tmp_path), repo="owner/repo")

        assert result is False

    @patch("heisenberg.discovery.client.requests.get")
    @patch("heisenberg.discovery.client._get_gh_token")
    def test_returns_false_on_network_error(self, mock_token, mock_get, tmp_path):
        """Should return False on network errors during download."""
        from heisenberg.discovery.client import download_artifact_by_id

        mock_token.return_value = "test-token"
        mock_get.side_effect = Exception("Connection refused")

        result = download_artifact_by_id(12345, str(tmp_path), repo="owner/repo")

        assert result is False

    @patch("heisenberg.discovery.client.requests.get")
    @patch("heisenberg.discovery.client._get_gh_token")
    def test_uses_streaming_download(self, mock_token, mock_get, tmp_path):
        """Should use streaming download (memory efficient)."""
        from heisenberg.discovery.client import download_artifact_by_id

        mock_token.return_value = "test-token"

        redirect_response = MagicMock()
        redirect_response.status_code = 302
        redirect_response.headers = {"Location": "https://blob.example.com/artifact.zip"}

        download_response = MagicMock()
        download_response.raise_for_status.side_effect = Exception("Error")
        download_response.__enter__ = lambda s: download_response
        download_response.__exit__ = MagicMock(return_value=False)

        mock_get.side_effect = [redirect_response, download_response]

        download_artifact_by_id(12345, str(tmp_path), repo="owner/repo")

        # Second call (blob download) should use stream=True
        blob_call = mock_get.call_args_list[1]
        assert blob_call[1].get("stream") is True


# =============================================================================
# RATE LIMIT - Direct download uses only 1 API call
# =============================================================================


class TestDirectDownloadRateLimit:
    """Tests verifying direct blob download uses minimal API calls."""

    @patch("heisenberg.discovery.client.requests.get")
    @patch("heisenberg.discovery.client._get_gh_token")
    def test_makes_only_one_api_call(self, mock_token, mock_get, tmp_path):
        """Should make only 1 API call (to get redirect URL)."""
        from heisenberg.discovery.client import download_artifact_by_id

        mock_token.return_value = "test-token"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("test.txt", "content")

        redirect_response = MagicMock()
        redirect_response.status_code = 302
        redirect_response.headers = {"Location": "https://blob.example.com/artifact.zip"}

        download_response = MagicMock()
        download_response.status_code = 200
        download_response.iter_content = lambda chunk_size: [zip_buffer.getvalue()]
        download_response.__enter__ = lambda s: download_response
        download_response.__exit__ = MagicMock(return_value=False)

        mock_get.side_effect = [redirect_response, download_response]

        download_artifact_by_id(12345, str(tmp_path), repo="owner/repo")

        # 2 requests total: 1 API call (get redirect), 1 blob download (free)
        assert mock_get.call_count == 2

        # First call is to GitHub API (uses rate limit)
        api_call = mock_get.call_args_list[0]
        assert "api.github.com" in api_call[0][0]

        # Second call is to blob storage (doesn't use rate limit)
        blob_call = mock_get.call_args_list[1]
        assert "blob.example.com" in blob_call[0][0]


# =============================================================================
# DOWNLOAD AND CHECK FAILURES - With artifact_id
# =============================================================================


class TestDownloadAndCheckFailuresWithId:
    """Tests for download_and_check_failures using artifact_id (direct S3 download)."""

    @patch("heisenberg.discovery.analysis.download_artifact_by_id")
    @patch("heisenberg.discovery.analysis.extract_failure_count_from_dir")
    def test_uses_artifact_id_when_provided(self, mock_extract, mock_download, tmp_path):
        """Should use download_artifact_by_id when artifact_id is provided."""
        mock_download.return_value = True
        mock_extract.return_value = 5

        result = download_and_check_failures(
            repo="owner/repo", artifact_name="playwright-report", artifact_id=12345
        )

        assert result == 5
        mock_download.assert_called_once()
        # Should include artifact_id in call
        call_kwargs = mock_download.call_args
        assert call_kwargs[0][0] == 12345  # artifact_id is first positional arg

    @patch("heisenberg.discovery.analysis.download_artifact_to_dir")
    @patch("heisenberg.discovery.analysis.extract_failure_count_from_dir")
    def test_falls_back_to_name_when_no_id(self, mock_extract, mock_download, tmp_path):
        """Should use download_artifact_to_dir when artifact_id is not provided."""
        mock_download.return_value = True
        mock_extract.return_value = 3

        result = download_and_check_failures(repo="owner/repo", artifact_name="playwright-report")

        assert result == 3
        mock_download.assert_called_once()

    @patch("heisenberg.discovery.analysis.download_artifact_by_id")
    def test_returns_none_when_download_fails_with_id(self, mock_download):
        """Should return None when download_artifact_by_id fails."""
        mock_download.return_value = False

        result = download_and_check_failures(
            repo="owner/repo", artifact_name="playwright-report", artifact_id=12345
        )

        assert result is None
