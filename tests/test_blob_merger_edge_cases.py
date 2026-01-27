"""Tests for blob_merger edge cases and error handling."""

import io
import zipfile

import pytest

from heisenberg.utils.merging import (
    BlobMergeError,
    extract_blob_files,
    extract_blob_zips,
    merge_blob_reports,
)


def create_zip_with_jsonl(jsonl_content: bytes = b'{"test": "data"}') -> bytes:
    """Create a ZIP file containing a .jsonl file."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("report.jsonl", jsonl_content)
    return buffer.getvalue()


def create_nested_zip(inner_content: bytes) -> bytes:
    """Create a ZIP file containing another ZIP file."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("nested.zip", inner_content)
    return buffer.getvalue()


def create_report_zip(name: str = "report-1.zip") -> tuple[str, bytes]:
    """Create a mock report ZIP file."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("data.jsonl", b'{"events": []}')
    return (name, buffer.getvalue())


class TestExtractBlobFiles:
    """Tests for extract_blob_files function."""

    def test_extract_jsonl_from_simple_zip(self):
        """Should extract .jsonl files from a simple ZIP."""
        zip_content = create_zip_with_jsonl(b'{"test": "value"}')

        result = extract_blob_files(zip_content)

        assert len(result) == 1
        assert result[0] == b'{"test": "value"}'

    def test_extract_from_nested_zip(self):
        """Should extract .jsonl from nested ZIP structures."""
        inner_zip = create_zip_with_jsonl(b'{"nested": "data"}')
        outer_zip = create_nested_zip(inner_zip)

        result = extract_blob_files(outer_zip)

        assert len(result) == 1
        assert result[0] == b'{"nested": "data"}'

    def test_extract_respects_max_depth(self):
        """Should stop at max_depth."""
        # Create 4 levels of nesting
        content = create_zip_with_jsonl(b'{"deep": "data"}')
        for _ in range(3):
            content = create_nested_zip(content)

        # With max_depth=2, should not find the deeply nested file
        result = extract_blob_files(content, max_depth=2)
        assert len(result) == 0

        # With max_depth=4, should find it
        result = extract_blob_files(content, max_depth=4)
        assert len(result) == 1

    def test_extract_handles_invalid_zip(self):
        """Should handle invalid ZIP content gracefully."""
        invalid_content = b"not a zip file"

        result = extract_blob_files(invalid_content)

        assert result == []

    def test_extract_handles_corrupted_nested_zip(self):
        """Should skip corrupted nested ZIPs."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("valid.jsonl", b'{"valid": "data"}')
            zf.writestr("corrupted.zip", b"not a valid zip")
        zip_content = buffer.getvalue()

        result = extract_blob_files(zip_content)

        assert len(result) == 1
        assert result[0] == b'{"valid": "data"}'

    def test_extract_multiple_jsonl_files(self):
        """Should extract multiple .jsonl files."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("report1.jsonl", b'{"file": "1"}')
            zf.writestr("report2.jsonl", b'{"file": "2"}')
            zf.writestr("other.txt", b"not jsonl")
        zip_content = buffer.getvalue()

        result = extract_blob_files(zip_content)

        assert len(result) == 2

    def test_extract_zero_max_depth(self):
        """Should return empty list with max_depth=0."""
        zip_content = create_zip_with_jsonl()

        result = extract_blob_files(zip_content, max_depth=0)

        assert result == []


class TestExtractBlobZips:
    """Tests for extract_blob_zips function."""

    def test_extract_report_zips(self):
        """Should extract report-*.zip files."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            inner_zip = io.BytesIO()
            with zipfile.ZipFile(inner_zip, "w") as inner:
                inner.writestr("data.jsonl", b"{}")
            zf.writestr("report-1.zip", inner_zip.getvalue())
            zf.writestr("report-2.zip", inner_zip.getvalue())
            zf.writestr("other.zip", inner_zip.getvalue())  # Not a report
            zf.writestr("data.txt", b"not a zip")
        zip_content = buffer.getvalue()

        result = extract_blob_zips(zip_content)

        assert len(result) == 2
        assert all("report" in name.lower() for name, _ in result)

    def test_extract_handles_invalid_zip(self):
        """Should handle invalid ZIP content gracefully."""
        invalid_content = b"not a zip file"

        result = extract_blob_zips(invalid_content)

        assert result == []

    def test_extract_case_insensitive_report(self):
        """Should match 'report' case-insensitively."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            inner_zip = io.BytesIO()
            with zipfile.ZipFile(inner_zip, "w") as inner:
                inner.writestr("data.jsonl", b"{}")
            zf.writestr("Report-Chrome.zip", inner_zip.getvalue())
            zf.writestr("REPORT-Firefox.zip", inner_zip.getvalue())
        zip_content = buffer.getvalue()

        result = extract_blob_zips(zip_content)

        assert len(result) == 2


class TestMergeBlobReports:
    """Tests for merge_blob_reports function."""

    @pytest.mark.asyncio
    async def test_merge_raises_error_when_no_files(self):
        """Should raise error when no blob files provided."""
        with pytest.raises(BlobMergeError, match="No blob files"):
            await merge_blob_reports()

    @pytest.mark.asyncio
    async def test_merge_raises_error_for_empty_lists(self):
        """Should raise error for empty blob lists."""
        with pytest.raises(BlobMergeError, match="No blob files"):
            await merge_blob_reports(blob_files=[], blob_zips=[])


class TestBlobMergeError:
    """Tests for BlobMergeError exception."""

    def test_blob_merge_error_is_exception(self):
        """Should be a proper exception."""
        error = BlobMergeError("Merge failed")

        assert isinstance(error, Exception)
        assert str(error) == "Merge failed"

    def test_blob_merge_error_with_cause(self):
        """Should support exception chaining."""
        cause = ValueError("Original error")
        error = BlobMergeError("Merge failed")
        error.__cause__ = cause

        assert error.__cause__ == cause
