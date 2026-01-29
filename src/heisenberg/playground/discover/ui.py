"""CLI output formatting and Rich progress display."""

from __future__ import annotations

import json

from .models import (
    ProgressInfo,
    ProjectSource,
    SourceStatus,
)

STATUS_ICONS = {
    SourceStatus.COMPATIBLE: "+",
    SourceStatus.NO_FAILURES: "~",
    SourceStatus.HAS_ARTIFACTS: "!",
    SourceStatus.NO_ARTIFACTS: "-",
    SourceStatus.NO_FAILED_RUNS: ".",
}

STATUS_COLORS = {
    SourceStatus.COMPATIBLE: "green",
    SourceStatus.NO_FAILURES: "yellow",
    SourceStatus.HAS_ARTIFACTS: "yellow",
    SourceStatus.NO_ARTIFACTS: "red",
    SourceStatus.NO_FAILED_RUNS: "dim",
}

STATUS_LABELS = {
    SourceStatus.COMPATIBLE: "compatible",
    SourceStatus.NO_FAILURES: "tests passing",
    SourceStatus.HAS_ARTIFACTS: "has artifacts",
    SourceStatus.NO_ARTIFACTS: "no artifacts",
    SourceStatus.NO_FAILED_RUNS: "no failed runs",
}


def format_status_label(status: SourceStatus) -> str:
    """Get the human-readable label for a source status."""
    return STATUS_LABELS.get(status, status.value)


def format_size(size_bytes: int) -> str:
    """Format byte count as human-readable size (e.g., '52 MB')."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.0f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


COL_REPO = 40
COL_STATUS = 14
COL_TRAIL = 7


def format_stars(stars: int) -> str:
    """Format star count for display (e.g., 81807 → '81.8k')."""
    if stars >= 1_000_000:
        return f"{stars / 1_000_000:.1f}M"
    if stars >= 1_000:
        return f"{stars / 1_000:.1f}k"
    return str(stars)


def create_progress_display():
    """Create a Rich Progress display for tracking repo analysis.

    Returns a Progress object with spinner, description, and live elapsed timer.
    TimeElapsedColumn auto-updates during rendering — no manual refresh needed.
    """
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        transient=False,  # Keep completed tasks visible
    )


def format_progress_line(info: ProgressInfo) -> str:
    """Format a progress line for CLI output.

    Args:
        info: ProgressInfo with completion details

    Returns:
        Formatted string like "[ 3/10] + owner/repo (1.5s)"
    """
    # Status icon
    icon = "+" if info.status == "compatible" else "-"

    # Format elapsed time
    if info.elapsed_ms >= 1000:
        time_str = f"{info.elapsed_ms / 1000:.1f}s"
    else:
        time_str = f"{info.elapsed_ms}ms"

    # Base line
    line = f"[{info.completed:2}/{info.total}] {icon} {info.repo} ({time_str})"

    # Add optional message
    if info.message:
        line += f" - {info.message}"

    return line


def format_status_icon(status: SourceStatus) -> str:
    """Get the text icon for a source status."""
    return STATUS_ICONS.get(status, "?")


def format_status_color(status: SourceStatus) -> str:
    """Get the Rich color name for a source status."""
    return STATUS_COLORS.get(status, "white")


def print_source_line(
    source: ProjectSource,
    console=None,
) -> None:
    """Print a single source line with unified column layout and colors.

    Format: {icon} {repo:<COL_REPO} │ {status:<COL_STATUS} {stars:>COL_TRAIL}
    For sources with artifacts, prints indented sub-lines.
    For COMPATIBLE sources, also prints run URL sub-line.
    """
    from rich.console import Console

    if console is None:
        console = Console(highlight=False)

    icon = format_status_icon(source.status)
    color = format_status_color(source.status)
    status_label = format_status_label(source.status)
    stars_str = format_stars(source.stars)
    console.print(
        f"  [{color}]{icon}[/{color}] {source.repo:<{COL_REPO}}"
        f" [dim]\u2502[/dim] [{color}]{status_label:<{COL_STATUS}}[/{color}]"
        f" {stars_str:>{COL_TRAIL}}",
    )

    # Sub-lines for sources with artifacts
    if source.status == SourceStatus.COMPATIBLE:
        artifacts = ", ".join(source.playwright_artifacts[:3])
        console.print(f"      [dim]{artifacts}[/dim]")
        if source.run_url:
            console.print(f"      [dim]{source.run_url}[/dim]")
    elif source.status == SourceStatus.HAS_ARTIFACTS:
        artifacts = ", ".join(source.artifact_names[:3])
        console.print(f"      [dim]{artifacts}[/dim]")


def print_summary(
    sources: list[ProjectSource],
    min_stars: int,
    total_analyzed: int | None = None,
    console=None,
) -> None:
    """Print the analysis summary with colors."""
    from collections import Counter

    from rich.console import Console

    if console is None:
        console = Console(highlight=False)

    compatible_count = sum(1 for c in sources if c.compatible)
    analyzed = total_analyzed or len(sources)

    if analyzed != len(sources):
        console.print(
            f"Analyzed {analyzed} repositories, {len(sources)} with >={min_stars} stars",
        )
    else:
        console.print(f"Analyzed {len(sources)} repositories (min {min_stars} stars)")
    console.print()

    for source in sources:
        print_source_line(source, console)

    separator = "\u2550" * 70
    console.print(f"\n[dim]{separator}[/dim]")
    console.print(
        f"[green]{compatible_count} compatible[/green] / {len(sources)} listed",
    )

    # Breakdown of non-compatible statuses
    status_counts = Counter(s.status for s in sources)
    other_parts = []
    for status in SourceStatus:
        if status == SourceStatus.COMPATIBLE:
            continue
        count = status_counts.get(status, 0)
        if count > 0:
            color = format_status_color(status)
            label = format_status_label(status)
            other_parts.append(f"[{color}]{count} {label}[/{color}]")
    if other_parts:
        console.print(" \u00b7 ".join(other_parts))

    console.print(f"[dim]{separator}[/dim]\n")


def save_results(sources: list[ProjectSource], output_path: str) -> None:
    """Save results to JSON file."""
    output_data = [
        {
            "repo": c.repo,
            "stars": c.stars,
            "compatible": c.compatible,
            "status": c.status.value,
            "artifacts": c.artifact_names,
            "playwright_artifacts": c.playwright_artifacts,
            "run_id": c.run_id,
            "run_url": c.run_url,
        }
        for c in sources
    ]
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"Results saved to {output_path}")
