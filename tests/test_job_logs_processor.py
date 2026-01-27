"""Tests for GitHub Actions job logs processor.

These tests verify that Heisenberg can fetch and extract relevant
log snippets from GitHub Actions job logs to improve failure diagnosis.
"""

from __future__ import annotations

from heisenberg.parsers.job_logs import JobLogsProcessor, LogSnippet


class TestLogSnippetExtraction:
    """Tests for extracting relevant snippets from job logs."""

    def test_extract_snippet_around_error_keyword(self):
        """Extract context around [error] keyword."""
        log_content = """
[2024-01-15T10:00:00Z] Starting test suite...
[2024-01-15T10:00:01Z] Running test_login_success
[2024-01-15T10:00:02Z] Test passed
[2024-01-15T10:00:03Z] Running test_login_failure
[2024-01-15T10:00:04Z] [error] Expected status 401 but got 200
[2024-01-15T10:00:05Z] at AuthTests.testLoginFailure(AuthTests.java:42)
[2024-01-15T10:00:06Z] Test failed
[2024-01-15T10:00:07Z] Running test_logout
[2024-01-15T10:00:08Z] Test passed
""".strip()

        processor = JobLogsProcessor()
        snippets = processor.extract_snippets(log_content)

        assert len(snippets) >= 1
        error_snippet = snippets[0]
        assert "Expected status 401 but got 200" in error_snippet.content
        # Line number is the start of the snippet (with context)
        assert error_snippet.line_number >= 1

    def test_extract_snippet_around_exception(self):
        """Extract context around exception stack trace."""
        log_content = """
[2024-01-15T10:00:00Z] Connecting to database...
[2024-01-15T10:00:01Z] Connection established
[2024-01-15T10:00:02Z] Running query...
[2024-01-15T10:00:03Z] java.lang.NullPointerException: Cannot invoke method on null
[2024-01-15T10:00:04Z]     at com.example.Service.process(Service.java:42)
[2024-01-15T10:00:05Z]     at com.example.Handler.handle(Handler.java:15)
[2024-01-15T10:00:06Z] Query failed
[2024-01-15T10:00:07Z] Closing connection
""".strip()

        processor = JobLogsProcessor()
        snippets = processor.extract_snippets(log_content)

        assert len(snippets) >= 1
        assert "NullPointerException" in snippets[0].content

    def test_extract_snippet_around_timeout(self):
        """Extract context around timeout errors."""
        log_content = """
[2024-01-15T10:00:00Z] Waiting for element...
[2024-01-15T10:00:01Z] Element not found, retrying...
[2024-01-15T10:00:02Z] Element not found, retrying...
[2024-01-15T10:00:03Z] TimeoutError: Waiting for selector ".submit-btn" timed out
[2024-01-15T10:00:04Z] Test failed
""".strip()

        processor = JobLogsProcessor()
        snippets = processor.extract_snippets(log_content)

        assert len(snippets) >= 1
        assert "TimeoutError" in snippets[0].content

    def test_extract_multiple_snippets(self):
        """Extract multiple error snippets when far apart."""
        # Create log with errors far enough apart to not merge
        lines = ["Line " + str(i) for i in range(50)]
        lines[10] = "[error] First error occurred"
        lines[40] = "[error] Second error occurred"
        log_content = "\n".join(lines)

        processor = JobLogsProcessor(context_before=3, context_after=3)
        snippets = processor.extract_snippets(log_content)

        assert len(snippets) == 2
        assert "First error" in snippets[0].content
        assert "Second error" in snippets[1].content

    def test_context_lines_before_and_after(self):
        """Include context lines before and after error."""
        lines = [f"Line {i}" for i in range(20)]
        lines[10] = "[error] The actual error message"
        log_content = "\n".join(lines)

        processor = JobLogsProcessor(context_before=3, context_after=2)
        snippets = processor.extract_snippets(log_content)

        assert len(snippets) == 1
        snippet = snippets[0]
        # Should include lines 7-12 (3 before, error line, 2 after)
        assert "Line 7" in snippet.content
        assert "Line 8" in snippet.content
        assert "Line 9" in snippet.content
        assert "[error]" in snippet.content
        assert "Line 11" in snippet.content
        assert "Line 12" in snippet.content

    def test_no_snippets_for_clean_log(self):
        """Return empty list when no errors in log."""
        log_content = """
[2024-01-15T10:00:00Z] Starting tests...
[2024-01-15T10:00:01Z] Test 1 passed
[2024-01-15T10:00:02Z] Test 2 passed
[2024-01-15T10:00:03Z] All tests completed successfully
""".strip()

        processor = JobLogsProcessor()
        snippets = processor.extract_snippets(log_content)

        assert len(snippets) == 0

    def test_deduplicate_overlapping_snippets(self):
        """Merge overlapping snippet regions."""
        log_content = """
Line 1
Line 2
[error] First error
[error] Second error immediately after
Line 5
Line 6
""".strip()

        processor = JobLogsProcessor(context_before=1, context_after=1)
        snippets = processor.extract_snippets(log_content)

        # Should merge into single snippet since they overlap
        assert len(snippets) == 1
        assert "First error" in snippets[0].content
        assert "Second error" in snippets[0].content


class TestLogSnippetFiltering:
    """Tests for filtering snippets by test names."""

    def test_filter_by_failed_test_name(self):
        """Filter snippets to those mentioning specific test."""
        # Create log with errors far apart so they don't merge
        lines = ["Filler line " + str(i) for i in range(50)]
        lines[10] = "[error] testLoginFailure: Expected 401 but got 200"
        lines[40] = "[error] testLogout: Session not found"
        log_content = "\n".join(lines)

        processor = JobLogsProcessor(context_before=2, context_after=2)
        snippets = processor.extract_snippets(
            log_content,
            filter_tests=["testLoginFailure"],
        )

        assert len(snippets) == 1
        assert "testLoginFailure" in snippets[0].content

    def test_filter_multiple_test_names(self):
        """Filter by multiple test names."""
        # Create log with errors far apart
        lines = ["Filler " + str(i) for i in range(60)]
        lines[10] = "[error] testA: Error A"
        lines[30] = "[error] testB: Error B"
        lines[50] = "[error] testC: Error C"
        log_content = "\n".join(lines)

        processor = JobLogsProcessor(context_before=2, context_after=2)
        snippets = processor.extract_snippets(
            log_content,
            filter_tests=["testA", "testC"],
        )

        assert len(snippets) == 2


class TestLogSnippetDataclass:
    """Tests for LogSnippet dataclass."""

    def test_snippet_properties(self):
        """LogSnippet should have required properties."""
        snippet = LogSnippet(
            content="Error content here",
            line_number=42,
            keyword="[error]",
        )

        assert snippet.content == "Error content here"
        assert snippet.line_number == 42
        assert snippet.keyword == "[error]"

    def test_snippet_to_string(self):
        """LogSnippet should format nicely for prompts."""
        snippet = LogSnippet(
            content="Connection refused",
            line_number=100,
            keyword="error",
        )

        formatted = snippet.format_for_prompt()

        assert "[LINE 100]" in formatted
        assert "Connection refused" in formatted


class TestJobLogsProcessorIntegration:
    """Integration tests for job logs processing."""

    def test_process_real_world_log_format(self):
        """Process log in GitHub Actions format."""
        log_content = """
2024-01-15T10:00:00.0000000Z ##[group]Run npm test
2024-01-15T10:00:01.0000000Z npm test
2024-01-15T10:00:02.0000000Z ##[endgroup]
2024-01-15T10:00:03.0000000Z
2024-01-15T10:00:04.0000000Z > project@1.0.0 test
2024-01-15T10:00:05.0000000Z > jest
2024-01-15T10:00:06.0000000Z
2024-01-15T10:00:07.0000000Z PASS src/utils.test.js
2024-01-15T10:00:08.0000000Z FAIL src/auth.test.js
2024-01-15T10:00:09.0000000Z   ● Auth › should reject invalid password
2024-01-15T10:00:10.0000000Z
2024-01-15T10:00:11.0000000Z     expect(received).toBe(expected)
2024-01-15T10:00:12.0000000Z
2024-01-15T10:00:13.0000000Z     Expected: 401
2024-01-15T10:00:14.0000000Z     Received: 200
2024-01-15T10:00:15.0000000Z
2024-01-15T10:00:16.0000000Z       at Object.<anonymous> (src/auth.test.js:42:19)
2024-01-15T10:00:17.0000000Z
2024-01-15T10:00:18.0000000Z ##[error]Process completed with exit code 1.
""".strip()

        processor = JobLogsProcessor()
        snippets = processor.extract_snippets(log_content)

        assert len(snippets) >= 1
        # Should capture the FAIL and assertion error
        combined = " ".join(s.content for s in snippets)
        assert "FAIL" in combined or "error" in combined.lower()

    def test_max_total_lines_limit(self):
        """Limit total extracted lines to prevent prompt bloat."""
        # Create log with many errors
        lines = []
        for i in range(100):
            lines.append(f"[error] Error number {i}")

        log_content = "\n".join(lines)

        processor = JobLogsProcessor(max_total_lines=50)
        snippets = processor.extract_snippets(log_content)

        total_lines = sum(len(s.content.split("\n")) for s in snippets)
        assert total_lines <= 50

    def test_format_snippets_for_prompt(self):
        """Format all snippets for AI prompt."""
        log_content = """
[error] First error message
[error] Second error message
""".strip()

        processor = JobLogsProcessor()
        snippets = processor.extract_snippets(log_content)
        formatted = processor.format_for_prompt(snippets)

        assert "### Relevant Job Log Snippets:" in formatted
        assert "First error" in formatted
        assert "Second error" in formatted
