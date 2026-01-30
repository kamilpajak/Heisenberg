"""Rich-based display component for discovery UI.

Handles all console output for the discovery process via event-based architecture.
"""

from __future__ import annotations

from collections import Counter

from rich.console import Console

from .events import (
    AnalysisCompleted,
    AnalysisProgress,
    AnalysisStarted,
    DiscoveryCompleted,
    DiscoveryEvent,
    QueryCompleted,
    SearchCompleted,
    SearchStarted,
)
from .models import SourceStatus


def format_stars(stars: int) -> str:
    """Format star count for display (e.g., 81807 -> '81.8k')."""
    if stars >= 1_000_000:
        return f"{stars / 1_000_000:.1f}M"
    if stars >= 1_000:
        return f"{stars / 1_000:.1f}k"
    return str(stars)


class DiscoveryDisplay:
    """Handles all display output for discovery process.

    Modes:
    - Default: Show search progress, compatible repos only during analysis, grouped summary
    - Verbose: Show all repos during analysis
    - Quiet: No output (for JSON mode or scripting)
    """

    def __init__(self, verbose: bool = False, quiet: bool = False):
        """Initialize display.

        Args:
            verbose: Show all repos during analysis (not just compatible)
            quiet: Suppress all output
        """
        self.verbose = verbose
        self.quiet = quiet
        self.console = Console(highlight=False)

        # State tracking
        self._stats: Counter[SourceStatus] = Counter()
        self._progress_total = 0
        self._progress_completed = 0
        self._analysis_started = False  # Track if analysis phase has begun

    def handle(self, event: DiscoveryEvent) -> None:
        """Main event dispatcher.

        Routes events to appropriate handlers based on type.
        """
        if self.quiet:
            return  # Silent mode - skip all output

        match event:
            case SearchStarted():
                self._on_search_started(event)
            case QueryCompleted():
                self._on_query_completed(event)
            case SearchCompleted():
                self._on_search_completed(event)
            case AnalysisStarted():
                self._on_analysis_started(event)
            case AnalysisProgress():
                self._on_analysis_progress(event)
            case AnalysisCompleted():
                self._on_analysis_completed(event)
            case DiscoveryCompleted():
                self._on_discovery_completed(event)

    # =========================================================================
    # SEARCH PHASE HANDLERS
    # =========================================================================

    def _on_search_started(self, event: SearchStarted) -> None:
        """Handle search started event."""
        self.console.print("[bold]Searching GitHub for Playwright repos...[/bold]")
        self.console.print()

    def _on_query_completed(self, event: QueryCompleted) -> None:
        """Handle query completed event."""
        new_str = f" [green](+{event.new_repos} new)[/green]" if event.new_repos > 0 else ""
        preview = (
            event.query_preview[:35] + "..."
            if len(event.query_preview) > 35
            else event.query_preview
        )
        self.console.print(
            f"  Query {event.query_index + 1}: "
            f"[dim]{preview}[/dim] "
            f"{event.repos_found} repos{new_str}"
        )

    def _on_search_completed(self, event: SearchCompleted) -> None:
        """Handle search completed event."""
        self.console.print()

        filter_parts = []
        if event.quarantine_skipped > 0:
            filter_parts.append(f"{event.quarantine_skipped} quarantined")
        if event.stars_filtered > 0:
            filter_parts.append(f"{event.stars_filtered} below min stars")

        filter_str = f" ({', '.join(filter_parts)})" if filter_parts else ""
        self.console.print(
            f"Found {event.total_candidates} candidates -> "
            f"analyzing [bold]{event.to_analyze}[/bold]{filter_str}"
        )
        self.console.print()

        self._progress_total = event.to_analyze

    # =========================================================================
    # ANALYSIS PHASE HANDLERS
    # =========================================================================

    def _on_analysis_started(self, event: AnalysisStarted) -> None:
        """Handle analysis started event - show progress indicator."""
        if not self._analysis_started:
            # Show one-time message when analysis phase begins
            self._analysis_started = True
            if not self.verbose:
                self.console.print(
                    f"  [dim]Analyzing {event.total} repos (this may take a while)...[/dim]"
                )
                self.console.print()

        if self.verbose:
            # In verbose mode, show which repo is being analyzed
            stars_str = format_stars(event.stars) if event.stars > 0 else "—"
            self.console.print(f"  [dim]→ {event.repo} ({stars_str}★)...[/dim]")

    def _on_analysis_progress(self, event: AnalysisProgress) -> None:
        """Handle analysis progress event."""
        # Could be used for live stage updates
        pass

    def _on_analysis_completed(self, event: AnalysisCompleted) -> None:
        """Handle analysis completed event."""
        self._progress_completed += 1
        self._stats[event.status] += 1

        if event.status == SourceStatus.COMPATIBLE:
            # Always show compatible repos immediately
            self._print_compatible_hit(event)
        elif self.verbose:
            # Show all repos in verbose mode
            self._print_repo_line(event)

    def _print_compatible_hit(self, event: AnalysisCompleted) -> None:
        """Print a highlighted compatible repo discovery."""
        stars_str = format_stars(event.stars)
        artifact = event.artifact_name or "?"
        elapsed = (
            f"{event.elapsed_ms / 1000:.1f}s"
            if event.elapsed_ms >= 1000
            else f"{event.elapsed_ms}ms"
        )

        self.console.print(
            f"  [green]✓[/green] [bold]{event.repo}[/bold]  "
            f"[dim]{stars_str}★[/dim]  "
            f"[cyan]{artifact}[/cyan]  "
            f"[dim][{elapsed}][/dim]"
        )

    def _print_repo_line(self, event: AnalysisCompleted) -> None:
        """Print a repo line for verbose mode."""
        stars_str = format_stars(event.stars)
        status_label = event.status.value.replace("_", " ")

        # Color based on status
        color = {
            SourceStatus.COMPATIBLE: "green",
            SourceStatus.NO_FAILURES: "yellow",
            SourceStatus.HAS_ARTIFACTS: "yellow",
            SourceStatus.NO_ARTIFACTS: "red",
            SourceStatus.NO_FAILED_RUNS: "dim",
            SourceStatus.UNSUPPORTED_FORMAT: "magenta",
        }.get(event.status, "white")

        icon = {
            SourceStatus.COMPATIBLE: "✓",
            SourceStatus.NO_FAILURES: "~",
            SourceStatus.HAS_ARTIFACTS: "!",
            SourceStatus.NO_ARTIFACTS: "-",
            SourceStatus.NO_FAILED_RUNS: ".",
            SourceStatus.UNSUPPORTED_FORMAT: "⚠",
        }.get(event.status, "?")

        self.console.print(
            f"  [{color}]{icon}[/{color}] {event.repo:<40} "
            f"[dim]{stars_str}★[/dim]  "
            f"[{color}]{status_label}[/{color}]"
        )

    # =========================================================================
    # SUMMARY HANDLER
    # =========================================================================

    def _on_discovery_completed(self, event: DiscoveryCompleted) -> None:
        """Handle discovery completed event - print final summary."""
        compatible_count = event.stats.get(SourceStatus.COMPATIBLE, 0)

        self.console.print()
        self.console.print("═" * 60)

        # Compatible section
        self.console.print(f"  [bold green]{compatible_count} COMPATIBLE[/bold green]")

        for source in event.results:
            if source.status == SourceStatus.COMPATIBLE:
                stars_str = format_stars(source.stars)
                self.console.print(f"    + {source.repo:<35} {stars_str:>8}★")

        # Filtered breakdown
        other_counts = []
        for status in SourceStatus:
            if status != SourceStatus.COMPATIBLE:
                count = event.stats.get(status, 0)
                if count > 0:
                    label = status.value.replace("_", " ")
                    other_counts.append(f"{count} {label}")

        if other_counts:
            self.console.print()
            self.console.print(f"  [dim]Filtered: {', '.join(other_counts)}[/dim]")

        self.console.print("═" * 60)
