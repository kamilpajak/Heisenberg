"""Tests for GitHub API client - TDD Red-Green-Refactor."""

from unittest.mock import MagicMock, patch

import pytest

from heisenberg.github_client import (
    GitHubClient,
    GitHubContext,
    post_pr_comment,
)


class TestGitHubContext:
    """Test suite for GitHubContext data model."""

    def test_context_from_environment(self, monkeypatch):
        """Should parse context from GitHub Actions environment variables."""
        # Given
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_SHA", "abc123def456")
        monkeypatch.setenv("GITHUB_REF", "refs/pull/42/merge")
        monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")

        # When
        context = GitHubContext.from_environment()

        # Then
        assert context.owner == "owner"
        assert context.repo == "repo"
        assert context.sha == "abc123def456"
        assert context.pr_number == 42

    def test_context_extracts_pr_number_from_ref(self, monkeypatch):
        """Should extract PR number from GITHUB_REF."""
        # Given
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_SHA", "abc123")
        monkeypatch.setenv("GITHUB_REF", "refs/pull/123/merge")
        monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")

        # When
        context = GitHubContext.from_environment()

        # Then
        assert context.pr_number == 123

    def test_context_handles_push_event(self, monkeypatch):
        """Should handle push events (no PR number)."""
        # Given
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_SHA", "abc123")
        monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
        monkeypatch.setenv("GITHUB_EVENT_NAME", "push")

        # When
        context = GitHubContext.from_environment()

        # Then
        assert context.pr_number is None
        assert not context.is_pull_request

    def test_context_is_pull_request_property(self, monkeypatch):
        """Should correctly identify PR context."""
        # Given
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_SHA", "abc123")
        monkeypatch.setenv("GITHUB_REF", "refs/pull/42/merge")
        monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")

        # When
        context = GitHubContext.from_environment()

        # Then
        assert context.is_pull_request


class TestGitHubClient:
    """Test suite for GitHubClient."""

    def test_client_initializes_with_token(self):
        """Client should initialize with GitHub token."""
        # When
        client = GitHubClient(token="ghp_test_token")

        # Then
        assert client.token == "ghp_test_token"

    def test_client_from_environment(self, monkeypatch):
        """Client should read token from environment."""
        # Given
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_env_token")

        # When
        client = GitHubClient.from_environment()

        # Then
        assert client.token == "ghp_env_token"

    def test_client_raises_without_token(self, monkeypatch):
        """Client should raise error if no token available."""
        # Given
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        # When/Then
        with pytest.raises(ValueError, match="token"):
            GitHubClient.from_environment()

    @patch("heisenberg.github_client.requests.post")
    def test_client_posts_comment_to_pr(self, mock_post: MagicMock):
        """Client should post comment via GitHub API."""
        # Given
        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"id": 12345, "html_url": "https://github.com/..."},
        )
        client = GitHubClient(token="ghp_test")
        context = GitHubContext(
            owner="testowner",
            repo="testrepo",
            sha="abc123",
            pr_number=42,
            event_name="pull_request",
        )

        # When
        result = client.post_pr_comment(context, "Test comment body")

        # Then
        assert result["id"] == 12345
        mock_post.assert_called_once()

        # Verify API call
        call_kwargs = mock_post.call_args[1]
        assert "testowner" in mock_post.call_args[0][0]
        assert "testrepo" in mock_post.call_args[0][0]
        assert "42" in mock_post.call_args[0][0]
        assert call_kwargs["json"]["body"] == "Test comment body"
        assert "Authorization" in call_kwargs["headers"]

    @patch("heisenberg.github_client.requests.post")
    def test_client_handles_api_error(self, mock_post: MagicMock):
        """Client should handle API errors gracefully."""
        # Given
        mock_post.return_value = MagicMock(
            status_code=403,
            json=lambda: {"message": "Resource not accessible"},
        )
        client = GitHubClient(token="ghp_test")
        context = GitHubContext(
            owner="owner", repo="repo", sha="abc", pr_number=1, event_name="pull_request"
        )

        # When/Then
        with pytest.raises(Exception, match="403|error|failed"):
            client.post_pr_comment(context, "Comment")

    @patch("heisenberg.github_client.requests.get")
    @patch("heisenberg.github_client.requests.patch")
    def test_client_updates_existing_comment(self, mock_patch: MagicMock, mock_get: MagicMock):
        """Client should update existing Heisenberg comment if found."""
        # Given
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {"id": 111, "body": "Some other comment"},
                {"id": 222, "body": "## Heisenberg Test Analysis\nOld content"},
            ],
        )
        mock_patch.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": 222, "html_url": "https://..."},
        )
        client = GitHubClient(token="ghp_test")
        context = GitHubContext(
            owner="owner", repo="repo", sha="abc", pr_number=1, event_name="pull_request"
        )

        # When
        result = client.post_or_update_comment(context, "## Heisenberg Test Analysis\nNew content")

        # Then
        assert result["id"] == 222
        mock_patch.assert_called_once()
        mock_get.assert_called_once()


class TestPostPrCommentHelper:
    """Test suite for post_pr_comment convenience function."""

    @patch("heisenberg.github_client.GitHubClient")
    @patch("heisenberg.github_client.GitHubContext")
    def test_post_pr_comment_creates_client_and_context(
        self, mock_context_class: MagicMock, mock_client_class: MagicMock, monkeypatch
    ):
        """Should create client and context from environment."""
        # Given
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        mock_context = MagicMock()
        mock_context.is_pull_request = True
        mock_context_class.from_environment.return_value = mock_context

        mock_client = MagicMock()
        mock_client.post_or_update_comment.return_value = {"id": 123}
        mock_client_class.from_environment.return_value = mock_client

        # When
        post_pr_comment("Test body")

        # Then
        mock_context_class.from_environment.assert_called_once()
        mock_client_class.from_environment.assert_called_once()
        mock_client.post_or_update_comment.assert_called_with(mock_context, "Test body")

    @patch("heisenberg.github_client.GitHubClient")
    @patch("heisenberg.github_client.GitHubContext")
    def test_post_pr_comment_skips_if_not_pr(
        self, mock_context_class: MagicMock, mock_client_class: MagicMock, monkeypatch
    ):
        """Should skip posting if not in PR context."""
        # Given
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        mock_context = MagicMock()
        mock_context.is_pull_request = False
        mock_context_class.from_environment.return_value = mock_context

        # When
        result = post_pr_comment("Test body")

        # Then
        assert result is None
        mock_client_class.from_environment.return_value.post_or_update_comment.assert_not_called()
