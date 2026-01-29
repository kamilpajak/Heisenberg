"""Tests for CLI output formatting and Rich progress display."""

from __future__ import annotations

from heisenberg.playground.discover.models import (
    ProgressInfo,
    SourceStatus,
)
from heisenberg.playground.discover.ui import (
    COL_STATUS,
    format_progress_line,
    format_size,
    format_stars,
    format_status_color,
    format_status_icon,
    format_status_label,
)

# =============================================================================
# PRESENTER TESTS
# =============================================================================


class TestFormatStatusIcon:
    """Tests for format_status_icon function."""

    def test_compatible_icon(self):
        """COMPATIBLE status should show plus."""
        assert format_status_icon(SourceStatus.COMPATIBLE) == "+"

    def test_no_failures_icon(self):
        """NO_FAILURES status should show tilde."""
        assert format_status_icon(SourceStatus.NO_FAILURES) == "~"

    def test_has_artifacts_icon(self):
        """HAS_ARTIFACTS status should show exclamation."""
        assert format_status_icon(SourceStatus.HAS_ARTIFACTS) == "!"

    def test_no_artifacts_icon(self):
        """NO_ARTIFACTS status should show dash."""
        assert format_status_icon(SourceStatus.NO_ARTIFACTS) == "-"

    def test_no_failed_runs_icon(self):
        """NO_FAILED_RUNS status should show dot."""
        assert format_status_icon(SourceStatus.NO_FAILED_RUNS) == "."


class TestFormatStatusColor:
    """Tests for format_status_color function."""

    def test_compatible_color(self):
        """COMPATIBLE status should be green."""
        assert format_status_color(SourceStatus.COMPATIBLE) == "green"

    def test_no_failures_color(self):
        """NO_FAILURES status should be yellow."""
        assert format_status_color(SourceStatus.NO_FAILURES) == "yellow"

    def test_has_artifacts_color(self):
        """HAS_ARTIFACTS status should be yellow."""
        assert format_status_color(SourceStatus.HAS_ARTIFACTS) == "yellow"

    def test_no_artifacts_color(self):
        """NO_ARTIFACTS status should be red."""
        assert format_status_color(SourceStatus.NO_ARTIFACTS) == "red"

    def test_no_failed_runs_color(self):
        """NO_FAILED_RUNS status should be dim."""
        assert format_status_color(SourceStatus.NO_FAILED_RUNS) == "dim"


class TestFormatStatusLabel:
    """Tests for format_status_label function."""

    def test_compatible_label(self):
        """COMPATIBLE status should return 'compatible'."""
        assert format_status_label(SourceStatus.COMPATIBLE) == "compatible"

    def test_no_failures_label(self):
        """NO_FAILURES status should return 'tests passing'."""
        assert format_status_label(SourceStatus.NO_FAILURES) == "tests passing"

    def test_has_artifacts_label(self):
        """HAS_ARTIFACTS status should return 'has artifacts'."""
        assert format_status_label(SourceStatus.HAS_ARTIFACTS) == "has artifacts"

    def test_no_artifacts_label(self):
        """NO_ARTIFACTS status should return 'no artifacts'."""
        assert format_status_label(SourceStatus.NO_ARTIFACTS) == "no artifacts"

    def test_no_failed_runs_label(self):
        """NO_FAILED_RUNS status should return 'no failed runs'."""
        assert format_status_label(SourceStatus.NO_FAILED_RUNS) == "no failed runs"

    def test_all_labels_have_spaces(self):
        """All multi-word labels should use spaces, not underscores."""
        for status in SourceStatus:
            label = format_status_label(status)
            assert "_" not in label, f"{status.name} label contains underscore: {label}"

    def test_all_labels_fit_column_width(self):
        """All labels should fit within COL_STATUS (14 chars)."""
        for status in SourceStatus:
            label = format_status_label(status)
            assert len(label) <= COL_STATUS, (
                f"{status.name} label '{label}' is {len(label)} chars, max {COL_STATUS}"
            )


class TestFormatStars:
    """Tests for format_stars function."""

    def test_small_numbers_unchanged(self):
        """Numbers under 1000 should be returned as-is."""
        assert format_stars(0) == "0"
        assert format_stars(293) == "293"
        assert format_stars(999) == "999"

    def test_thousands(self):
        """Numbers >= 1000 should use 'k' suffix with one decimal."""
        assert format_stars(1000) == "1.0k"
        assert format_stars(5962) == "6.0k"
        assert format_stars(6746) == "6.7k"
        assert format_stars(81807) == "81.8k"

    def test_millions(self):
        """Numbers >= 1M should use 'M' suffix with one decimal."""
        assert format_stars(1_000_000) == "1.0M"
        assert format_stars(2_500_000) == "2.5M"


class TestFormatSize:
    """Tests for format_size function."""

    def test_bytes(self):
        """Small values should show bytes."""
        assert format_size(0) == "0 B"
        assert format_size(512) == "512 B"

    def test_kilobytes(self):
        """Values in KB range should show KB."""
        assert format_size(1024) == "1 KB"
        assert format_size(150_000) == "146 KB"

    def test_megabytes(self):
        """Values in MB range should show MB."""
        assert format_size(1_048_576) == "1 MB"
        assert format_size(52_000_000) == "50 MB"
        assert format_size(500_000_000) == "477 MB"

    def test_gigabytes(self):
        """Values in GB range should show GB with one decimal."""
        assert format_size(1_073_741_824) == "1.0 GB"
        assert format_size(1_500_000_000) == "1.4 GB"


class TestFormatProgressLine:
    """Tests for format_progress_line function."""

    def test_format_progress_line_basic(self):
        """Should format progress line with completion order."""
        info = ProgressInfo(
            completed=3,
            total=10,
            repo="owner/repo",
            status="compatible",
            elapsed_ms=1500,
        )

        line = format_progress_line(info)

        assert "[ 3/10]" in line
        assert "owner/repo" in line
        assert "1.5s" in line or "1500" in line

    def test_format_progress_line_shows_plus_for_compatible(self):
        """Should show + for compatible repos."""
        info = ProgressInfo(
            completed=1, total=5, repo="good/repo", status="compatible", elapsed_ms=100
        )

        line = format_progress_line(info)

        assert "+" in line

    def test_format_progress_line_shows_dash_for_incompatible(self):
        """Should show - for non-compatible repos."""
        info = ProgressInfo(
            completed=1, total=5, repo="bad/repo", status="no_artifacts", elapsed_ms=100
        )

        line = format_progress_line(info)

        assert "-" in line

    def test_format_progress_line_includes_message(self):
        """Should include optional message."""
        info = ProgressInfo(
            completed=1,
            total=5,
            repo="microsoft/playwright",
            status="compatible",
            elapsed_ms=50,
            message="skipped verify",
        )

        line = format_progress_line(info)

        assert "skipped verify" in line


class TestRichProgressDisplay:
    """Tests for Rich-based progress display."""

    def test_create_progress_display_returns_rich_progress(self):
        """create_progress_display should return a Rich Progress object."""
        from heisenberg.playground.discover.ui import create_progress_display

        progress = create_progress_display()

        from rich.progress import Progress

        assert isinstance(progress, Progress)

    def test_progress_display_has_spinner_column(self):
        """Progress display should include a spinner for active tasks."""
        from heisenberg.playground.discover.ui import create_progress_display

        progress = create_progress_display()

        column_types = [type(col).__name__ for col in progress.columns]
        assert "SpinnerColumn" in column_types

    def test_progress_display_has_elapsed_column(self):
        """Progress display should include a live elapsed timer."""
        from heisenberg.playground.discover.ui import create_progress_display

        progress = create_progress_display()

        column_types = [type(col).__name__ for col in progress.columns]
        assert "TimeElapsedColumn" in column_types

    def test_progress_display_has_task_description(self):
        """Progress display should show task description."""
        from heisenberg.playground.discover.ui import create_progress_display

        progress = create_progress_display()

        column_types = [type(col).__name__ for col in progress.columns]
        assert any("Column" in t for t in column_types)
