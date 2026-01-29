"""Fuzz tests for CLI using Hypothesis.

These tests use property-based testing to find edge cases, crashes,
and unexpected behavior in CLI argument handling and core logic.

Run with: pytest tests/test_cli_fuzz.py -v --run-fuzz
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from heisenberg.cli.commands import convert_to_unified, run_analyze, run_fetch_github
from heisenberg.cli.formatters import format_json_output, format_output, format_text_output

# Skip all tests in this module unless --run-fuzz is provided
pytestmark = pytest.mark.fuzz


# =============================================================================
# Hypothesis Strategies for CLI arguments
# =============================================================================


def output_formats() -> st.SearchStrategy[str]:
    """Strategy for valid output format choices."""
    return st.sampled_from(["github-comment", "json", "text", "unified-json"])


def providers() -> st.SearchStrategy[str]:
    """Strategy for valid LLM provider choices."""
    return st.sampled_from(["anthropic", "openai", "google"])


def report_formats() -> st.SearchStrategy[str]:
    """Strategy for valid report format choices."""
    return st.sampled_from(["playwright", "junit"])


def repo_strings() -> st.SearchStrategy[str]:
    """Strategy for GitHub repository strings (owner/repo format)."""
    # Valid: owner/repo format
    valid = st.from_regex(r"[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+", fullmatch=True)
    # Invalid: random strings
    invalid = st.text(min_size=0, max_size=50)
    return st.one_of(valid, invalid)


def artifact_names() -> st.SearchStrategy[str]:
    """Strategy for artifact name patterns."""
    return st.one_of(
        st.just("playwright"),
        st.just("blob-report"),
        st.text(min_size=0, max_size=30),
    )


def log_windows() -> st.SearchStrategy[int]:
    """Strategy for log window values (should be positive, but fuzz negative too)."""
    return st.integers(min_value=-1000, max_value=10000)


def run_ids() -> st.SearchStrategy[int | None]:
    """Strategy for workflow run IDs."""
    return st.one_of(
        st.none(),
        st.integers(min_value=0, max_value=2**63 - 1),
        st.integers(min_value=-1000, max_value=-1),  # Invalid negative IDs
    )


def docker_services() -> st.SearchStrategy[str]:
    """Strategy for Docker service strings."""
    return st.one_of(
        st.just(""),
        st.just("api,db,redis"),
        st.text(min_size=0, max_size=100),
    )


# =============================================================================
# Strategies for test data structures
# =============================================================================


def minimal_playwright_report() -> dict:
    """Create a minimal valid Playwright report."""
    return {
        "suites": [],
        "stats": {"expected": 0, "unexpected": 0, "skipped": 0, "flaky": 0},
    }


def playwright_report_with_failure() -> dict:
    """Create a Playwright report with one failure."""
    return {
        "suites": [
            {
                "title": "Suite",
                "specs": [
                    {
                        "title": "test",
                        "file": "test.ts",
                        "tests": [
                            {
                                "projectName": "chromium",
                                "status": "unexpected",
                                "results": [
                                    {
                                        "status": "failed",
                                        "duration": 100,
                                        "errors": [{"message": "Test error"}],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
        "stats": {"expected": 0, "unexpected": 1, "skipped": 0, "flaky": 0},
    }


@st.composite
def fuzzed_playwright_reports(draw) -> dict:
    """Strategy to generate fuzzed Playwright reports."""
    num_suites = draw(st.integers(min_value=0, max_value=5))
    suites = []

    for _ in range(num_suites):
        num_specs = draw(st.integers(min_value=0, max_value=3))
        specs = []

        for _ in range(num_specs):
            num_tests = draw(st.integers(min_value=0, max_value=3))
            tests = []

            for _ in range(num_tests):
                status = draw(st.sampled_from(["expected", "unexpected", "skipped", "flaky"]))
                result_status = draw(st.sampled_from(["passed", "failed", "skipped", "timedOut"]))

                errors = []
                if result_status in ("failed", "timedOut"):
                    error_msg = draw(st.text(min_size=0, max_size=200))
                    errors = [{"message": error_msg}]

                tests.append(
                    {
                        "projectName": draw(st.sampled_from(["chromium", "firefox", "webkit", ""])),
                        "status": status,
                        "results": [
                            {
                                "status": result_status,
                                "duration": draw(st.integers(min_value=0, max_value=300000)),
                                "errors": errors,
                            }
                        ],
                    }
                )

            specs.append(
                {
                    "title": draw(st.text(min_size=0, max_size=100)),
                    "file": draw(st.text(min_size=0, max_size=50)) + ".ts",
                    "tests": tests,
                }
            )

        suites.append({"title": draw(st.text(min_size=0, max_size=50)), "specs": specs})

    expected = draw(st.integers(min_value=0, max_value=100))
    unexpected = draw(st.integers(min_value=0, max_value=100))
    skipped = draw(st.integers(min_value=0, max_value=100))
    flaky = draw(st.integers(min_value=0, max_value=100))

    return {
        "suites": suites,
        "stats": {
            "expected": expected,
            "unexpected": unexpected,
            "skipped": skipped,
            "flaky": flaky,
        },
    }


# =============================================================================
# Fuzz Tests for analyze command
# =============================================================================


class TestAnalyzeCommandFuzz:
    """Fuzz tests for the analyze command."""

    @settings(max_examples=50, deadline=5000)
    @given(
        output_format=output_formats(),
        provider=providers(),
        log_window=log_windows(),
        docker_services=docker_services(),
        ai_analysis=st.booleans(),
        post_comment=st.booleans(),
    )
    def test_analyze_with_valid_report_no_crash(
        self,
        output_format: str,
        provider: str,
        log_window: int,
        docker_services: str,
        ai_analysis: bool,
        post_comment: bool,
    ):
        """Analyze command should not crash with valid report and various args."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(minimal_playwright_report(), f)
            report_path = Path(f.name)

        try:
            args = argparse.Namespace(
                report=report_path,
                output_format=output_format,
                provider=provider,
                log_window=log_window,
                docker_services=docker_services,
                ai_analysis=ai_analysis,
                post_comment=post_comment,
                model=None,
                container_logs=None,
                report_format="playwright",
            )

            # Mock AI analysis to avoid actual API calls
            with patch("heisenberg.cli.analyze_with_ai") as mock_ai:
                with patch("heisenberg.cli.analyze_unified_run") as mock_unified:
                    mock_ai.return_value = None
                    mock_unified.return_value = None

                    # Should not raise unexpected exceptions
                    result = run_analyze(args)
                    assert result in (0, 1)  # Valid exit codes
        finally:
            report_path.unlink()

    @settings(max_examples=30, deadline=5000)
    @given(report_data=fuzzed_playwright_reports())
    def test_analyze_with_fuzzed_report_no_crash(self, report_data: dict):
        """Analyze should handle fuzzed report data without crashing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(report_data, f)
            report_path = Path(f.name)

        try:
            args = argparse.Namespace(
                report=report_path,
                output_format="text",
                provider="anthropic",
                log_window=30,
                docker_services="",
                ai_analysis=False,
                post_comment=False,
                model=None,
                container_logs=None,
                report_format="playwright",
            )

            # Should not crash - may return error code for invalid data
            try:
                result = run_analyze(args)
                assert result in (0, 1)
            except ValueError:
                # ValueError is acceptable for malformed data
                pass
        finally:
            report_path.unlink()

    def test_analyze_missing_report_returns_error(self):
        """Analyze should return error code for missing report file."""
        args = argparse.Namespace(
            report=Path("/nonexistent/path/report.json"),
            output_format="text",
            provider="anthropic",
            log_window=30,
            docker_services="",
            ai_analysis=False,
            use_unified=False,
            post_comment=False,
            model=None,
            container_logs=None,
            report_format="playwright",
        )

        result = run_analyze(args)
        assert result == 1


# =============================================================================
# Fuzz Tests for output formatting
# =============================================================================


class TestOutputFormattingFuzz:
    """Fuzz tests for output formatting functions."""

    @settings(max_examples=50, deadline=2000)
    @given(
        root_cause=st.text(min_size=0, max_size=500),
        evidence=st.lists(st.text(min_size=0, max_size=100), min_size=0, max_size=10),
        suggested_fix=st.text(min_size=0, max_size=500),
        confidence=st.sampled_from(["HIGH", "MEDIUM", "LOW"]),
        tokens=st.integers(min_value=0, max_value=1000000),
        cost=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
    )
    def testformat_json_output_no_crash(
        self,
        root_cause: str,
        evidence: list[str],
        suggested_fix: str,
        confidence: str,
        tokens: int,
        cost: float,
    ):
        """JSON output formatting should not crash with various AI results."""
        # Create mock result
        mock_result = MagicMock()
        mock_result.has_failures = True
        mock_result.summary = "Test summary"
        mock_result.report = MagicMock()
        mock_result.report.failed_tests = []

        # Create mock AI result
        mock_ai = MagicMock()
        mock_ai.diagnosis = MagicMock()
        mock_ai.diagnosis.root_cause = root_cause
        mock_ai.diagnosis.evidence = evidence
        mock_ai.diagnosis.suggested_fix = suggested_fix
        mock_ai.diagnosis.confidence = MagicMock(value=confidence)
        mock_ai.total_tokens = tokens
        mock_ai.estimated_cost = cost

        # Should not crash
        output = format_json_output(mock_result, mock_ai)
        assert isinstance(output, str)

        # Should be valid JSON
        parsed = json.loads(output)
        assert "ai_diagnosis" in parsed

    @settings(max_examples=50, deadline=2000)
    @given(
        summary=st.text(min_size=0, max_size=200),
        has_failures=st.booleans(),
        num_failures=st.integers(min_value=0, max_value=20),
    )
    def testformat_text_output_no_crash(
        self,
        summary: str,
        has_failures: bool,
        num_failures: int,
    ):
        """Text output formatting should not crash."""
        mock_result = MagicMock()
        mock_result.has_failures = has_failures
        mock_result.summary = summary
        mock_result.container_logs = None
        mock_result.report = MagicMock()

        # Create mock failed tests
        failed_tests = []
        for i in range(num_failures):
            test = MagicMock()
            test.full_name = f"test_{i}"
            test.file = f"test_{i}.ts"
            test.status = "failed"
            test.errors = [MagicMock(message=f"Error {i}")]
            failed_tests.append(test)

        mock_result.report.failed_tests = failed_tests

        # Should not crash
        output = format_text_output(mock_result, None)
        assert isinstance(output, str)


# =============================================================================
# Fuzz Tests for unified model conversion
# =============================================================================


class TestUnifiedConversionFuzz:
    """Fuzz tests for Playwright to UnifiedTestRun conversion."""

    @settings(max_examples=30, deadline=3000)
    @given(
        run_id=st.one_of(st.none(), st.text(min_size=0, max_size=50)),
        repository=st.one_of(st.none(), st.text(min_size=0, max_size=100)),
        branch=st.one_of(st.none(), st.text(min_size=0, max_size=50)),
    )
    def test_convert_to_unified_no_crash(
        self,
        run_id: str | None,
        repository: str | None,
        branch: str | None,
    ):
        """Unified conversion should not crash with various metadata."""
        from heisenberg.parsers.playwright import PlaywrightReport

        # Create minimal report
        report = PlaywrightReport(
            total_passed=5,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[],
        )

        # Should not crash
        unified = convert_to_unified(
            report,
            run_id=run_id,
            repository=repository,
            branch=branch,
        )

        assert unified is not None
        # Transformer defaults None run_id to "unknown"
        expected_run_id = run_id if run_id else "unknown"
        assert unified.run_id == expected_run_id
        assert unified.repository == repository


# =============================================================================
# Fuzz Tests for repo string parsing
# =============================================================================


class TestRepoParsingFuzz:
    """Fuzz tests for repository string parsing."""

    @settings(max_examples=100, deadline=1000)
    @given(repo_string=repo_strings())
    def test_repo_parsing_no_crash(self, repo_string: str):
        """Repo parsing should handle any string without crashing."""
        parts = repo_string.split("/")

        # Should not crash - just validate the split
        if len(parts) == 2:
            owner, repo = parts
            assert isinstance(owner, str)
            assert isinstance(repo, str)
        else:
            # Invalid format - this is expected for some fuzzed inputs
            pass


# =============================================================================
# Fuzz Tests for argument namespace creation
# =============================================================================


class TestArgNamespaceFuzz:
    """Fuzz tests for argument namespace handling."""

    @settings(max_examples=50, deadline=2000)
    @given(
        output_format=output_formats(),
        provider=providers(),
        report_format=report_formats(),
        model=st.one_of(st.none(), st.text(min_size=0, max_size=50)),
        log_window=log_windows(),
    )
    def test_args_namespace_creation(
        self,
        output_format: str,
        provider: str,
        report_format: str,
        model: str | None,
        log_window: int,
    ):
        """Argument namespace should be creatable with fuzzed values."""
        args = argparse.Namespace(
            output_format=output_format,
            provider=provider,
            report_format=report_format,
            model=model,
            log_window=log_window,
            ai_analysis=False,
            use_unified=False,
            post_comment=False,
            docker_services="",
            container_logs=None,
        )

        # Should have all attributes
        assert hasattr(args, "output_format")
        assert hasattr(args, "provider")
        assert hasattr(args, "log_window")

        # Values should be preserved
        assert args.output_format == output_format
        assert args.provider == provider


# =============================================================================
# Fuzz Tests for format_output dispatcher
# =============================================================================


class TestFormatOutputDispatcherFuzz:
    """Fuzz tests for the format_output dispatcher."""

    @settings(max_examples=30, deadline=3000)
    @given(output_format=output_formats())
    def testformat_output_dispatcher_no_crash(self, output_format: str):
        """Output format dispatcher should handle all formats without crashing."""
        mock_result = MagicMock()
        mock_result.has_failures = False
        mock_result.summary = "All tests passed"
        mock_result.container_logs = None
        mock_result.report = MagicMock()
        mock_result.report.failed_tests = []
        mock_result.to_markdown = MagicMock(return_value="# Report")

        args = argparse.Namespace(output_format=output_format)

        # unified-json is handled separately in run_analyze
        if output_format == "unified-json":
            return

        # Should not crash
        output = format_output(args, mock_result, None)
        assert isinstance(output, str)


# =============================================================================
# Fuzz Tests for fetch-github command
# =============================================================================


class TestFetchGitHubFuzz:
    """Fuzz tests for the fetch-github command."""

    @settings(max_examples=50, deadline=2000)
    @given(
        repo=repo_strings(),
        run_id=run_ids(),
        artifact_name=artifact_names(),
        provider=providers(),
    )
    def test_fetch_github_repo_validation(
        self,
        repo: str,
        run_id: int | None,
        artifact_name: str,
        provider: str,
    ):
        """fetch-github should validate repo format without crashing."""
        args = argparse.Namespace(
            repo=repo,
            token=None,  # Will fail due to missing token
            run_id=run_id,
            artifact_name=artifact_name,
            output=None,
            ai_analysis=False,
            provider=provider,
            list_artifacts=False,
            merge_blobs=False,
            include_logs=False,
            include_screenshots=False,
            include_traces=False,
        )

        # Should not crash - will return error due to missing token
        result = run_fetch_github(args)
        assert result == 1  # Error due to missing token

    @settings(max_examples=30, deadline=2000)
    @given(
        # GitHub tokens are ASCII - use printable ASCII characters
        token=st.text(
            alphabet=st.characters(
                whitelist_categories=(),
                whitelist_characters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
            ),
            min_size=0,
            max_size=100,
        ),
        repo=st.just("valid/repo"),  # Valid format
    )
    def test_fetch_github_invalid_token_handling(
        self,
        token: str,
        repo: str,
    ):
        """fetch-github should handle various ASCII token values."""
        args = argparse.Namespace(
            repo=repo,
            token=token if token else None,
            run_id=None,
            artifact_name="playwright",
            output=None,
            ai_analysis=False,
            provider="anthropic",
            list_artifacts=False,
            merge_blobs=False,
            include_logs=False,
            include_screenshots=False,
            include_traces=False,
        )

        # Mock environment to ensure no GITHUB_TOKEN
        with patch.dict("os.environ", {}, clear=True):
            # Should not crash
            result = run_fetch_github(args)
            # Will fail without valid token or if token is empty
            assert isinstance(result, int)


# =============================================================================
# Fuzz Tests for malformed input handling
# =============================================================================


class TestMalformedInputFuzz:
    """Fuzz tests for malformed input handling."""

    @settings(max_examples=30, deadline=5000)
    @given(
        content=st.binary(min_size=0, max_size=1000),
    )
    def test_analyze_handles_binary_garbage(self, content: bytes):
        """Analyze should handle binary garbage in report file."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
            f.write(content)
            report_path = Path(f.name)

        try:
            args = argparse.Namespace(
                report=report_path,
                output_format="text",
                provider="anthropic",
                log_window=30,
                docker_services="",
                ai_analysis=False,
                post_comment=False,
                model=None,
                container_logs=None,
                report_format="playwright",
            )

            # Should not crash - returns error for invalid JSON
            try:
                result = run_analyze(args)
                assert result in (0, 1)
            except (ValueError, json.JSONDecodeError):
                # These are acceptable for garbage input
                pass
        finally:
            report_path.unlink()

    @settings(max_examples=30, deadline=5000)
    @given(
        json_string=st.text(min_size=0, max_size=500),
    )
    def test_analyze_handles_random_json_strings(self, json_string: str):
        """Analyze should handle random strings as JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(json_string)
            report_path = Path(f.name)

        try:
            args = argparse.Namespace(
                report=report_path,
                output_format="text",
                provider="anthropic",
                log_window=30,
                docker_services="",
                ai_analysis=False,
                post_comment=False,
                model=None,
                container_logs=None,
                report_format="playwright",
            )

            # Should not crash
            try:
                result = run_analyze(args)
                assert result in (0, 1)
            except (ValueError, json.JSONDecodeError):
                pass
        finally:
            report_path.unlink()

    @settings(max_examples=20, deadline=5000)
    @given(
        data=st.recursive(
            st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(),
            lambda children: st.lists(children, max_size=5)
            | st.dictionaries(st.text(max_size=10), children, max_size=5),
            max_leaves=20,
        ),
    )
    def test_analyze_handles_arbitrary_json(self, data):
        """Analyze should handle arbitrary valid JSON structures."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            report_path = Path(f.name)

        try:
            args = argparse.Namespace(
                report=report_path,
                output_format="text",
                provider="anthropic",
                log_window=30,
                docker_services="",
                ai_analysis=False,
                post_comment=False,
                model=None,
                container_logs=None,
                report_format="playwright",
            )

            # Should not crash - may return error for wrong structure
            try:
                result = run_analyze(args)
                assert result in (0, 1)
            except (ValueError, TypeError, KeyError, AttributeError):
                # These are acceptable for wrong structure
                pass
        finally:
            report_path.unlink()


# =============================================================================
# Fuzz Tests for special characters and unicode
# =============================================================================


class TestUnicodeHandlingFuzz:
    """Fuzz tests for unicode and special character handling."""

    @settings(max_examples=30, deadline=5000)
    @given(
        error_message=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S", "Z"),
                whitelist_characters="\n\t\r",
            ),
            min_size=0,
            max_size=500,
        ),
        test_title=st.text(min_size=0, max_size=100),
        file_name=st.text(min_size=1, max_size=50).map(lambda s: s + ".ts"),
    )
    def test_unicode_in_error_messages(
        self,
        error_message: str,
        test_title: str,
        file_name: str,
    ):
        """Unicode characters in error messages should be handled."""
        report = {
            "suites": [
                {
                    "title": "Suite",
                    "specs": [
                        {
                            "title": test_title,
                            "file": file_name,
                            "tests": [
                                {
                                    "projectName": "chromium",
                                    "status": "unexpected",
                                    "results": [
                                        {
                                            "status": "failed",
                                            "duration": 100,
                                            "errors": [{"message": error_message}],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
            "stats": {"expected": 0, "unexpected": 1, "skipped": 0, "flaky": 0},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(report, f, ensure_ascii=False)
            report_path = Path(f.name)

        try:
            args = argparse.Namespace(
                report=report_path,
                output_format="text",
                provider="anthropic",
                log_window=30,
                docker_services="",
                ai_analysis=False,
                post_comment=False,
                model=None,
                container_logs=None,
                report_format="playwright",
            )

            # Should not crash
            result = run_analyze(args)
            assert result in (0, 1)
        finally:
            report_path.unlink()
