"""GitHub Actions job logs processor.

This module extracts relevant log snippets from GitHub Actions job logs
to enhance AI-powered failure diagnosis. It filters logs intelligently
to include only error-relevant context, avoiding prompt bloat.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LogSnippet:
    """A snippet of log content with context."""

    content: str
    line_number: int
    keyword: str

    def format_for_prompt(self) -> str:
        """Format snippet for inclusion in AI prompt."""
        lines = self.content.strip().split("\n")
        formatted_lines = []
        for i, line in enumerate(lines):
            actual_line = self.line_number + i
            formatted_lines.append(f"[LINE {actual_line}] {line}")
        return "\n".join(formatted_lines)


@dataclass
class JobLogsProcessor:
    """Processor for extracting relevant snippets from job logs."""

    # Keywords that indicate error-relevant content
    error_keywords: list[str] = field(
        default_factory=lambda: [
            "[error]",
            "error:",
            "Error:",
            "ERROR",
            "exception",
            "Exception",
            "FAIL",
            "Failed",
            "failed",
            "timeout",
            "Timeout",
            "TimeoutError",
            "AssertionError",
            "NullPointerException",
            "TypeError",
            "ReferenceError",
            "##[error]",
        ]
    )

    # Number of lines to include before error
    context_before: int = 5

    # Number of lines to include after error
    context_after: int = 10

    # Maximum total lines to extract (to prevent prompt bloat)
    max_total_lines: int = 200

    def extract_snippets(
        self,
        log_content: str,
        filter_tests: list[str] | None = None,
    ) -> list[LogSnippet]:
        """Extract relevant snippets from log content.

        Args:
            log_content: Raw job log content.
            filter_tests: Optional list of test names to filter by.
                Only snippets mentioning these tests will be included.

        Returns:
            List of LogSnippet objects with error-relevant content.
        """
        lines = log_content.split("\n")
        error_line_indices: list[tuple[int, str]] = []

        # Find all lines containing error keywords
        for i, line in enumerate(lines):
            for keyword in self.error_keywords:
                if keyword.lower() in line.lower():
                    error_line_indices.append((i, keyword))
                    break

        if not error_line_indices:
            return []

        # Build snippet regions (with context)
        regions: list[tuple[int, int, str]] = []
        for line_idx, keyword in error_line_indices:
            start = max(0, line_idx - self.context_before)
            end = min(len(lines), line_idx + self.context_after + 1)
            regions.append((start, end, keyword))

        # Merge overlapping regions
        merged_regions = self._merge_regions(regions)

        # Extract snippets
        snippets: list[LogSnippet] = []
        total_lines = 0

        for start, end, keyword in merged_regions:
            if total_lines >= self.max_total_lines:
                break

            # Calculate how many lines we can include
            available_lines = self.max_total_lines - total_lines
            actual_end = min(end, start + available_lines)

            snippet_lines = lines[start:actual_end]
            snippet_content = "\n".join(snippet_lines)

            # Apply test name filter if provided
            if filter_tests:
                if not any(test in snippet_content for test in filter_tests):
                    continue

            snippets.append(
                LogSnippet(
                    content=snippet_content,
                    line_number=start + 1,  # 1-indexed for human readability
                    keyword=keyword,
                )
            )
            total_lines += len(snippet_lines)

        return snippets

    def _merge_regions(
        self,
        regions: list[tuple[int, int, str]],
    ) -> list[tuple[int, int, str]]:
        """Merge overlapping regions.

        Args:
            regions: List of (start, end, keyword) tuples.

        Returns:
            Merged list of regions.
        """
        if not regions:
            return []

        # Sort by start index
        sorted_regions = sorted(regions, key=lambda r: r[0])
        merged: list[tuple[int, int, str]] = []

        current_start, current_end, current_keyword = sorted_regions[0]

        for start, end, keyword in sorted_regions[1:]:
            if start <= current_end:
                # Overlapping - extend current region
                current_end = max(current_end, end)
            else:
                # No overlap - save current and start new
                merged.append((current_start, current_end, current_keyword))
                current_start, current_end, current_keyword = start, end, keyword

        # Don't forget the last region
        merged.append((current_start, current_end, current_keyword))

        return merged

    def format_for_prompt(self, snippets: list[LogSnippet]) -> str:
        """Format snippets for inclusion in AI prompt.

        Args:
            snippets: List of LogSnippet objects.

        Returns:
            Formatted string suitable for AI prompt.
        """
        if not snippets:
            return ""

        parts = ["### Relevant Job Log Snippets:"]
        for snippet in snippets:
            parts.append("")
            parts.append(snippet.format_for_prompt())

        return "\n".join(parts)
