"""Tests for log compression/filtering module - TDD Red-Green-Refactor."""

from datetime import UTC, datetime, timedelta

import pytest

from heisenberg.integrations.docker import ContainerLogs, LogEntry
from heisenberg.utils.compression import (
    CompressedLogs,
    LogCompressor,
    compress_logs_for_llm,
)


class TestLogCompressor:
    """Test suite for LogCompressor class."""

    def test_compressor_initializes_with_defaults(self):
        """Compressor should have sensible defaults."""
        # When
        compressor = LogCompressor()

        # Then
        assert compressor.max_total_lines > 0
        assert compressor.max_lines_per_container > 0

    def test_compressor_accepts_custom_limits(self):
        """Compressor should accept custom line limits."""
        # When
        compressor = LogCompressor(
            max_total_lines=100,
            max_lines_per_container=50,
        )

        # Then
        assert compressor.max_total_lines == 100
        assert compressor.max_lines_per_container == 50

    def test_compressor_accepts_token_limit(self):
        """Compressor should accept token limit."""
        # When
        compressor = LogCompressor(max_tokens=4000)

        # Then
        assert compressor.max_tokens == 4000

    def test_compress_returns_compressed_logs(self, sample_logs: dict[str, ContainerLogs]):
        """Compressor should return CompressedLogs object."""
        # Given
        compressor = LogCompressor()

        # When
        result = compressor.compress(sample_logs)

        # Then
        assert isinstance(result, CompressedLogs)

    def test_compress_preserves_small_logs(self, sample_logs: dict[str, ContainerLogs]):
        """Compressor should preserve logs that fit within limits."""
        # Given
        compressor = LogCompressor(max_total_lines=1000)

        # When
        result = compressor.compress(sample_logs)

        # Then
        assert result.total_lines == sum(len(logs.entries) for logs in sample_logs.values())
        assert not result.was_truncated

    def test_compress_truncates_large_logs(self, verbose_logs: dict[str, ContainerLogs]):
        """Compressor should truncate logs exceeding limits."""
        # Given
        compressor = LogCompressor(max_total_lines=20, max_lines_per_container=10)

        # When
        result = compressor.compress(verbose_logs)

        # Then
        assert result.total_lines <= 20
        assert result.was_truncated

    def test_compress_prioritizes_error_logs(self, mixed_logs: dict[str, ContainerLogs]):
        """Compressor should prioritize stderr over stdout."""
        # Given
        compressor = LogCompressor(max_lines_per_container=5)

        # When
        result = compressor.compress(mixed_logs)

        # Then
        # Error logs should be preserved
        api_logs = result.logs.get("api")
        assert api_logs is not None
        error_count = sum(1 for e in api_logs.entries if e.stream == "stderr")
        assert error_count > 0

    def test_compress_preserves_logs_around_timestamp(self, verbose_logs: dict[str, ContainerLogs]):
        """Compressor should preserve logs around a focus timestamp."""
        # Given
        focus_time = datetime(2024, 1, 15, 10, 30, 50, tzinfo=UTC)
        compressor = LogCompressor(
            max_lines_per_container=10,
            focus_timestamp=focus_time,
        )

        # When
        result = compressor.compress(verbose_logs)

        # Then
        # Should have entries around the focus time
        api_logs = result.logs.get("api")
        assert api_logs is not None
        times = [e.timestamp for e in api_logs.entries]
        # At least some entries should be near focus time
        near_focus = [t for t in times if abs((t - focus_time).total_seconds()) < 30]
        assert len(near_focus) > 0

    def test_compress_deduplicates_repeated_messages(
        self, logs_with_duplicates: dict[str, ContainerLogs]
    ):
        """Compressor should deduplicate repeated log messages."""
        # Given
        compressor = LogCompressor(deduplicate=True)

        # When
        result = compressor.compress(logs_with_duplicates)

        # Then
        api_logs = result.logs.get("api")
        assert api_logs is not None
        # Should have fewer entries due to deduplication
        messages = [e.message for e in api_logs.entries]
        # Check for dedup marker
        assert any("repeated" in m.lower() or "x" in m for m in messages) or len(messages) < 50

    def test_compress_filters_noisy_patterns(self, noisy_logs: dict[str, ContainerLogs]):
        """Compressor should filter out common noisy log patterns."""
        # Given
        compressor = LogCompressor(filter_noise=True)

        # When
        result = compressor.compress(noisy_logs)

        # Then
        api_logs = result.logs.get("api")
        assert api_logs is not None
        messages = [e.message.lower() for e in api_logs.entries]
        # Noisy patterns should be filtered
        assert not any("health check" in m for m in messages)
        assert not any("heartbeat" in m for m in messages)


class TestCompressedLogs:
    """Test suite for CompressedLogs data model."""

    def test_compressed_logs_has_logs(self, sample_logs: dict[str, ContainerLogs]):
        """CompressedLogs should contain the compressed logs."""
        # When
        compressed = CompressedLogs(
            logs=sample_logs,
            original_lines=100,
            total_lines=50,
            was_truncated=True,
        )

        # Then
        assert compressed.logs == sample_logs

    def test_compressed_logs_tracks_statistics(self):
        """CompressedLogs should track compression statistics."""
        # When
        compressed = CompressedLogs(
            logs={},
            original_lines=500,
            total_lines=100,
            was_truncated=True,
        )

        # Then
        assert compressed.original_lines == 500
        assert compressed.total_lines == 100
        assert compressed.compression_ratio == pytest.approx(0.2)

    def test_compressed_logs_to_text(self, sample_logs: dict[str, ContainerLogs]):
        """CompressedLogs should convert to text for LLM prompt."""
        # Given
        compressed = CompressedLogs(
            logs=sample_logs,
            original_lines=10,
            total_lines=10,
            was_truncated=False,
        )

        # When
        text = compressed.to_text()

        # Then
        assert isinstance(text, str)
        assert "api" in text.lower()

    def test_compressed_logs_estimates_tokens(self, sample_logs: dict[str, ContainerLogs]):
        """CompressedLogs should estimate token count."""
        # Given
        compressed = CompressedLogs(
            logs=sample_logs,
            original_lines=10,
            total_lines=10,
            was_truncated=False,
        )

        # When
        tokens = compressed.estimated_tokens

        # Then
        assert tokens > 0


class TestConvenienceFunction:
    """Test suite for compress_logs_for_llm helper."""

    def test_compress_logs_for_llm_returns_compressed(self, sample_logs: dict[str, ContainerLogs]):
        """Helper should return CompressedLogs."""
        # When
        result = compress_logs_for_llm(sample_logs)

        # Then
        assert isinstance(result, CompressedLogs)

    def test_compress_logs_for_llm_accepts_options(self, verbose_logs: dict[str, ContainerLogs]):
        """Helper should accept compression options."""
        # When
        result = compress_logs_for_llm(
            verbose_logs,
            max_tokens=1000,
            focus_timestamp=datetime(2024, 1, 15, 10, 30, 50, tzinfo=UTC),
        )

        # Then
        assert result.estimated_tokens <= 1500  # Some buffer


# Fixtures


@pytest.fixture
def sample_logs() -> dict[str, ContainerLogs]:
    """Small sample logs that fit within limits."""
    return {
        "api": ContainerLogs(
            container_name="api",
            entries=[
                LogEntry(
                    timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                    message="Server started on port 3000",
                    stream="stdout",
                ),
                LogEntry(
                    timestamp=datetime(2024, 1, 15, 10, 30, 5, tzinfo=UTC),
                    message="Database connection error: timeout",
                    stream="stderr",
                ),
            ],
        )
    }


@pytest.fixture
def verbose_logs() -> dict[str, ContainerLogs]:
    """Verbose logs for truncation testing."""
    base_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    entries = [
        LogEntry(
            timestamp=base_time + timedelta(seconds=i),
            message=f"Log entry {i}: Processing request batch #{i}",
            stream="stdout",
        )
        for i in range(100)
    ]
    return {
        "api": ContainerLogs(container_name="api", entries=entries),
    }


@pytest.fixture
def mixed_logs() -> dict[str, ContainerLogs]:
    """Logs with mixed stdout/stderr for priority testing."""
    base_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    entries = []

    # Add stdout entries
    for i in range(20):
        entries.append(
            LogEntry(
                timestamp=base_time + timedelta(seconds=i),
                message=f"INFO: Processing item {i}",
                stream="stdout",
            )
        )

    # Add stderr entries (errors)
    for i in range(5):
        entries.append(
            LogEntry(
                timestamp=base_time + timedelta(seconds=i + 10),
                message=f"ERROR: Failed to process item {i}",
                stream="stderr",
            )
        )

    return {
        "api": ContainerLogs(container_name="api", entries=entries),
    }


@pytest.fixture
def logs_with_duplicates() -> dict[str, ContainerLogs]:
    """Logs with repeated messages for deduplication testing."""
    base_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    entries = []

    # Add many duplicate messages
    for i in range(50):
        entries.append(
            LogEntry(
                timestamp=base_time + timedelta(seconds=i),
                message="Connection retry attempt failed",
                stream="stderr",
            )
        )

    # Add some unique messages
    entries.append(
        LogEntry(
            timestamp=base_time + timedelta(seconds=60),
            message="Finally connected to database",
            stream="stdout",
        )
    )

    return {
        "api": ContainerLogs(container_name="api", entries=entries),
    }


@pytest.fixture
def noisy_logs() -> dict[str, ContainerLogs]:
    """Logs with common noisy patterns."""
    base_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    entries = [
        LogEntry(base_time + timedelta(seconds=0), "Health check passed", "stdout"),
        LogEntry(base_time + timedelta(seconds=1), "Heartbeat sent", "stdout"),
        LogEntry(base_time + timedelta(seconds=2), "Health check passed", "stdout"),
        LogEntry(base_time + timedelta(seconds=3), "Heartbeat sent", "stdout"),
        LogEntry(base_time + timedelta(seconds=4), "ERROR: Database timeout", "stderr"),
        LogEntry(base_time + timedelta(seconds=5), "Health check passed", "stdout"),
        LogEntry(base_time + timedelta(seconds=6), "Request processed successfully", "stdout"),
    ]
    return {
        "api": ContainerLogs(container_name="api", entries=entries),
    }
