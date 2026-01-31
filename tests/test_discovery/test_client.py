"""Tests for GitHub API client (gh CLI communication)."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

from heisenberg.discovery.client import (
    _gh_subprocess,
    _is_rate_limit_error,
    get_failed_runs,
    get_repo_stars,
    get_run_artifacts,
    search_repos,
)
from heisenberg.discovery.models import GH_MAX_RETRIES

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

    @patch("heisenberg.discovery.client.gh_api")
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
    def test_returns_repo_tuples_with_stars(self, mock_run, _mock_sleep):
        """Should return list of (repo, stars) tuples."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {"items": [{"repository": {"full_name": "owner/repo", "stargazers_count": 500}}]}
            ),
            returncode=0,
        )

        results = search_repos("playwright", limit=10)

        assert len(results) == 1
        assert results[0] == ("owner/repo", 500)

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_deduplicates_across_results(self, mock_run, _mock_sleep):
        """Should deduplicate repos that appear multiple times, keeping highest stars."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "items": [
                        {"repository": {"full_name": "owner/repo", "stargazers_count": 100}},
                        {"repository": {"full_name": "owner/repo", "stargazers_count": 100}},
                    ]
                }
            ),
            returncode=0,
        )

        results = search_repos("query", limit=10)

        assert len(results) == 1
        assert results[0] == ("owner/repo", 100)

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_defaults_to_zero_stars_when_missing(self, mock_run, _mock_sleep):
        """Should default to 0 stars when stargazers_count is missing."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"items": [{"repository": {"full_name": "owner/repo"}}]}),
            returncode=0,
        )

        results = search_repos("query", limit=10)

        assert len(results) == 1
        assert results[0] == ("owner/repo", 0)


class TestGetRepoStars:
    """Tests for get_repo_stars function."""

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_star_count_on_success(self, mock_run, _mock_sleep):
        """Should return star count from API response."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"stargazers_count": 42}),
            returncode=0,
        )

        result = get_repo_stars("owner/repo")

        assert result == 42

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_zero_for_zero_star_repo(self, mock_run, _mock_sleep):
        """Should return 0 for repos with no stars."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"stargazers_count": 0}),
            returncode=0,
        )

        result = get_repo_stars("owner/repo")

        assert result == 0

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_none_on_api_error(self, mock_run, _mock_sleep):
        """Should return None when gh CLI fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "gh", stderr="Not Found")

        result = get_repo_stars("owner/repo")

        assert result is None

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_none_on_timeout(self, mock_run, _mock_sleep):
        """Should return None when request times out."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        result = get_repo_stars("owner/repo")

        assert result is None

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_none_on_invalid_json(self, mock_run, _mock_sleep):
        """Should return None when response is not valid JSON."""
        mock_run.return_value = MagicMock(
            stdout="not valid json",
            returncode=0,
        )

        result = get_repo_stars("owner/repo")

        assert result is None


# =============================================================================
# TIMEOUT HANDLING
# =============================================================================


class TestSubprocessTimeouts:
    """Tests for subprocess timeout handling."""

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_gh_api_returns_none_on_timeout(self, mock_run, _mock_sleep):
        """gh_api should return None when subprocess times out."""
        from heisenberg.discovery.client import gh_api

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        result = gh_api("/repos/owner/repo")

        assert result is None

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_search_repos_returns_empty_on_timeout(self, mock_run, _mock_sleep):
        """search_repos should return empty list of tuples on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        result = search_repos("query", limit=10)

        assert result == []
        assert isinstance(result, list)

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
        from heisenberg.discovery.client import download_artifact_to_dir

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=120)

        result = download_artifact_to_dir("owner/repo", "artifact", "/tmp/target")

        assert result is False

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_download_artifact_passes_timeout(self, mock_run, _mock_sleep):
        """download_artifact_to_dir should pass timeout to subprocess."""
        from heisenberg.discovery.client import download_artifact_to_dir
        from heisenberg.discovery.models import TIMEOUT_DOWNLOAD

        mock_run.return_value = MagicMock(returncode=0)

        download_artifact_to_dir("owner/repo", "artifact", "/tmp/target")

        _, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == TIMEOUT_DOWNLOAD

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_gh_api_passes_timeout(self, mock_run, _mock_sleep):
        """gh_api should pass timeout to subprocess."""
        from heisenberg.discovery.client import gh_api
        from heisenberg.discovery.models import TIMEOUT_API

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
    def test_raises_rate_limit_error_after_retries(self, mock_run, _mock_sleep):
        """gh_api should raise GitHubRateLimitError after retries are exhausted."""
        from subprocess import CalledProcessError

        import pytest

        from heisenberg.discovery.client import gh_api
        from heisenberg.discovery.models import GitHubRateLimitError

        mock_run.side_effect = CalledProcessError(1, "gh", stderr="API rate limit exceeded")

        with pytest.raises(GitHubRateLimitError):
            gh_api("/repos/owner/repo")


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
    def test_raises_rate_limit_error_after_max_retries(self, mock_run, mock_sleep, _mock_random):
        """Should raise GitHubRateLimitError after exhausting all retries."""
        import pytest

        from heisenberg.discovery.models import GitHubRateLimitError

        rate_error = subprocess.CalledProcessError(1, "gh", stderr="rate limit exceeded")
        mock_run.side_effect = rate_error

        with pytest.raises(GitHubRateLimitError):
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

        from heisenberg.discovery.models import GitHubRateLimitError

        rate_error = subprocess.CalledProcessError(1, "gh", stderr="rate limit")
        mock_run.side_effect = rate_error

        with pytest.raises(GitHubRateLimitError):
            _gh_subprocess(["gh", "api", "/test"])

        backoff_delays = [call[0][0] for call in mock_sleep.call_args_list if call[0][0] >= 1.0]
        assert len(backoff_delays) == GH_MAX_RETRIES
        for i in range(1, len(backoff_delays)):
            assert backoff_delays[i] > backoff_delays[i - 1]


# =============================================================================
# BATCH STAR FETCHING
# =============================================================================


class TestFetchStarsBatch:
    """Tests for fetch_stars_batch function."""

    @patch("heisenberg.discovery.client.get_repo_stars")
    def test_returns_dict_of_repo_to_stars(self, mock_get_stars):
        """Should return dict mapping repo names to star counts."""
        from heisenberg.discovery.client import fetch_stars_batch

        mock_get_stars.side_effect = lambda repo: {"a/x": 100, "b/y": 200}[repo]

        result = fetch_stars_batch(["a/x", "b/y"])

        assert result == {"a/x": 100, "b/y": 200}

    @patch("heisenberg.discovery.client.get_repo_stars")
    def test_handles_api_failures_gracefully(self, mock_get_stars):
        """Should use 0 for repos where API call failed (returned None)."""
        from heisenberg.discovery.client import fetch_stars_batch

        mock_get_stars.side_effect = lambda repo: 100 if repo == "a/x" else None

        result = fetch_stars_batch(["a/x", "b/y"])

        assert result == {"a/x": 100, "b/y": 0}

    @patch("heisenberg.discovery.client.get_repo_stars")
    def test_returns_empty_dict_for_empty_input(self, mock_get_stars):
        """Should return empty dict when given empty list."""
        from heisenberg.discovery.client import fetch_stars_batch

        result = fetch_stars_batch([])

        assert result == {}
        mock_get_stars.assert_not_called()

    @patch("heisenberg.discovery.client.get_repo_stars")
    def test_fetches_in_parallel(self, mock_get_stars):
        """Should use ThreadPoolExecutor for parallel fetching."""
        from heisenberg.discovery.client import fetch_stars_batch

        mock_get_stars.return_value = 50

        result = fetch_stars_batch(["a/1", "b/2", "c/3"])

        assert len(result) == 3
        assert mock_get_stars.call_count == 3

    @patch("heisenberg.discovery.client.get_repo_stars")
    def test_all_failures_returns_all_zeros(self, mock_get_stars):
        """Should return 0 for all repos when all API calls fail."""
        from heisenberg.discovery.client import fetch_stars_batch

        mock_get_stars.return_value = None

        result = fetch_stars_batch(["a/x", "b/y"])

        assert result == {"a/x": 0, "b/y": 0}


# =============================================================================
# JOB-AWARE ARTIFACT SELECTION
# =============================================================================


class TestGetFailedJobs:
    """Tests for get_failed_jobs function."""

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_failed_job_names(self, mock_run, _mock_sleep):
        """Should return list of failed job names."""
        from heisenberg.discovery.client import get_failed_jobs

        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "jobs": [
                        {"name": "e2e-web (ubuntu-latest)", "conclusion": "failure"},
                        {"name": "e2e-desktop [1/4]", "conclusion": "success"},
                        {"name": "npm audit", "conclusion": "failure"},
                    ]
                }
            ),
            returncode=0,
        )

        result = get_failed_jobs("owner/repo", "12345")

        assert result == ["e2e-web (ubuntu-latest)", "npm audit"]

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_empty_list_when_no_failures(self, mock_run, _mock_sleep):
        """Should return empty list when all jobs passed."""
        from heisenberg.discovery.client import get_failed_jobs

        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "jobs": [
                        {"name": "build", "conclusion": "success"},
                        {"name": "test", "conclusion": "success"},
                    ]
                }
            ),
            returncode=0,
        )

        result = get_failed_jobs("owner/repo", "12345")

        assert result == []

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_returns_empty_list_on_api_error(self, mock_run, _mock_sleep):
        """Should return empty list on API error."""
        from heisenberg.discovery.client import get_failed_jobs

        mock_run.side_effect = subprocess.CalledProcessError(1, "gh")

        result = get_failed_jobs("owner/repo", "12345")

        assert result == []

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_calls_correct_api_endpoint(self, mock_run, _mock_sleep):
        """Should call the jobs endpoint with correct parameters."""
        from heisenberg.discovery.client import get_failed_jobs

        mock_run.return_value = MagicMock(
            stdout=json.dumps({"jobs": []}),
            returncode=0,
        )

        get_failed_jobs("owner/repo", "99999")

        call_args = mock_run.call_args[0][0]
        assert "repos/owner/repo/actions/runs/99999/jobs" in " ".join(call_args)
