"""Tests for backend retry logic - TDD for Phase 5."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest


class TestRetryDecorator:
    """Test suite for retry decorator."""

    def test_retry_decorator_exists(self):
        """retry_with_backoff decorator should be importable."""
        from heisenberg.backend.retry import retry_with_backoff

        assert retry_with_backoff is not None

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_first_attempt(self):
        """Function should return immediately on success."""
        from heisenberg.backend.retry import retry_with_backoff

        # Given
        mock_func = AsyncMock(return_value="success")

        @retry_with_backoff(max_retries=3)
        async def test_func():
            return await mock_func()

        # When
        result = await test_func()

        # Then
        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_retries_on_failure(self):
        """Function should retry on retryable exceptions."""
        from heisenberg.backend.retry import retry_with_backoff

        # Given
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("Connection timeout")
            return "success"

        # When
        result = await test_func()

        # Then
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_respects_max_retries(self):
        """Function should raise after max retries exceeded."""
        from heisenberg.backend.retry import retry_with_backoff

        # Given
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        async def always_fails():
            raise TimeoutError("Always fails")

        # When/Then
        with pytest.raises(TimeoutError, match="Always fails"):
            await always_fails()

    @pytest.mark.asyncio
    async def test_retry_uses_exponential_backoff(self):
        """Retry delays should increase exponentially."""
        from heisenberg.backend.retry import retry_with_backoff

        # Given
        delays = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            delays.append(delay)
            await original_sleep(0.001)  # Minimal actual sleep

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=1.0, jitter=False)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise TimeoutError("Fail")
            return "success"

        # When
        with patch("heisenberg.backend.retry.asyncio.sleep", mock_sleep):
            await test_func()

        # Then - delays should be 1.0, 2.0, 4.0 (exponential)
        assert len(delays) == 3
        assert delays[0] == pytest.approx(1.0, rel=0.1)
        assert delays[1] == pytest.approx(2.0, rel=0.1)
        assert delays[2] == pytest.approx(4.0, rel=0.1)

    @pytest.mark.asyncio
    async def test_retry_adds_jitter(self):
        """Retry delays should include jitter when enabled."""
        from heisenberg.backend.retry import retry_with_backoff

        # Given
        delays = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            delays.append(delay)
            await original_sleep(0.001)

        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=1.0, jitter=True)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise TimeoutError("Fail")
            return "success"

        # When
        with patch("heisenberg.backend.retry.asyncio.sleep", mock_sleep):
            await test_func()

        # Then - delays should have jitter (not exactly 1.0, 2.0)
        assert len(delays) == 2
        # With jitter, values should be in range [0.5*base, 1.5*base]
        assert 0.5 <= delays[0] <= 1.5
        assert 1.0 <= delays[1] <= 3.0


class TestRetryableErrors:
    """Test suite for retryable error handling."""

    @pytest.mark.asyncio
    async def test_retries_on_timeout_error(self):
        """Should retry on TimeoutError."""
        from heisenberg.backend.retry import retry_with_backoff

        # Given
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("Timeout")
            return "success"

        # When
        result = await test_func()

        # Then
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_connection_error(self):
        """Should retry on ConnectionError."""
        from heisenberg.backend.retry import retry_with_backoff

        # Given
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection refused")
            return "success"

        # When
        result = await test_func()

        # Then
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_does_not_retry_on_value_error(self):
        """Should NOT retry on ValueError (non-retryable)."""
        from heisenberg.backend.retry import retry_with_backoff

        # Given
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")

        # When/Then
        with pytest.raises(ValueError, match="Invalid input"):
            await test_func()

        assert call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_custom_retryable_exceptions(self):
        """Should allow custom retryable exceptions."""
        from heisenberg.backend.retry import retry_with_backoff

        # Given
        class CustomError(Exception):
            pass

        call_count = 0

        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            retryable_exceptions=(CustomError,),
        )
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise CustomError("Custom error")
            return "success"

        # When
        result = await test_func()

        # Then
        assert result == "success"
        assert call_count == 2


class TestRetryConfig:
    """Test suite for retry configuration in settings."""

    def test_settings_has_retry_max_retries(self):
        """Settings should have retry_max_retries field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "retry_max_retries")
        assert settings.retry_max_retries == 3  # default

    def test_settings_has_retry_base_delay(self):
        """Settings should have retry_base_delay field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "retry_base_delay")
        assert settings.retry_base_delay == 1.0  # default

    def test_settings_has_retry_max_delay(self):
        """Settings should have retry_max_delay field."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "retry_max_delay")
        assert settings.retry_max_delay == 60.0  # default


class TestRetryWithMaxDelay:
    """Test suite for max delay capping."""

    @pytest.mark.asyncio
    async def test_retry_respects_max_delay(self):
        """Retry delay should be capped at max_delay."""
        from heisenberg.backend.retry import retry_with_backoff

        # Given
        delays = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            delays.append(delay)
            await original_sleep(0.001)

        call_count = 0

        # base_delay=10, so delays would be 10, 20, 40, 80...
        # but max_delay=25 caps it
        @retry_with_backoff(
            max_retries=4, base_delay=10.0, max_delay=25.0, jitter=False
        )
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 4:
                raise TimeoutError("Fail")
            return "success"

        # When
        with patch("heisenberg.backend.retry.asyncio.sleep", mock_sleep):
            await test_func()

        # Then
        assert delays[0] == pytest.approx(10.0, rel=0.1)
        assert delays[1] == pytest.approx(20.0, rel=0.1)
        assert delays[2] == pytest.approx(25.0, rel=0.1)  # capped
        assert delays[3] == pytest.approx(25.0, rel=0.1)  # capped
