"""Tests for GitHub API client (gh CLI communication)."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

from heisenberg.playground.discover.client import (
    _gh_subprocess,
    _is_rate_limit_error,
    get_failed_runs,
    get_run_artifacts,
    search_repos,
)
from heisenberg.playground.discover.models import GH_MAX_RETRIES

# =============================================================================
# GITHUB CLIENT TESTS
# =============================================================================


class TestGetFailedRuns:
    """Tests for get_failed_runs function."""

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_workflow_runs(self, mock_run, _mock_sleep):
        """Should return list of workflow runs."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "workflow_runs": [
                        {"id": 100, "html_url": "url1"},
                        {"id": 200, "html_url": "url2"},
                    ]
                }
            ),
            returncode=0,
        )

        runs = get_failed_runs("owner/repo")

        assert len(runs) == 2
        assert runs[0]["id"] == 100

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_requests_multiple_runs(self, mock_run, _mock_sleep):
        """Should request per_page=5 by default."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"workflow_runs": []}),
            returncode=0,
        )

        get_failed_runs("owner/repo")

        call_args = " ".join(mock_run.call_args[0][0])
        assert "per_page=5" in call_args


class TestGetRunArtifacts:
    """Tests for get_run_artifacts function."""

    @patch("heisenberg.playground.discover.client.gh_api")
    def test_returns_artifacts_list(self, mock_gh_api):
        """Should return list of artifact dicts."""
        mock_gh_api.return_value = {
            "artifacts": [
                {"name": "report1", "expired": False},
                {"name": "report2", "expired": True},
            ]
        }

        artifacts = get_run_artifacts("owner/repo", "123")

        assert len(artifacts) == 2
        assert artifacts[0]["name"] == "report1"


class TestSearchRepos:
    """Tests for search_repos function."""

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_repo_names(self, mock_run, _mock_sleep):
        """Should return list of repo names."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"items": [{"repository": {"full_name": "owner/repo"}}]}),
            returncode=0,
        )

        results = search_repos("playwright", limit=10)

        assert len(results) == 1
        assert results[0] == "owner/repo"

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_deduplicates_across_results(self, mock_run, _mock_sleep):
        """Should deduplicate repos that appear multiple times."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "items": [
                        {"repository": {"full_name": "owner/repo"}},
                        {"repository": {"full_name": "owner/repo"}},
                    ]
                }
            ),
            returncode=0,
        )

        results = search_repos("query", limit=10)

        assert len(results) == 1


# =============================================================================
# TIMEOUT HANDLING
# =============================================================================


class TestSubprocessTimeouts:
    """Tests for subprocess timeout handling."""

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_gh_api_returns_none_on_timeout(self, mock_run, _mock_sleep):
        """gh_api should return None when subprocess times out."""
        from heisenberg.playground.discover.client import gh_api

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        result = gh_api("/repos/owner/repo")

        assert result is None

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_search_repos_returns_empty_on_timeout(self, mock_run, _mock_sleep):
        """search_repos should return empty list on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        result = search_repos("query", limit=10)

        assert result == []

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_get_failed_runs_returns_empty_on_timeout(self, mock_run, _mock_sleep):
        """get_failed_runs should return empty list on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        result = get_failed_runs("owner/repo")

        assert result == []

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_download_artifact_returns_false_on_timeout(self, mock_run, _mock_sleep):
        """download_artifact_to_dir should return False on timeout."""
        from heisenberg.playground.discover.client import download_artifact_to_dir

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=120)

        result = download_artifact_to_dir("owner/repo", "artifact", "/tmp/target")

        assert result is False

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_download_artifact_passes_timeout(self, mock_run, _mock_sleep):
        """download_artifact_to_dir should pass timeout to subprocess."""
        from heisenberg.playground.discover.client import download_artifact_to_dir
        from heisenberg.playground.discover.models import TIMEOUT_DOWNLOAD

        mock_run.return_value = MagicMock(returncode=0)

        download_artifact_to_dir("owner/repo", "artifact", "/tmp/target")

        _, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == TIMEOUT_DOWNLOAD

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_gh_api_passes_timeout(self, mock_run, _mock_sleep):
        """gh_api should pass timeout to subprocess."""
        from heisenberg.playground.discover.client import gh_api
        from heisenberg.playground.discover.models import TIMEOUT_API

        mock_run.return_value = MagicMock(
            stdout='{"ok": true}',
            returncode=0,
        )

        gh_api("/repos/owner/repo")

        _, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == TIMEOUT_API


# =============================================================================
# RATE LIMIT HANDLING
# =============================================================================


class TestRateLimitHandling:
    """Tests for rate limit handling."""

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_handles_rate_limit_error_gracefully(self, mock_run, _mock_sleep):
        """gh_api should return None after retries are exhausted."""
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, "gh", stderr="API rate limit exceeded")

        from heisenberg.playground.discover.client import gh_api

        result = gh_api("/repos/owner/repo")

        assert result is None


class TestIsRateLimitError:
    """Tests for _is_rate_limit_error helper."""

    def test_detects_rate_limit_text(self):
        """Should detect 'rate limit' in stderr."""
        exc = subprocess.CalledProcessError(1, "gh", stderr="API rate limit exceeded")
        assert _is_rate_limit_error(exc) is True

    def test_detects_abuse_text(self):
        """Should detect 'abuse' in stderr (GitHub secondary rate limit)."""
        exc = subprocess.CalledProcessError(
            1, "gh", stderr="You have triggered an abuse detection mechanism"
        )
        assert _is_rate_limit_error(exc) is True

    def test_case_insensitive(self):
        """Should detect rate limit regardless of case."""
        exc = subprocess.CalledProcessError(1, "gh", stderr="Rate Limit Exceeded")
        assert _is_rate_limit_error(exc) is True

    def test_false_for_other_errors(self):
        """Should return False for non-rate-limit errors."""
        exc = subprocess.CalledProcessError(1, "gh", stderr="Not Found")
        assert _is_rate_limit_error(exc) is False

    def test_false_for_empty_stderr(self):
        """Should return False when stderr is empty string."""
        exc = subprocess.CalledProcessError(1, "gh", stderr="")
        assert _is_rate_limit_error(exc) is False

    def test_false_for_none_stderr(self):
        """Should return False when stderr is None."""
        exc = subprocess.CalledProcessError(1, "gh", stderr=None)
        assert _is_rate_limit_error(exc) is False


class TestGhSubprocess:
    """Tests for _gh_subprocess throttle + retry wrapper."""

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_result_on_success(self, mock_run, mock_sleep, _mock_random):
        """Should return subprocess result on first attempt."""
        mock_run.return_value = MagicMock(stdout='{"ok": true}', returncode=0)

        result = _gh_subprocess(["gh", "api", "/test"])

        assert result.stdout == '{"ok": true}'
        mock_run.assert_called_once()

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_retries_on_rate_limit(self, mock_run, mock_sleep, _mock_random):
        """Should retry and succeed after transient rate limit."""
        rate_error = subprocess.CalledProcessError(1, "gh", stderr="rate limit exceeded")
        success = MagicMock(stdout='{"ok": true}', returncode=0)
        mock_run.side_effect = [rate_error, success]

        result = _gh_subprocess(["gh", "api", "/test"])

        assert result.stdout == '{"ok": true}'
        assert mock_run.call_count == 2

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_raises_after_max_retries(self, mock_run, mock_sleep, _mock_random):
        """Should raise CalledProcessError after exhausting all retries."""
        import pytest

        rate_error = subprocess.CalledProcessError(1, "gh", stderr="rate limit exceeded")
        mock_run.side_effect = rate_error

        with pytest.raises(subprocess.CalledProcessError):
            _gh_subprocess(["gh", "api", "/test"])

        assert mock_run.call_count == GH_MAX_RETRIES + 1

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_no_retry_on_other_errors(self, mock_run, mock_sleep, _mock_random):
        """Should raise immediately for non-rate-limit errors."""
        import pytest

        other_error = subprocess.CalledProcessError(1, "gh", stderr="Not Found")
        mock_run.side_effect = other_error

        with pytest.raises(subprocess.CalledProcessError):
            _gh_subprocess(["gh", "api", "/test"])

        mock_run.assert_called_once()

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_no_retry_on_timeout(self, mock_run, mock_sleep, _mock_random):
        """Should raise immediately on timeout (not retryable)."""
        import pytest

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        with pytest.raises(subprocess.TimeoutExpired):
            _gh_subprocess(["gh", "api", "/test"])

        mock_run.assert_called_once()

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_passes_timeout_parameter(self, mock_run, mock_sleep, _mock_random):
        """Should forward timeout to subprocess.run."""
        mock_run.return_value = MagicMock(stdout="{}", returncode=0)

        _gh_subprocess(["gh", "api", "/test"], timeout=60)

        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 60

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_jitter_before_each_attempt(self, mock_run, mock_sleep, _mock_random):
        """Should sleep with small jitter before each API call."""
        mock_run.return_value = MagicMock(stdout="{}", returncode=0)

        _gh_subprocess(["gh", "api", "/test"])

        assert mock_sleep.call_count >= 1
        assert mock_sleep.call_args_list[0] == ((0.1,),)

    @patch("random.uniform", return_value=0.1)
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_backoff_delays_increase(self, mock_run, mock_sleep, _mock_random):
        """Retry backoff delays should increase exponentially."""
        import pytest

        rate_error = subprocess.CalledProcessError(1, "gh", stderr="rate limit")
        mock_run.side_effect = rate_error

        with pytest.raises(subprocess.CalledProcessError):
            _gh_subprocess(["gh", "api", "/test"])

        backoff_delays = [call[0][0] for call in mock_sleep.call_args_list if call[0][0] >= 1.0]
        assert len(backoff_delays) == GH_MAX_RETRIES
        for i in range(1, len(backoff_delays)):
            assert backoff_delays[i] > backoff_delays[i - 1]
