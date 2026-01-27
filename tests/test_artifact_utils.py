"""Tests for artifact_utils module."""

from heisenberg.utils.artifacts import extract_spec_file_from_path, extract_test_name_from_path


class TestExtractTestNameFromPath:
    """Tests for extract_test_name_from_path function."""

    def test_extract_test_name_from_trace_path(self):
        """Test extraction from trace.zip path."""
        path_parts = ["test-results", "login-test", "trace.zip"]
        result = extract_test_name_from_path(path_parts, file_suffix="trace.zip")
        assert result == "login-test"

    def test_extract_test_name_from_screenshot_path(self):
        """Test extraction from screenshot path."""
        path_parts = ["test-results", "checkout-test", "screenshot.png"]
        result = extract_test_name_from_path(path_parts)
        assert result == "checkout-test"

    def test_extract_test_name_from_jpeg_path(self):
        """Test extraction from JPEG screenshot path."""
        path_parts = ["data", "results", "my-test", "failure.jpg"]
        result = extract_test_name_from_path(path_parts)
        assert result == "my-test"

    def test_extract_test_name_nested_path(self):
        """Test extraction from deeply nested path."""
        path_parts = [
            "playwright-report",
            "data",
            "test-results",
            "chromium",
            "tests",
            "login.spec.ts",
            "should-login-successfully",
            "trace.zip",
        ]
        result = extract_test_name_from_path(path_parts, file_suffix="trace.zip")
        assert result == "should-login-successfully"

    def test_extract_test_name_returns_unknown_when_not_found(self):
        """Test fallback to unknown-test."""
        path_parts = ["trace.zip"]
        result = extract_test_name_from_path(path_parts, file_suffix="trace.zip")
        assert result == "unknown-test"

    def test_extract_test_name_empty_path(self):
        """Test with empty path."""
        result = extract_test_name_from_path([])
        assert result == "unknown-test"


class TestExtractSpecFileFromPath:
    """Tests for extract_spec_file_from_path function."""

    def test_extract_spec_file(self):
        """Test extraction of .spec.ts file."""
        path_parts = ["tests", "e2e", "login.spec.ts", "test-name", "trace.zip"]
        result = extract_spec_file_from_path(path_parts)
        assert result == "login.spec.ts"

    def test_extract_test_file(self):
        """Test extraction of .test.js file."""
        path_parts = ["src", "__tests__", "auth.test.js", "should-work"]
        result = extract_spec_file_from_path(path_parts)
        assert result == "auth.test.js"

    def test_extract_spec_file_with_multiple_matches(self):
        """Test that first match is returned."""
        path_parts = ["api.spec.ts", "unit.test.ts"]
        result = extract_spec_file_from_path(path_parts)
        assert result == "api.spec.ts"

    def test_extract_spec_file_returns_unknown(self):
        """Test fallback when no spec file found."""
        path_parts = ["test-results", "some-test", "trace.zip"]
        result = extract_spec_file_from_path(path_parts)
        assert result == "unknown-file"

    def test_extract_spec_file_empty_path(self):
        """Test with empty path."""
        result = extract_spec_file_from_path([])
        assert result == "unknown-file"
