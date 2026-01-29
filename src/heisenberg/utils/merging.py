"""Blob report merger for Playwright sharded test reports.

Playwright blob reports contain protocol events that require merging
via `npx playwright merge-reports` to produce a standard JSON report.

This module provides functionality to:
- Extract blob files from nested ZIP artifacts
- Merge blob reports using Playwright CLI
- Return parsed JSON report for analysis
"""

from __future__ import annotations

import asyncio
import io
import json
import tempfile
import zipfile
from pathlib import Path


class BlobMergeError(Exception):
    """Exception raised when blob merge fails."""

    pass


def extract_blob_files(zip_content: bytes, max_depth: int = 3) -> list[bytes]:
    """Extract .jsonl blob files from nested ZIP structure.

    Args:
        zip_content: ZIP file content as bytes
        max_depth: Maximum nesting depth to search

    Returns:
        List of blob file contents as bytes
    """
    if max_depth <= 0:
        return []

    blob_files = []

    try:
        zip_buffer = io.BytesIO(zip_content)
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".jsonl"):
                    blob_files.append(zf.read(name))
                elif name.endswith(".zip"):
                    try:
                        nested_content = zf.read(name)
                        blob_files.extend(extract_blob_files(nested_content, max_depth - 1))
                    except (zipfile.BadZipFile, KeyError):
                        continue
    except zipfile.BadZipFile:
        pass

    return blob_files


def extract_blob_zips(zip_content: bytes) -> list[tuple[str, bytes]]:
    """Extract report-*.zip files from GitHub artifact for Playwright merge.

    Playwright's merge-reports expects the nested ZIP files (report-*.zip),
    not extracted .jsonl files.

    Args:
        zip_content: GitHub artifact ZIP content as bytes

    Returns:
        List of (filename, zip_content) tuples
    """
    blob_zips = []

    try:
        zip_buffer = io.BytesIO(zip_content)
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".zip") and "report" in name.lower():
                    try:
                        blob_zips.append((name, zf.read(name)))
                    except KeyError:
                        continue
    except zipfile.BadZipFile:
        pass

    return blob_zips


def _write_blob_files(
    blob_dir: Path,
    blob_files: list[bytes] | None,
    blob_zips: list[tuple[str, bytes]] | None,
) -> None:
    """Write blob files to a directory for Playwright merge.

    Args:
        blob_dir: Directory to write files to.
        blob_files: List of blob contents (auto-named as report-N.jsonl).
        blob_zips: List of (filename, content) tuples with explicit names.
    """
    if blob_zips:
        for filename, content in blob_zips:
            (blob_dir / filename).write_bytes(content)
    elif blob_files:
        for i, content in enumerate(blob_files):
            (blob_dir / f"report-{i}.jsonl").write_bytes(content)


async def merge_blob_reports(
    blob_files: list[bytes] | None = None,
    blob_zips: list[tuple[str, bytes]] | None = None,
    output_format: str = "json",
) -> dict | None:
    """Merge Playwright blob reports into a single JSON report.

    Uses `npx playwright merge-reports` to process blob files.
    Playwright expects the nested report-*.zip files, not extracted .jsonl.

    Args:
        blob_files: List of blob file contents (auto-named as report-N.jsonl)
        blob_zips: List of (filename, zip_content) tuples with explicit names
        output_format: Output format (json, html, etc.)

    Returns:
        Parsed JSON report or None if merge fails

    Raises:
        BlobMergeError: If npx/playwright not available or merge fails
    """
    if not blob_files and not blob_zips:
        raise BlobMergeError("No blob files provided")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        blob_dir = temp_path / "blobs"
        blob_dir.mkdir()

        _write_blob_files(blob_dir, blob_files, blob_zips)

        # Output file for JSON (avoids stdout buffer limits)
        output_file = temp_path / "merged-report.json"

        # Run playwright merge-reports with output redirected to file
        try:
            with output_file.open("w") as f:
                proc = await asyncio.create_subprocess_exec(
                    "npx",
                    "playwright",
                    "merge-reports",
                    "--reporter",
                    output_format,
                    str(blob_dir),
                    stdout=f,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=temp_dir,
                )
                try:
                    _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                except TimeoutError as e:
                    proc.kill()
                    raise BlobMergeError("Merge operation timed out") from e
        except FileNotFoundError as e:
            raise BlobMergeError(
                "npx not found. Please install Node.js and Playwright: npm install -D @playwright/test"
            ) from e

        if proc.returncode != 0:
            raise BlobMergeError(f"Merge failed: {stderr.decode() if stderr else 'Unknown error'}")

        # Read JSON from output file
        if not output_file.exists() or output_file.stat().st_size == 0:
            raise BlobMergeError("Merge completed but no output was generated")

        try:
            return json.loads(output_file.read_text())
        except json.JSONDecodeError as e:
            raise BlobMergeError(f"Failed to parse merged report: {e}") from e
