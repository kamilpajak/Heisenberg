"""Shared utilities for Playwright artifact parsing.

This module contains common functions used by both trace_analyzer
and screenshot_analyzer for extracting test metadata from artifact paths.
"""

from __future__ import annotations


def extract_test_name_from_path(path_parts: list[str], file_suffix: str | None = None) -> str:
    """Extract test name from artifact path parts.

    For trace files, looks for the parent directory of trace.zip.
    For screenshots, looks for the parent directory of image files.

    Args:
        path_parts: List of path components from artifact path.
        file_suffix: Optional suffix to match (e.g., "trace.zip", ".png").

    Returns:
        Extracted test name or "unknown-test" if not found.
    """
    for i, part in enumerate(path_parts):
        part_lower = part.lower()

        # Check for trace.zip
        if file_suffix and part_lower.endswith(file_suffix.lower()):
            if i > 0:
                return path_parts[i - 1]
            continue

        # Check for image files
        if part.endswith((".png", ".jpg", ".jpeg")) and i > 0:
            return path_parts[i - 1]

    return "unknown-test"


def extract_spec_file_from_path(path_parts: list[str]) -> str:
    """Extract spec/test file path from artifact path parts.

    Looks for path components containing .spec. or .test. patterns
    which indicate Playwright/Jest test files.

    Args:
        path_parts: List of path components from artifact path.

    Returns:
        Extracted file path or "unknown-file" if not found.
    """
    for part in path_parts:
        if ".spec." in part or ".test." in part:
            return part
    return "unknown-file"
