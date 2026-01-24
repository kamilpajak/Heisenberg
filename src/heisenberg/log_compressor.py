"""Log compression and filtering for optimized LLM token usage."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from heisenberg.docker_logs import ContainerLogs, LogEntry

# Common noisy patterns to filter
NOISE_PATTERNS = [
    r"health\s*check",
    r"heartbeat",
    r"keep\s*alive",
    r"ping\s*pong",
    r"metrics\s*collected",
    r"^\s*$",  # Empty lines
]


@dataclass
class CompressedLogs:
    """Result of log compression."""

    logs: dict[str, ContainerLogs]
    original_lines: int
    total_lines: int
    was_truncated: bool
    filtered_patterns: list[str] = field(default_factory=list)
    deduplicated_count: int = 0

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio (compressed / original)."""
        if self.original_lines == 0:
            return 1.0
        return self.total_lines / self.original_lines

    @property
    def estimated_tokens(self) -> int:
        """Estimate token count (rough approximation: 4 chars per token)."""
        text = self.to_text()
        return len(text) // 4

    def to_text(self) -> str:
        """Convert compressed logs to text for LLM prompt."""
        lines = []

        for name, container_logs in self.logs.items():
            lines.append(f"=== Container: {name} ===")

            if not container_logs.entries:
                lines.append("(no logs)")
            else:
                for entry in container_logs.entries:
                    lines.append(str(entry))

            lines.append("")

        if self.was_truncated:
            lines.append(
                f"[Logs truncated: showing {self.total_lines} of {self.original_lines} lines]"
            )

        if self.deduplicated_count > 0:
            lines.append(f"[{self.deduplicated_count} duplicate entries collapsed]")

        return "\n".join(lines)


class LogCompressor:
    """Compresses and filters logs for efficient LLM analysis."""

    def __init__(
        self,
        max_total_lines: int = 200,
        max_lines_per_container: int = 100,
        max_tokens: int | None = None,
        focus_timestamp: datetime | None = None,
        deduplicate: bool = False,
        filter_noise: bool = False,
    ):
        """
        Initialize log compressor.

        Args:
            max_total_lines: Maximum total lines across all containers.
            max_lines_per_container: Maximum lines per container.
            max_tokens: Optional token limit (overrides line limits).
            focus_timestamp: Prioritize logs around this timestamp.
            deduplicate: Remove repeated log messages.
            filter_noise: Filter common noisy log patterns.
        """
        self.max_total_lines = max_total_lines
        self.max_lines_per_container = max_lines_per_container
        self.max_tokens = max_tokens
        self.focus_timestamp = focus_timestamp
        self.deduplicate = deduplicate
        self.filter_noise = filter_noise

        # Compile noise patterns
        self._noise_regexes = [re.compile(p, re.IGNORECASE) for p in NOISE_PATTERNS]

    def compress(self, logs: dict[str, ContainerLogs]) -> CompressedLogs:
        """
        Compress logs for LLM consumption.

        Args:
            logs: Dictionary of container logs.

        Returns:
            CompressedLogs with compressed and filtered logs.
        """
        original_lines = sum(len(container.entries) for container in logs.values())
        filtered_patterns: list[str] = []
        deduplicated_count = 0

        compressed_logs: dict[str, ContainerLogs] = {}

        for name, container_logs in logs.items():
            entries = list(container_logs.entries)

            # Step 1: Filter noise patterns
            if self.filter_noise:
                entries, patterns = self._filter_noise(entries)
                filtered_patterns.extend(patterns)

            # Step 2: Deduplicate
            if self.deduplicate:
                entries, dedup_count = self._deduplicate(entries)
                deduplicated_count += dedup_count

            # Step 3: Prioritize and truncate
            entries = self._prioritize_and_truncate(entries)

            compressed_logs[name] = ContainerLogs(
                container_name=name,
                entries=entries,
            )

        # Step 4: Enforce total limit across containers
        compressed_logs = self._enforce_total_limit(compressed_logs)

        total_lines = sum(len(c.entries) for c in compressed_logs.values())
        was_truncated = total_lines < original_lines

        result = CompressedLogs(
            logs=compressed_logs,
            original_lines=original_lines,
            total_lines=total_lines,
            was_truncated=was_truncated,
            filtered_patterns=list(set(filtered_patterns)),
            deduplicated_count=deduplicated_count,
        )

        # Step 5: Enforce token limit if specified
        if self.max_tokens:
            result = self._enforce_token_limit(result)

        return result

    def _filter_noise(self, entries: list[LogEntry]) -> tuple[list[LogEntry], list[str]]:
        """Filter out noisy log patterns."""
        filtered = []
        patterns_matched = []

        for entry in entries:
            is_noise = False
            for regex in self._noise_regexes:
                if regex.search(entry.message):
                    is_noise = True
                    patterns_matched.append(regex.pattern)
                    break

            if not is_noise:
                filtered.append(entry)

        return filtered, patterns_matched

    def _deduplicate(self, entries: list[LogEntry]) -> tuple[list[LogEntry], int]:
        """Deduplicate repeated log messages."""
        if not entries:
            return entries, 0

        message_counts: Counter[str] = Counter()
        for entry in entries:
            message_counts[entry.message] += 1

        seen_messages: set[str] = set()
        deduplicated: list[LogEntry] = []
        total_duplicates = 0

        for entry in entries:
            if entry.message in seen_messages:
                total_duplicates += 1
                continue

            seen_messages.add(entry.message)
            count = message_counts[entry.message]

            if count > 1:
                # Add marker showing repeat count
                new_entry = LogEntry(
                    timestamp=entry.timestamp,
                    message=f"{entry.message} (repeated {count}x)",
                    stream=entry.stream,
                )
                deduplicated.append(new_entry)
            else:
                deduplicated.append(entry)

        return deduplicated, total_duplicates

    def _prioritize_and_truncate(self, entries: list[LogEntry]) -> list[LogEntry]:
        """Prioritize important logs and truncate to limit."""
        if len(entries) <= self.max_lines_per_container:
            return entries

        # Score each entry for priority
        scored: list[tuple[float, int, LogEntry]] = []

        for i, entry in enumerate(entries):
            score = self._calculate_priority_score(entry, i, len(entries))
            scored.append((score, i, entry))

        # Sort by score (descending) and take top entries
        scored.sort(key=lambda x: (-x[0], x[1]))
        top_entries = scored[: self.max_lines_per_container]

        # Sort back by original order (timestamp)
        top_entries.sort(key=lambda x: x[1])

        return [entry for _, _, entry in top_entries]

    def _calculate_priority_score(self, entry: LogEntry, index: int, total: int) -> float:
        """Calculate priority score for a log entry."""
        score = 0.0

        # Stderr (errors) get higher priority
        if entry.stream == "stderr":
            score += 10.0

        # Keywords indicating errors/issues
        lower_msg = entry.message.lower()
        error_keywords = ["error", "exception", "fail", "timeout", "crash", "fatal"]
        for keyword in error_keywords:
            if keyword in lower_msg:
                score += 5.0

        # Proximity to focus timestamp
        if self.focus_timestamp:
            time_diff = abs((entry.timestamp - self.focus_timestamp).total_seconds())
            # Higher score for entries closer to focus time
            if time_diff < 10:
                score += 8.0
            elif time_diff < 30:
                score += 5.0
            elif time_diff < 60:
                score += 2.0

        # Slight preference for entries near beginning and end
        if index < total * 0.1 or index > total * 0.9:
            score += 1.0

        return score

    def _enforce_total_limit(self, logs: dict[str, ContainerLogs]) -> dict[str, ContainerLogs]:
        """Enforce total line limit across all containers."""
        total = sum(len(c.entries) for c in logs.values())

        if total <= self.max_total_lines:
            return logs

        # Calculate fair share per container
        num_containers = len(logs)
        if num_containers == 0:
            return logs

        per_container = self.max_total_lines // num_containers

        result = {}
        for name, container in logs.items():
            entries = container.entries[:per_container]
            result[name] = ContainerLogs(container_name=name, entries=entries)

        return result

    def _enforce_token_limit(self, result: CompressedLogs) -> CompressedLogs:
        """Reduce logs further if they exceed token limit."""
        while result.estimated_tokens > self.max_tokens and result.total_lines > 10:
            # Reduce each container by 20%
            new_logs = {}
            for name, container in result.logs.items():
                keep = max(1, int(len(container.entries) * 0.8))
                # Keep entries with highest priority (errors first, then edges)
                entries = container.entries
                stderr_entries = [e for e in entries if e.stream == "stderr"]
                stdout_entries = [e for e in entries if e.stream == "stdout"]

                # Prioritize stderr
                kept = stderr_entries[:keep]
                remaining = keep - len(kept)
                if remaining > 0:
                    kept.extend(stdout_entries[:remaining])

                # Sort by timestamp
                kept.sort(key=lambda e: e.timestamp)

                new_logs[name] = ContainerLogs(container_name=name, entries=kept)

            total_lines = sum(len(c.entries) for c in new_logs.values())
            result = CompressedLogs(
                logs=new_logs,
                original_lines=result.original_lines,
                total_lines=total_lines,
                was_truncated=True,
                filtered_patterns=result.filtered_patterns,
                deduplicated_count=result.deduplicated_count,
            )

        return result


def compress_logs_for_llm(
    logs: dict[str, ContainerLogs],
    max_tokens: int | None = None,
    max_lines: int = 200,
    focus_timestamp: datetime | None = None,
    deduplicate: bool = True,
    filter_noise: bool = True,
) -> CompressedLogs:
    """
    Convenience function to compress logs for LLM analysis.

    Args:
        logs: Dictionary of container logs.
        max_tokens: Optional token limit.
        max_lines: Maximum total lines.
        focus_timestamp: Prioritize logs around this timestamp.
        deduplicate: Remove repeated messages.
        filter_noise: Filter common noisy patterns.

    Returns:
        CompressedLogs ready for LLM prompt.
    """
    compressor = LogCompressor(
        max_total_lines=max_lines,
        max_tokens=max_tokens,
        focus_timestamp=focus_timestamp,
        deduplicate=deduplicate,
        filter_noise=filter_noise,
    )
    return compressor.compress(logs)
