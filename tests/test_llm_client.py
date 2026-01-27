"""Tests for LLM client - TDD Red-Green-Refactor."""

from unittest.mock import MagicMock, patch

import pytest

from heisenberg.llm.client import (
    LLMClient,
    LLMClientError,
    LLMConfig,
    LLMResponse,
)


class TestLLMClientError:
    """Test suite for LLMClientError exception."""

    def test_llm_client_error_is_exception(self):
        """LLMClientError should be an Exception subclass."""
        assert issubclass(LLMClientError, Exception)

    def test_llm_client_error_stores_message(self):
        """Should store error message."""
        error = LLMClientError("API call failed")

        assert str(error) == "API call failed"

    def test_llm_client_error_can_be_raised(self):
        """Should be raisable and catchable."""
        with pytest.raises(LLMClientError, match="test error"):
            raise LLMClientError("test error")


class TestLLMConfig:
    """Test suite for LLM configuration."""

    def test_config_has_defaults(self):
        """Config should have sensible defaults."""
        # When
        config = LLMConfig()

        # Then
        assert config.model == "claude-sonnet-4-20250514"
        assert config.max_tokens == 4096
        assert config.temperature == pytest.approx(0.3)

    def test_config_accepts_custom_values(self):
        """Config should accept custom values."""
        # When
        config = LLMConfig(
            model="claude-3-opus-20240229",
            max_tokens=8192,
            temperature=0.5,
        )

        # Then
        assert config.model == "claude-3-opus-20240229"
        assert config.max_tokens == 8192
        assert config.temperature == pytest.approx(0.5)


class TestLLMClient:
    """Test suite for LLM client."""

    def test_client_initializes_with_api_key(self):
        """Client should initialize with API key."""
        # When
        client = LLMClient(api_key="test-key")

        # Then
        assert client.api_key == "test-key"

    def test_client_accepts_config(self):
        """Client should accept custom config."""
        # Given
        config = LLMConfig(max_tokens=2048)

        # When
        client = LLMClient(api_key="test-key", config=config)

        # Then
        assert client.config.max_tokens == 2048

    def test_client_from_environment(self, monkeypatch):
        """Client should read API key from environment."""
        # Given
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-api-key")

        # When
        client = LLMClient.from_environment()

        # Then
        assert client.api_key == "env-api-key"

    def test_client_raises_without_api_key(self, monkeypatch):
        """Client should raise error if no API key available."""
        # Given
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        # When/Then
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            LLMClient.from_environment()

    @patch("heisenberg.llm.client.anthropic.Anthropic")
    def test_client_sends_message(self, mock_anthropic_class: MagicMock):
        """Client should send message to Anthropic API."""
        # Given
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Test diagnosis")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        client = LLMClient(api_key="test-key")

        # When
        client.analyze("Test prompt content")

        # Then
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert "Test prompt content" in str(call_kwargs["messages"])

    @patch("heisenberg.llm.client.anthropic.Anthropic")
    def test_client_returns_llm_response(self, mock_anthropic_class: MagicMock):
        """Client should return structured LLMResponse."""
        # Given
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="AI analysis result")]
        mock_response.usage.input_tokens = 150
        mock_response.usage.output_tokens = 75
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        client = LLMClient(api_key="test-key")

        # When
        response = client.analyze("Analyze this")

        # Then
        assert isinstance(response, LLMResponse)
        assert response.content == "AI analysis result"
        assert response.input_tokens == 150
        assert response.output_tokens == 75

    @patch("heisenberg.llm.client.anthropic.Anthropic")
    def test_client_uses_system_prompt(self, mock_anthropic_class: MagicMock):
        """Client should use system prompt for context."""
        # Given
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        client = LLMClient(api_key="test-key")

        # When
        client.analyze("User prompt", system_prompt="You are a test analyst")

        # Then
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == "You are a test analyst"

    @patch("heisenberg.llm.client.anthropic.Anthropic")
    def test_client_handles_api_error(self, mock_anthropic_class: MagicMock):
        """Client should handle API errors gracefully."""
        # Given
        import anthropic

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="Rate limit exceeded",
            request=MagicMock(),
            body=None,
        )
        mock_anthropic_class.return_value = mock_client

        client = LLMClient(api_key="test-key")

        # When/Then
        with pytest.raises(Exception, match="rate|limit|error|failed"):
            client.analyze("Test prompt")


class TestLLMResponse:
    """Test suite for LLM response data model."""

    def test_response_contains_content(self):
        """Response should contain text content."""
        # When
        response = LLMResponse(
            content="Analysis result",
            input_tokens=100,
            output_tokens=50,
            model="claude-3-5-sonnet-20241022",
            provider="anthropic",
        )

        # Then
        assert response.content == "Analysis result"

    def test_response_tracks_token_usage(self):
        """Response should track token usage for cost estimation."""
        # When
        response = LLMResponse(
            content="Result",
            input_tokens=1000,
            output_tokens=500,
            model="claude-3-5-sonnet-20241022",
            provider="anthropic",
        )

        # Then
        assert response.input_tokens == 1000
        assert response.output_tokens == 500
        assert response.total_tokens == 1500

    def test_response_estimates_cost(self):
        """Response should estimate cost based on token usage."""
        # When (Claude 3.5 Sonnet pricing: $3/M input, $15/M output)
        response = LLMResponse(
            content="Result",
            input_tokens=1000,
            output_tokens=500,
            model="claude-3-5-sonnet-20241022",
            provider="anthropic",
        )

        # Then
        expected_cost = (1000 * 3 / 1_000_000) + (500 * 15 / 1_000_000)
        assert abs(response.estimated_cost - expected_cost) < 0.0001
